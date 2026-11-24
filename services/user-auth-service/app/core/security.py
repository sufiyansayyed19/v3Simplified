import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.models.auth import User

bearer_scheme = HTTPBearer(auto_error=False)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_allowed_corporate_email(normalized_email: str) -> bool:
    allowed_domain = settings.COMPANY_EMAIL_DOMAIN.strip().lower()
    if "@" not in normalized_email:
        return False
    _, domain = normalized_email.rsplit("@", 1)
    return domain == allowed_domain


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise AppError(401, "UNAUTHENTICATED", "Invalid or expired access token.")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "UNAUTHENTICATED", "Missing or invalid authorization header.")

    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if not user:
        raise AppError(401, "UNAUTHENTICATED", "Authenticated user not found.")
    return user
