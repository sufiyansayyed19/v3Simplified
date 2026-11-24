from datetime import datetime, timedelta, timezone
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

from app.api.v1.payments import get_now_utc  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.parking_callback import ParkingCallbackClient, get_callback_client  # noqa: E402


def _make_jwt(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=60)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class CapturingCallbackClient(ParkingCallbackClient):
    def __init__(self) -> None:
        self.deliveries: list[dict] = []

    def deliver_payment_result(
        self,
        booking_id: uuid.UUID,
        payment_id: uuid.UUID,
        status: str,
        transaction_id: str | None,
        processed_at: datetime,
        request_id: str | None = None,
    ) -> bool:
        self.deliveries.append({"booking_id": booking_id, "payment_id": payment_id, "status": status})
        return True


@pytest.fixture()
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    clock = {"now": datetime(2026, 11, 23, 9, 0, 0, tzinfo=timezone.utc)}
    cb_client = CapturingCallbackClient()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_now_utc] = lambda: clock["now"]
    app.dependency_overrides[get_callback_client] = lambda: cb_client

    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    yield {
        "client": TestClient(app),
        "clock": clock,
        "cb_client": cb_client,
        "user_a": user_a,
        "headers_a": {"Authorization": f"Bearer {_make_jwt(user_a)}"},
        "headers_b": {"Authorization": f"Bearer {_make_jwt(user_b)}"},
        "internal_headers": {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
    }
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_internal_payment_create_and_process(ctx):
    client = ctx["client"]
    expires = ctx["clock"]["now"] + timedelta(minutes=5)
    payload = {
        "booking_id": str(uuid.uuid4()),
        "user_id": str(ctx["user_a"]),
        "amount": 60.00,
        "expires_at": expires.isoformat(),
    }

    # Missing internal token -> 401
    assert client.post("/internal/v1/payments", json=payload).status_code == 401

    # Valid internal create -> 201
    r1 = client.post("/internal/v1/payments", json=payload, headers=ctx["internal_headers"])
    assert r1.status_code == 201
    p1 = r1.json()
    assert p1["status"] == "PENDING"

    # User B cannot access User A's payment (404)
    assert client.get(f"/api/v1/payments/{p1['payment_id']}", headers=ctx["headers_b"]).status_code == 404

    # Process payment -> SUCCESS + transaction_id + callback delivered
    r_ok = client.post(
        f"/api/v1/payments/{p1['payment_id']}/process",
        json={"payment_method": "UPI"},
        headers=ctx["headers_a"],
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["status"] == "SUCCESS"
    assert r_ok.json()["transaction_id"].startswith("TXN")
    assert len(ctx["cb_client"].deliveries) == 1
