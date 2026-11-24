from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.core.clock import IST_FALLBACK, get_now  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.parking import Booking, ParkingSlot  # noqa: E402
from app.services.clients import (  # noqa: E402
    PaymentServiceClient,
    VehicleInfo,
    VehicleServiceClient,
    get_payment_client,
    get_vehicle_client,
)


def _make_jwt(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=60)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class FakeVehicleClient(VehicleServiceClient):
    def __init__(self, vehicles: dict[uuid.UUID, VehicleInfo]) -> None:
        self.vehicles = vehicles

    def get_owned_vehicle(self, vehicle_id: uuid.UUID, bearer_token: str, request_id: str | None = None) -> VehicleInfo:
        return self.vehicles[vehicle_id]


class FakePaymentClient(PaymentServiceClient):
    def __init__(self) -> None:
        self.calls: list[uuid.UUID] = []

    def create_payment(
        self,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        amount: Decimal,
        expires_at: datetime,
        request_id: str | None = None,
    ) -> uuid.UUID:
        self.calls.append(booking_id)
        return uuid.uuid4()


@pytest.fixture()
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    with TestingSessionLocal() as db:
        db.add_all(
            [
                ParkingSlot(slot_number="C01", vehicle_type="CAR", is_charging_enabled=False),
                ParkingSlot(slot_number="C02", vehicle_type="CAR", is_charging_enabled=False),
                ParkingSlot(slot_number="C51", vehicle_type="CAR", is_charging_enabled=True),
                ParkingSlot(slot_number="B01", vehicle_type="BIKE", is_charging_enabled=False),
            ]
        )
        db.commit()

    ev_car_id = uuid.uuid4()
    non_ev_car_id = uuid.uuid4()
    vehicles = {
        ev_car_id: VehicleInfo(id=ev_car_id, vehicle_number="MH12EV0001", vehicle_type="CAR", is_ev=True, is_active=True),
        non_ev_car_id: VehicleInfo(
            id=non_ev_car_id, vehicle_number="MH12NA0002", vehicle_type="CAR", is_ev=False, is_active=True
        ),
    }

    clock = {"now": datetime(2026, 11, 23, 8, 30, 0, tzinfo=IST_FALLBACK)}
    vehicle_client = FakeVehicleClient(vehicles)
    payment_client = FakePaymentClient()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_now] = lambda: clock["now"]
    app.dependency_overrides[get_vehicle_client] = lambda: vehicle_client
    app.dependency_overrides[get_payment_client] = lambda: payment_client

    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    yield {
        "client": TestClient(app),
        "db_factory": TestingSessionLocal,
        "clock": clock,
        "ev_car_id": ev_car_id,
        "non_ev_car_id": non_ev_car_id,
        "payment_client": payment_client,
        "headers_a": {"Authorization": f"Bearer {_make_jwt(user_a)}"},
        "headers_b": {"Authorization": f"Bearer {_make_jwt(user_b)}"},
    }
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_availability_booking_snapshots_and_overlap(ctx):
    client = ctx["client"]
    h_a = ctx["headers_a"]
    h_b = ctx["headers_b"]

    # 1. Availability check for EV car with charging (1 slot C51, ₹20/hr)
    r_avail = client.get(
        "/api/v1/parking/availability",
        params={
            "date": "2026-11-23",
            "start_time": "10:00",
            "end_time": "13:00",
            "vehicle_id": str(ctx["ev_car_id"]),
            "requires_charging": "true",
        },
        headers=h_a,
    )
    assert r_avail.status_code == 200
    assert r_avail.json()["available_slots"] == 1
    assert Decimal(str(r_avail.json()["rate_per_hour"])) == Decimal("20.00")

    # 2. Create booking -> 201, ₹60, snapshots stored, slot C51 allocated
    payload = {
        "vehicle_id": str(ctx["ev_car_id"]),
        "date": "2026-11-23",
        "start_time": "10:00",
        "end_time": "13:00",
        "requires_charging": True,
    }
    r_book = client.post("/api/v1/parking/bookings", json=payload, headers=h_a)
    assert r_book.status_code == 201
    b = r_book.json()
    assert b["slot_number"] == "C51"
    assert b["vehicle_number_snapshot"] == "MH12EV0001"
    assert Decimal(str(b["amount"])) == Decimal("60.00")
    assert b["status"] == "PAYMENT_PENDING"
    assert b["payment_id"] is not None

    # 3. User A tries overlapping booking -> 409 USER_BOOKING_OVERLAP
    r_user_ov = client.post(
        "/api/v1/parking/bookings",
        json={
            "vehicle_id": str(ctx["non_ev_car_id"]),
            "date": "2026-11-23",
            "start_time": "12:00",
            "end_time": "14:00",
            "requires_charging": False,
        },
        headers=h_a,
    )
    assert r_user_ov.status_code == 409
    assert r_user_ov.json()["error"]["code"] == "USER_BOOKING_OVERLAP"

    # 4. Adjacent interval (13:00-15:00) for User A is ALLOWED
    r_adj = client.post(
        "/api/v1/parking/bookings",
        json={
            "vehicle_id": str(ctx["non_ev_car_id"]),
            "date": "2026-11-23",
            "start_time": "13:00",
            "end_time": "15:00",
            "requires_charging": False,
        },
        headers=h_a,
    )
    assert r_adj.status_code == 201
    assert Decimal(str(r_adj.json()["amount"])) == Decimal("20.00")

    # 5. User B tries charging car for 10:00-13:00 -> 409 NO_PARKING_CAPACITY (C51 is held)
    r_full = client.post("/api/v1/parking/bookings", json=payload, headers=h_b)
    assert r_full.status_code == 409
    assert r_full.json()["error"]["code"] == "NO_PARKING_CAPACITY"


def test_time_rules_and_sunday_closure(ctx):
    client = ctx["client"]
    h_a = ctx["headers_a"]

    # Non-EV requesting charging -> 422 CHARGING_NOT_SUPPORTED
    r_non_ev = client.post(
        "/api/v1/parking/bookings",
        json={
            "vehicle_id": str(ctx["non_ev_car_id"]),
            "date": "2026-11-23",
            "start_time": "10:00",
            "end_time": "11:00",
            "requires_charging": True,
        },
        headers=h_a,
    )
    assert r_non_ev.status_code == 422
    assert r_non_ev.json()["error"]["code"] == "CHARGING_NOT_SUPPORTED"

    # Past time slot (08:00 when now is 08:30) -> 422 INVALID_BOOKING_TIME
    r_past = client.post(
        "/api/v1/parking/bookings",
        json={
            "vehicle_id": str(ctx["non_ev_car_id"]),
            "date": "2026-11-23",
            "start_time": "08:00",
            "end_time": "09:00",
            "requires_charging": False,
        },
        headers=h_a,
    )
    assert r_past.status_code == 422

    # Sunday (2026-11-22) is closed
    ctx["clock"]["now"] = datetime(2026, 11, 21, 10, 0, 0, tzinfo=IST_FALLBACK)
    r_sun = client.post(
        "/api/v1/parking/bookings",
        json={
            "vehicle_id": str(ctx["non_ev_car_id"]),
            "date": "2026-11-22",
            "start_time": "10:00",
            "end_time": "11:00",
            "requires_charging": False,
        },
        headers=h_a,
    )
    assert r_sun.status_code == 422
    assert r_sun.json()["error"]["code"] == "BOOKING_WINDOW_VIOLATION"


def test_cancellation_and_lazy_hold_expiry(ctx):
    client = ctx["client"]
    h_a = ctx["headers_a"]

    r = client.post(
        "/api/v1/parking/bookings",
        json={
            "vehicle_id": str(ctx["non_ev_car_id"]),
            "date": "2026-11-23",
            "start_time": "10:00",
            "end_time": "11:00",
            "requires_charging": False,
        },
        headers=h_a,
    )
    booking_id = r.json()["booking_id"]

    # Cannot cancel PAYMENT_PENDING booking
    assert client.post(f"/api/v1/parking/bookings/{booking_id}/cancel", headers=h_a).status_code == 409

    # Mark booking CONFIRMED in DB
    with ctx["db_factory"]() as db:
        b = db.get(Booking, uuid.UUID(booking_id))
        b.status = "CONFIRMED"
        db.commit()

    # Cancel before start_time -> ALLOWED
    ctx["clock"]["now"] = datetime(2026, 11, 23, 9, 55, 0, tzinfo=IST_FALLBACK)
    r_cancel = client.post(f"/api/v1/parking/bookings/{booking_id}/cancel", headers=h_a)
    assert r_cancel.status_code == 200
    assert r_cancel.json()["status"] == "CANCELLED"

    # Unpaid hold expires after 5 minutes on GET
    ctx["clock"]["now"] = datetime(2026, 11, 23, 8, 30, 0, tzinfo=IST_FALLBACK)
    r2 = client.post(
        "/api/v1/parking/bookings",
        json={
            "vehicle_id": str(ctx["non_ev_car_id"]),
            "date": "2026-11-23",
            "start_time": "14:00",
            "end_time": "15:00",
            "requires_charging": False,
        },
        headers=h_a,
    )
    b2_id = r2.json()["booking_id"]

    ctx["clock"]["now"] = datetime(2026, 11, 23, 8, 36, 0, tzinfo=IST_FALLBACK)
    r_get = client.get(f"/api/v1/parking/bookings/{b2_id}", headers=h_a)
    assert r_get.status_code == 200
    assert r_get.json()["status"] == "EXPIRED"
