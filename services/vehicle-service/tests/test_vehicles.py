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

from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


def _make_jwt(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=60)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture()
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    yield {
        "client": client,
        "headers_a": {"Authorization": f"Bearer {_make_jwt(user_a)}"},
        "headers_b": {"Authorization": f"Bearer {_make_jwt(user_b)}"},
    }
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_vehicle_crud_normalization_and_reregistration(ctx):
    client = ctx["client"]
    h_a = ctx["headers_a"]

    # 1. Create with messy formatting -> normalized
    r1 = client.post(
        "/api/v1/vehicles",
        json={"vehicle_number": "mh 12-ab 1234", "vehicle_type": "CAR", "is_ev": True},
        headers=h_a,
    )
    assert r1.status_code == 201
    v1 = r1.json()
    assert v1["vehicle_number"] == "MH12AB1234"
    assert v1["is_active"] is True

    # 2. Duplicate active plate for same user -> 409
    r_dup = client.post(
        "/api/v1/vehicles",
        json={"vehicle_number": "MH12AB1234", "vehicle_type": "CAR", "is_ev": False},
        headers=h_a,
    )
    assert r_dup.status_code == 409
    assert r_dup.json()["error"]["code"] == "VEHICLE_ALREADY_REGISTERED"

    # 3. List returns active vehicles
    r_list = client.get("/api/v1/vehicles", headers=h_a)
    assert r_list.status_code == 200
    assert len(r_list.json()["vehicles"]) == 1

    # 4. Update vehicle
    r_upd = client.put(
        f"/api/v1/vehicles/{v1['id']}",
        json={"vehicle_number": "MH12 AB 9999", "vehicle_type": "CAR", "is_ev": False},
        headers=h_a,
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["vehicle_number"] == "MH12AB9999"
    assert r_upd.json()["is_ev"] is False

    # 5. Soft deactivate
    r_del = client.delete(f"/api/v1/vehicles/{v1['id']}", headers=h_a)
    assert r_del.status_code == 200
    assert r_del.json()["is_active"] is False

    # 6. Inactive vehicle hidden from GET and list
    assert client.get(f"/api/v1/vehicles/{v1['id']}", headers=h_a).status_code == 404
    assert client.get("/api/v1/vehicles", headers=h_a).json()["vehicles"] == []

    # 7. Re-registering deactivated plate creates a new active row
    r_re = client.post(
        "/api/v1/vehicles",
        json={"vehicle_number": "MH12AB9999", "vehicle_type": "CAR", "is_ev": True},
        headers=h_a,
    )
    assert r_re.status_code == 201
    assert r_re.json()["id"] != v1["id"]


def test_owner_isolation_and_invalid_type(ctx):
    client = ctx["client"]
    h_a = ctx["headers_a"]
    h_b = ctx["headers_b"]

    v = client.post(
        "/api/v1/vehicles",
        json={"vehicle_number": "KA01CD5678", "vehicle_type": "BIKE", "is_ev": False},
        headers=h_a,
    ).json()

    # User B cannot view or delete User A's vehicle (404)
    assert client.get(f"/api/v1/vehicles/{v['id']}", headers=h_b).status_code == 404
    assert client.delete(f"/api/v1/vehicles/{v['id']}", headers=h_b).status_code == 404

    # Invalid vehicle_type rejected with 422
    r_bad = client.post(
        "/api/v1/vehicles",
        json={"vehicle_number": "MH12AB1234", "vehicle_type": "TRUCK", "is_ev": False},
        headers=h_a,
    )
    assert r_bad.status_code == 422
