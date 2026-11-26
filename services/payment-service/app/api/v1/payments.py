from datetime import datetime, timezone
from decimal import Decimal
import logging
import uuid

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_current_user_id, require_parking_service_token
from app.models.payment import Payment
from app.schemas.payment import (
    InternalPaymentCreateRequest,
    InternalPaymentCreateResponse,
    PaymentDetailResponse,
    PaymentProcessRequest,
    PaymentProcessResponse,
)
from app.services.parking_callback import ParkingCallbackClient, get_callback_client

router = APIRouter()
logger = logging.getLogger(__name__)


def get_now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _resolve_simulated_outcome(test_override: str | None) -> str:
    if (
        test_override is not None
        and settings.ENABLE_TEST_PAYMENT_OVERRIDE
        and settings.ENVIRONMENT.strip().lower() != "production"
    ):
        upper = test_override.strip().upper()
        if upper in ("SUCCESS", "FAILED"):
            return upper

    default_outcome = settings.PAYMENT_SIMULATION_DEFAULT_OUTCOME.strip().upper()
    return "FAILED" if default_outcome == "FAILED" else "SUCCESS"


@router.post(
    "/internal/v1/payments",
    response_model=InternalPaymentCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["internal"],
    dependencies=[Depends(require_parking_service_token)],
)
def create_internal_payment(
    payload: InternalPaymentCreateRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    req_expires_utc = _as_utc(payload.expires_at)

    existing = db.execute(
        select(Payment).where(Payment.booking_id == payload.booking_id)
    ).scalar_one_or_none()

    if existing is not None:
        same_user = existing.user_id == payload.user_id
        same_amount = Decimal(existing.amount) == Decimal(payload.amount)
        if not (same_user and same_amount):
            logger.warning("Payment conflict for booking_id=%s", payload.booking_id)
            raise AppError(
                409,
                "PAYMENT_REQUEST_CONFLICT",
                "A payment for this booking already exists with different values.",
            )
        response.status_code = status.HTTP_200_OK
        return InternalPaymentCreateResponse(
            payment_id=existing.id,
            booking_id=existing.booking_id,
            amount=existing.amount,
            status=existing.status,
            expires_at=existing.expires_at,
        )

    payment = Payment(
        booking_id=payload.booking_id,
        user_id=payload.user_id,
        amount=payload.amount,
        status="PENDING",
        expires_at=req_expires_utc,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    logger.info("Created pending payment_id=%s for booking_id=%s (amount=%s)", payment.id, payment.booking_id, payment.amount)

    return InternalPaymentCreateResponse(
        payment_id=payment.id,
        booking_id=payment.booking_id,
        amount=payment.amount,
        status=payment.status,
        expires_at=payment.expires_at,
    )


@router.post(
    "/api/v1/payments/{payment_id}/process",
    response_model=PaymentProcessResponse,
    tags=["payments"],
)
def process_payment(
    payment_id: uuid.UUID,
    payload: PaymentProcessRequest,
    test_outcome_header: str | None = Header(default=None, alias="X-Test-Payment-Outcome"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    now_utc: datetime = Depends(get_now_utc),
    db: Session = Depends(get_db),
    callback_client: ParkingCallbackClient = Depends(get_callback_client),
):
    logger.info("Processing payment_id=%s via method=%s for user_id=%s", payment_id, payload.payment_method, user_id)
    payment = db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.user_id == user_id)
    ).scalar_one_or_none()
    if payment is None:
        logger.warning("Payment not found: payment_id=%s", payment_id)
        raise AppError(404, "PAYMENT_NOT_FOUND", "Payment not found.")

    if payment.status != "PENDING":
        logger.warning("Payment already processed: payment_id=%s (status=%s)", payment_id, payment.status)
        raise AppError(409, "PAYMENT_ALREADY_PROCESSED", "Payment has already been processed.")

    if _as_utc(now_utc) >= _as_utc(payment.expires_at):
        logger.warning("Payment window expired for payment_id=%s", payment_id)
        raise AppError(409, "PAYMENT_EXPIRED", "Payment window has expired.")

    outcome = _resolve_simulated_outcome(test_outcome_header)
    txn_id = f"TXN{uuid.uuid4().hex[:10].upper()}" if outcome == "SUCCESS" else None

    payment.payment_method = payload.payment_method
    payment.status = outcome
    payment.transaction_id = txn_id
    db.commit()
    db.refresh(payment)
    logger.info("Payment %s finished with status=%s (txn_id=%s)", payment.id, payment.status, payment.transaction_id)

    callback_client.deliver_payment_result(
        booking_id=payment.booking_id,
        payment_id=payment.id,
        status=payment.status,
        transaction_id=payment.transaction_id,
        processed_at=_as_utc(now_utc),
    )

    return PaymentProcessResponse(
        payment_id=payment.id,
        booking_id=payment.booking_id,
        amount=payment.amount,
        status=payment.status,
        transaction_id=payment.transaction_id,
    )


@router.get(
    "/api/v1/payments/{payment_id}",
    response_model=PaymentDetailResponse,
    tags=["payments"],
)
def get_payment(
    payment_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    payment = db.execute(
        select(Payment).where(Payment.id == payment_id, Payment.user_id == user_id)
    ).scalar_one_or_none()
    if payment is None:
        raise AppError(404, "PAYMENT_NOT_FOUND", "Payment not found.")

    return PaymentDetailResponse(
        payment_id=payment.id,
        booking_id=payment.booking_id,
        amount=payment.amount,
        payment_method=payment.payment_method,
        status=payment.status,
        transaction_id=payment.transaction_id,
        expires_at=payment.expires_at,
        created_at=payment.created_at,
    )
