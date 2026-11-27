r"""Simple load & response-time benchmark script for ParkingSimplified.

Usage (after starting services with .\scripts\start_all.ps1):
    .\.venv\Scripts\python.exe scripts/load_check.py
    .\.venv\Scripts\python.exe scripts/load_check.py --requests 200 --concurrency 50
"""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import statistics
import time
import uuid

import httpx
import jwt

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-jwt-key-for-corporate-parking")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
PARKING_URL = os.getenv("PARKING_SERVICE_URL", "http://127.0.0.1:8003").rstrip("/")
VEHICLE_URL = os.getenv("VEHICLE_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/")


def _make_jwt(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def _next_operating_date_iso() -> str:
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    tomorrow = now_ist.date() + timedelta(days=1)
    if tomorrow.weekday() == 6:  # Sunday closed
        return (tomorrow + timedelta(days=1)).isoformat()
    return tomorrow.isoformat()


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = int(round((pct / 100.0) * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(idx, len(sorted_values) - 1))]


def run_benchmark(
    label: str,
    url: str,
    total_requests: int,
    concurrency: int,
    headers: dict[str, str] | None = None,
) -> None:
    """Fires `total_requests` concurrent HTTP GET requests and prints latency metrics."""
    def _single_call(_idx: int) -> tuple[int | str, float]:
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return resp.status_code, elapsed_ms
        except httpx.HTTPError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return type(exc).__name__, elapsed_ms

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(_single_call, range(total_requests)))
    total_wall_sec = time.perf_counter() - wall_start

    status_counts = Counter(status for status, _ in results)
    latencies = sorted(ms for _, ms in results)
    rps = total_requests / total_wall_sec if total_wall_sec > 0 else 0.0

    print(f"\n=== {label} ===")
    print(f"Target:       {url}")
    print(f"Requests:     {total_requests} (concurrency={concurrency})")
    print(f"Statuses:     {dict(status_counts)}")
    print(f"Total Time:   {total_wall_sec:.3f} s  ({rps:.1f} req/s)")
    print(
        f"Latency (ms): min={latencies[0]:.2f} | "
        f"avg={statistics.mean(latencies):.2f} | "
        f"p50={statistics.median(latencies):.2f} | "
        f"p95={_percentile(latencies, 95):.2f} | "
        f"max={latencies[-1]:.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Load & response-time benchmark for ParkingSimplified")
    parser.add_argument("--requests", type=int, default=200, help="Total requests per benchmark (default: 200)")
    parser.add_argument("--concurrency", type=int, default=50, help="Parallel worker threads (default: 50)")
    args = parser.parse_args()

    try:
        r = httpx.get(f"{PARKING_URL}/health", timeout=2.0)
        r.raise_for_status()
    except httpx.HTTPError:
        print(f"[ERROR] Parking Service is not reachable at {PARKING_URL}.")
        print(r"Start all services first using: .\scripts\start_all.ps1")
        raise SystemExit(1)

    user_id = uuid.uuid4()
    token = _make_jwt(user_id)
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Baseline HTTP / FastAPI route (no DB, no cross-service hop)
    run_benchmark(
        label="1. Baseline Health Check (No DB)",
        url=f"{PARKING_URL}/health",
        total_requests=args.requests,
        concurrency=args.concurrency,
    )

    # 2. Authenticated PostgreSQL Read (JWT decode + SQLAlchemy query)
    run_benchmark(
        label="2. Authenticated Bookings Read (JWT + PostgreSQL)",
        url=f"{PARKING_URL}/api/v1/parking/bookings",
        total_requests=args.requests,
        concurrency=args.concurrency,
        headers=auth_headers,
    )

    # 3. Cross-Service Read (Parking -> Vehicle REST call + PostgreSQL slot query)
    vehicle_id: str | None = None
    try:
        plate = f"LD{uuid.uuid4().hex[:6].upper()}"
        vr = httpx.post(
            f"{VEHICLE_URL}/api/v1/vehicles",
            json={"vehicle_number": plate, "vehicle_type": "CAR", "is_ev": False},
            headers=auth_headers,
            timeout=3.0,
        )
        if vr.status_code == 201:
            vehicle_id = vr.json()["id"]
            target_date = _next_operating_date_iso()
            avail_url = (
                f"{PARKING_URL}/api/v1/parking/availability"
                f"?date={target_date}&start_time=10:00&end_time=12:00"
                f"&vehicle_id={vehicle_id}&requires_charging=false"
            )
            run_benchmark(
                label="3. Cross-Service Availability Check (Parking -> Vehicle + PostgreSQL)",
                url=avail_url,
                total_requests=args.requests,
                concurrency=args.concurrency,
                headers=auth_headers,
            )
        else:
            print(f"\n[SKIP] Cross-service check skipped (Vehicle create returned {vr.status_code}).")
    except httpx.HTTPError:
        print(f"\n[SKIP] Vehicle Service not reachable at {VEHICLE_URL}; skipping Benchmark 3.")
    finally:
        if vehicle_id is not None:
            try:
                httpx.delete(f"{VEHICLE_URL}/api/v1/vehicles/{vehicle_id}", headers=auth_headers, timeout=2.0)
            except httpx.HTTPError:
                pass


if __name__ == "__main__":
    main()
