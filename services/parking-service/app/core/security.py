from dataclasses import dataclass
import uuid

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.errors import AppError

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user_id: uuid.UUID
    raw_token: str


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


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "UNAUTHENTICATED", "Missing or invalid authorization header.")

    user_id = decode_access_token(credentials.credentials)
    return AuthContext(user_id=user_id, raw_token=credentials.credentials)
