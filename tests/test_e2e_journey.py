"""Full End-to-End Multi-Service Journey Test across all 4 microservices + 4 PostgreSQL DBs."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import time
import uuid

import httpx
import jwt
import pytest
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = str(REPO_ROOT / ".venv" / "Scripts" / "python.exe")
JWT_SECRET_KEY = "super-secret-jwt-key-for-corporate-parking"

PORTS = {
    "auth": 18001,
    "vehicle": 18002,
    "parking": 18003,
    "payment": 18004,
}


def _wait_for_health(url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=1.0)
            if r.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"Service did not become healthy at {url}")


def _next_operating_date_iso() -> str:
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    tomorrow = now_ist.date() + timedelta(days=1)
    if tomorrow.weekday() == 6:  # Sunday
        return now_ist.date().isoformat()
    return tomorrow.isoformat()


def _make_jwt(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=60)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")


@pytest.fixture(scope="module")
def live_stack():
    base_env = os.environ.copy()
    base_env.update(
        {
            "VEHICLE_SERVICE_URL": f"http://127.0.0.1:{PORTS['vehicle']}",
            "PARKING_SERVICE_URL": f"http://127.0.0.1:{PORTS['parking']}",
            "PAYMENT_SERVICE_URL": f"http://127.0.0.1:{PORTS['payment']}",
            "JWT_SECRET_KEY": JWT_SECRET_KEY,
            "INTERNAL_SERVICE_TOKEN": "dev-internal-service-token",
            "COMPANY_EMAIL_DOMAIN": "company.com",
            "PAYMENT_SIMULATION_DEFAULT_OUTCOME": "SUCCESS",
            "ENABLE_TEST_PAYMENT_OVERRIDE": "true",
            "ENVIRONMENT": "development",
        }
    )

    specs = [
        ("auth", REPO_ROOT / "services" / "user-auth-service", PORTS["auth"]),
        ("vehicle", REPO_ROOT / "services" / "vehicle-service", PORTS["vehicle"]),
        ("parking", REPO_ROOT / "services" / "parking-service", PORTS["parking"]),
        ("payment", REPO_ROOT / "services" / "payment-service", PORTS["payment"]),
    ]

    procs: list[subprocess.Popen] = []
    try:
        for _name, cwd, port in specs:
            p = subprocess.Popen(
                [PYTHON_EXE, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=str(cwd),
                env=base_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            procs.append(p)

        for _name, _cwd, port in specs:
            _wait_for_health(f"http://127.0.0.1:{port}/health")

        yield {
            "auth": f"http://127.0.0.1:{PORTS['auth']}",
            "vehicle": f"http://127.0.0.1:{PORTS['vehicle']}",
            "parking": f"http://127.0.0.1:{PORTS['parking']}",
            "payment": f"http://127.0.0.1:{PORTS['payment']}",
        }
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


def _cleanup_e2e_user(user_id: uuid.UUID) -> None:
    uid_str = str(user_id)
    dbs = [
        ("postgresql+psycopg://payment_user:payment_pass@localhost:5432/payment_db", "DELETE FROM payments WHERE user_id = :uid"),
        ("postgresql+psycopg://parking_user:parking_pass@localhost:5432/parking_db", "DELETE FROM bookings WHERE user_id = :uid"),
        ("postgresql+psycopg://vehicle_user:vehicle_pass@localhost:5432/vehicle_db", "DELETE FROM vehicles WHERE user_id = :uid"),
    ]
    for url, sql in dbs:
        eng = create_engine(url)
        with eng.begin() as conn:
            conn.execute(text(sql), {"uid": uid_str})
        eng.dispose()


def test_full_e2e_corporate_parking_journey(live_stack):
    urls = live_stack
    user_id = uuid.uuid4()
    headers = {"Authorization": f"Bearer {_make_jwt(user_id)}"}
    booking_date = _next_operating_date_iso()

    try:
        with httpx.Client(timeout=10.0) as client:
            # 1. Register an EV car in Vehicle Service (:8002)
            r_veh = client.post(
                f"{urls['vehicle']}/api/v1/vehicles",
                json={"vehicle_number": f"E2E {user_id.hex[:6]}", "vehicle_type": "CAR", "is_ev": True},
                headers=headers,
            )
            assert r_veh.status_code == 201, r_veh.text
            vehicle_id = r_veh.json()["id"]

            # 2. Check availability in Parking Service (:8003) -> calls Vehicle Service (:8002)
            r_avail = client.get(
                f"{urls['parking']}/api/v1/parking/availability",
                params={
                    "date": booking_date,
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "vehicle_id": vehicle_id,
                    "requires_charging": "true",
                },
                headers=headers,
            )
            assert r_avail.status_code == 200, r_avail.text
            assert r_avail.json()["available"] is True
            assert float(r_avail.json()["rate_per_hour"]) == 20.0

            # 3. Create booking in Parking Service (:8003) -> calls Vehicle + Payment (:8004)
            r_book = client.post(
                f"{urls['parking']}/api/v1/parking/bookings",
                json={
                    "vehicle_id": vehicle_id,
                    "date": booking_date,
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "requires_charging": True,
                },
                headers=headers,
            )
            assert r_book.status_code == 201, r_book.text
            booking = r_book.json()
            booking_id = booking["booking_id"]
            payment_id = booking["payment_id"]
            assert booking["status"] == "PAYMENT_PENDING"
            assert float(booking["amount"]) == 40.0
            assert payment_id is not None

            # 4. Process payment in Payment Service (:8004) -> callbacks Parking Service (:8003)
            r_pay = client.post(
                f"{urls['payment']}/api/v1/payments/{payment_id}/process",
                json={"payment_method": "UPI"},
                headers=headers,
            )
            assert r_pay.status_code == 200, r_pay.text
            assert r_pay.json()["status"] == "SUCCESS"
            assert r_pay.json()["transaction_id"].startswith("TXN")

            # 5. Verify booking is now CONFIRMED in Parking Service
            r_get_booking = client.get(f"{urls['parking']}/api/v1/parking/bookings/{booking_id}", headers=headers)
            assert r_get_booking.status_code == 200, r_get_booking.text
            assert r_get_booking.json()["status"] == "CONFIRMED"

            # 6. Cancel the confirmed booking
            r_cancel = client.post(f"{urls['parking']}/api/v1/parking/bookings/{booking_id}/cancel", headers=headers)
            assert r_cancel.status_code == 200, r_cancel.text
            assert r_cancel.json()["status"] == "CANCELLED"
    finally:
        _cleanup_e2e_user(user_id)
