from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    generate_otp_code,
    get_current_user,
    is_allowed_corporate_email,
    normalize_email,
)
from app.models.auth import User, VerificationCode
from app.schemas.auth import (
    AuthTokenResponse,
    MessageResponse,
    SendCodeRequest,
    UpdateProfileRequest,
    UserProfile,
    VerifyCodeRequest,
)
from app.services.email_sender import EmailSender, get_email_sender

router = APIRouter(prefix="/api/v1", tags=["auth"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.post("/auth/company/send-code", response_model=MessageResponse)
def send_company_code(
    payload: SendCodeRequest,
    db: Session = Depends(get_db),
    email_sender: EmailSender = Depends(get_email_sender),
):
    email = normalize_email(str(payload.email))
    if not is_allowed_corporate_email(email):
        raise AppError(403, "CORPORATE_EMAIL_REQUIRED", "Only corporate email addresses are allowed.")

    now = _utcnow()

    # Mark any previous unused codes for this email as consumed
    old_codes = db.execute(
        select(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.consumed_at.is_(None),
        )
    ).scalars().all()
    for row in old_codes:
        row.consumed_at = now

    raw_code = generate_otp_code()
    verification = VerificationCode(
        email=email,
        code=raw_code,
        expires_at=now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )
    db.add(verification)
    db.commit()

    email_sender.send_otp(email=email, code=raw_code, expires_minutes=settings.OTP_EXPIRE_MINUTES)
    return MessageResponse(message="Verification code sent successfully")


@router.post("/auth/company/verify", response_model=AuthTokenResponse)
def verify_company_code(
    payload: VerifyCodeRequest,
    db: Session = Depends(get_db),
):
    email = normalize_email(str(payload.email))
    now = _utcnow()

    verification = db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.consumed_at.is_(None),
        )
        .order_by(desc(VerificationCode.created_at))
        .limit(1)
    ).scalar_one_or_none()

    if (
        verification is None
        or _as_utc(verification.expires_at) <= now
        or verification.code != payload.code
    ):
        raise AppError(401, "INVALID_OR_EXPIRED_CODE", "Verification code is invalid or has expired.")

    verification.consumed_at = now

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email, name=None)
        db.add(user)

    db.commit()
    db.refresh(user)

    access_token, expires_in = create_access_token(user.id)
    return AuthTokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserProfile.model_validate(user),
    )


@router.get("/users/me", response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)):
    return UserProfile.model_validate(current_user)


@router.patch("/users/me", response_model=UserProfile)
def update_me(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.name = payload.name.strip()
    db.commit()
    db.refresh(current_user)
    return UserProfile.model_validate(current_user)
