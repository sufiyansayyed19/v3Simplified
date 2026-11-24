from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.core.clock import IST_FALLBACK, as_utc, get_now  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.parking import Booking, ParkingSlot  # noqa: E402


@pytest.fixture()
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    clock = {"now": datetime(2026, 11, 23, 9, 0, 0, tzinfo=IST_FALLBACK)}

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_now] = lambda: clock["now"]

    with TestingSessionLocal() as db:
        slot = ParkingSlot(slot_number="C01", vehicle_type="CAR", is_charging_enabled=False)
        db.add(slot)
        db.commit()
        slot_id = slot.id

    yield {
        "client": TestClient(app),
        "db_factory": TestingSessionLocal,
        "clock": clock,
        "slot_id": slot_id,
        "pay_headers": {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
    }
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_payment_result_callback(ctx):
    client = ctx["client"]
    now_utc = as_utc(ctx["clock"]["now"])
    payment_id = uuid.uuid4()

    with ctx["db_factory"]() as db:
        b = Booking(
            user_id=uuid.uuid4(),
            vehicle_id=uuid.uuid4(),
            vehicle_number_snapshot="MH12AB1234",
            vehicle_type_snapshot="CAR",
            is_ev_snapshot=False,
            slot_id=ctx["slot_id"],
            booking_date=date(2026, 11, 23),
            start_time=time(11, 0),
            end_time=time(12, 0),
            requires_charging=False,
            status="PAYMENT_PENDING",
            amount=Decimal("10.00"),
            hold_expires_at=now_utc + timedelta(minutes=5),
            payment_id=payment_id,
        )
        db.add(b)
        db.commit()
        booking_id = b.id

    cb_body = {
        "payment_id": str(payment_id),
        "status": "SUCCESS",
        "transaction_id": "TXN123",
        "processed_at": now_utc.isoformat(),
    }
    # Missing internal token -> 401
    assert client.post(f"/internal/v1/bookings/{booking_id}/payment-result", json=cb_body).status_code == 401

    # Valid SUCCESS within hold -> CONFIRMED
    r1 = client.post(
        f"/internal/v1/bookings/{booking_id}/payment-result",
        json=cb_body,
        headers=ctx["pay_headers"],
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "CONFIRMED"
    assert r1.json()["result"] == "APPLIED"
