import uuid
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.errors import AppError

bearer_scheme = HTTPBearer(auto_error=False)


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


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> uuid.UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "UNAUTHENTICATED", "Missing or invalid authorization header.")

    return decode_access_token(credentials.credentials)
