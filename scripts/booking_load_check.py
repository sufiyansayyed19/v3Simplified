r"""Concurrent write-path load & locking benchmark for POST /api/v1/parking/bookings.

Tests the full synchronized write pipeline across live services:
  Vehicle check (8002) -> PostgreSQL FOR UPDATE slot lock (8003) -> Payment create (8004)

Usage (after starting services with .\scripts\start_all.ps1):
    .\.venv\Scripts\python.exe scripts/booking_load_check.py
    .\.venv\Scripts\python.exe scripts/booking_load_check.py --stages 20 50 100
"""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import statistics
import threading
import time
import uuid

import httpx
import jwt
from sqlalchemy import create_engine, text

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-jwt-key-for-corporate-parking")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
VEHICLE_URL = os.getenv("VEHICLE_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/")
PARKING_URL = os.getenv("PARKING_SERVICE_URL", "http://127.0.0.1:8003").rstrip("/")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", "http://127.0.0.1:8004").rstrip("/")

PAYMENT_DB_URL = os.getenv(
    "PAYMENT_DATABASE_URL",
    "postgresql+psycopg://payment_user:payment_pass@localhost:5432/payment_db",
)
PARKING_DB_URL = os.getenv(
    "PARKING_DATABASE_URL",
    "postgresql+psycopg://parking_user:parking_pass@localhost:5432/parking_db",
)
VEHICLE_DB_URL = os.getenv(
    "VEHICLE_DATABASE_URL",
    "postgresql+psycopg://vehicle_user:vehicle_pass@localhost:5432/vehicle_db",
)


def _make_jwt(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _pick_booking_window() -> tuple[str, str, str]:
    """Selects a valid operating date (today or tomorrow, never Sunday) and whole-hour slot."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    tomorrow = now_ist.date() + timedelta(days=1)
    if tomorrow.weekday() != 6:
        return tomorrow.isoformat(), "10:00", "11:00"

    # If tomorrow is Sunday, book a future slot today
    start_hour = max(7, now_ist.hour + 1)
    if start_hour >= 22:
        raise RuntimeError("No future operating hours left today (Saturday night) and tomorrow is Sunday.")
    return now_ist.date().isoformat(), f"{start_hour:02d}:00", f"{start_hour + 1:02d}:00"


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = int(round((pct / 100.0) * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(idx, len(sorted_values) - 1))]


def _cleanup_test_users(user_ids: list[uuid.UUID]) -> None:
    uid_strs = [str(uid) for uid in user_ids]
    targets = [
        (
            PARKING_DB_URL,
            "DELETE FROM bookings WHERE vehicle_number_snapshot LIKE 'BK%' OR user_id = ANY(CAST(:uids AS uuid[]))",
        ),
        (
            PAYMENT_DB_URL,
            "DELETE FROM payments WHERE user_id = ANY(CAST(:uids AS uuid[]))",
        ),
        (
            VEHICLE_DB_URL,
            "DELETE FROM vehicles WHERE vehicle_number LIKE 'BK%' OR user_id = ANY(CAST(:uids AS uuid[]))",
        ),
    ]
    for db_url, sql in targets:
        eng = create_engine(db_url)
        try:
            with eng.begin() as conn:
                conn.execute(text(sql), {"uids": uid_strs})
        finally:
            eng.dispose()


def _setup_users_and_vehicles(count: int) -> list[tuple[uuid.UUID, str, str]]:
    """Registers `count` distinct users and 1 CAR vehicle each on Vehicle Service."""
    def _create_one(_idx: int) -> tuple[uuid.UUID, str, str]:
        uid = uuid.uuid4()
        token = _make_jwt(uid)
        plate = f"BK{uid.hex[:8].upper()}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{VEHICLE_URL}/api/v1/vehicles",
                json={"vehicle_number": plate, "vehicle_type": "CAR", "is_ev": False},
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code != 201:
            raise RuntimeError(f"Failed to register test vehicle ({resp.status_code}): {resp.text}")
        return uid, token, resp.json()["id"]

    with ThreadPoolExecutor(max_workers=min(count, 25)) as pool:
        return list(pool.map(_create_one, range(count)))


def run_booking_stage(concurrent_users: int, target_date: str, start_time: str, end_time: str) -> None:
    _cleanup_test_users([])
    print(f"\n=== Stage: {concurrent_users} Concurrent Distinct Users -> POST /api/v1/parking/bookings ===")
    print(f"Preparing {concurrent_users} unique users and vehicles on Vehicle Service...")
    actors = _setup_users_and_vehicles(concurrent_users)
    user_ids = [uid for uid, _, _ in actors]

    barrier = threading.Barrier(concurrent_users)

    def _fire_booking(actor: tuple[uuid.UUID, str, str]) -> tuple[int | str, str | None, str | None, float]:
        _uid, token, vehicle_id = actor
        payload = {
            "vehicle_id": vehicle_id,
            "date": target_date,
            "start_time": start_time,
            "end_time": end_time,
            "requires_charging": False,
        }
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=30.0) as client:
            barrier.wait()
            t0 = time.perf_counter()
            try:
                resp = client.post(f"{PARKING_URL}/api/v1/parking/bookings", json=payload, headers=headers)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                body = resp.json()
                slot_num = body.get("slot_number") if resp.status_code == 201 else None
                err_code = body.get("error", {}).get("code") if resp.status_code != 201 else None
                return resp.status_code, slot_num, err_code, elapsed_ms
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                return type(exc).__name__, None, str(exc), elapsed_ms

    try:
        wall_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrent_users) as pool:
            results = list(pool.map(_fire_booking, actors))
        total_wall_sec = time.perf_counter() - wall_start

        status_counts = Counter(code for code, _, _, _ in results)
        error_codes = Counter(err for code, _, err, _ in results if code != 201)
        allocated_slots = [slot for code, slot, _, _ in results if code == 201 and slot is not None]
        unique_slots = set(allocated_slots)
        latencies = sorted(ms for _, _, _, ms in results)
        rps = concurrent_users / total_wall_sec if total_wall_sec > 0 else 0.0

        print(f"Booking Slot: {target_date} {start_time}-{end_time} (Non-EV CAR, 50 capacity)")
        print(f"Statuses:     {dict(status_counts)}")
        if error_codes:
            print(f"Error Codes:  {dict(error_codes)}")
        print(
            f"Double-Book?: {'PASS (0 duplicates across ' + str(len(allocated_slots)) + ' bookings)' if len(allocated_slots) == len(unique_slots) else 'FAIL (DUPLICATE SLOTS DETECTED!)'}"
        )
        print(f"Total Time:   {total_wall_sec:.3f} s  ({rps:.1f} req/s)")
        print(
            f"Latency (ms): min={latencies[0]:.2f} | "
            f"avg={statistics.mean(latencies):.2f} | "
            f"p50={statistics.median(latencies):.2f} | "
            f"p95={_percentile(latencies, 95):.2f} | "
            f"max={latencies[-1]:.2f}"
        )
    finally:
        _cleanup_test_users(user_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Concurrent booking write-path benchmark for ParkingSimplified")
    parser.add_argument(
        "--stages",
        type=int,
        nargs="+",
        default=[20, 50, 100],
        help="Concurrent user stages to test sequentially (default: 20 50 100)",
    )
    args = parser.parse_args()

    for name, url in [("Vehicle", VEHICLE_URL), ("Parking", PARKING_URL), ("Payment", PAYMENT_URL)]:
        try:
            r = httpx.get(f"{url}/health", timeout=2.0)
            r.raise_for_status()
        except httpx.HTTPError:
            print(f"[ERROR] {name} Service is not reachable at {url}.")
            print(r"Start all services first using: .\scripts\start_all.ps1")
            raise SystemExit(1)

    target_date, start_time, end_time = _pick_booking_window()
    for n in args.stages:
        run_booking_stage(n, target_date, start_time, end_time)


if __name__ == "__main__":
    main()
