from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.email_sender import EmailSender, get_email_sender  # noqa: E402


class CapturingEmailSender(EmailSender):
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_otp(self, email: str, code: str, expires_minutes: int) -> None:
        self.sent.append((email, code))


@pytest.fixture()
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    email_sender = CapturingEmailSender()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_sender] = lambda: email_sender

    client = TestClient(app)
    yield {
        "client": client,
        "db_factory": TestingSessionLocal,
        "email_sender": email_sender,
    }
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_health(ctx):
    resp = ctx["client"].get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "user-auth-service"


def test_reject_non_corporate_email(ctx):
    resp = ctx["client"].post("/api/v1/auth/company/send-code", json={"email": "outsider@gmail.com"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CORPORATE_EMAIL_REQUIRED"


def test_company_otp_login_and_me_flow(ctx):
    client = ctx["client"]
    sender = ctx["email_sender"]

    # 1. Send OTP
    r1 = client.post("/api/v1/auth/company/send-code", json={"email": "Alice@Company.com"})
    assert r1.status_code == 200
    assert len(sender.sent) == 1
    sent_email, otp_code = sender.sent[0]
    assert sent_email == "alice@company.com"

    # 2. Wrong OTP fails with 401
    r_bad = client.post("/api/v1/auth/company/verify", json={"email": "alice@company.com", "code": "000000"})
    assert r_bad.status_code == 401
    assert r_bad.json()["error"]["code"] == "INVALID_OR_EXPIRED_CODE"

    # 3. Correct OTP authenticates and returns HS256 JWT access_token
    r_ok = client.post("/api/v1/auth/company/verify", json={"email": "alice@company.com", "code": otp_code})
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "alice@company.com"
    access_token = body["access_token"]

    # 4. Replaying same OTP fails because is_used is now True
    r_replay = client.post("/api/v1/auth/company/verify", json={"email": "alice@company.com", "code": otp_code})
    assert r_replay.status_code == 401

    # 5. /users/me succeeds with HS256 Bearer token
    r_me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert r_me.status_code == 200
    assert r_me.json()["email"] == "alice@company.com"
