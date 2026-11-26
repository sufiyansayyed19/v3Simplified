from datetime import datetime
import logging
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import as_utc, get_now
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.models.parking import Booking

router = APIRouter(prefix="/internal/v1", tags=["internal"])
logger = logging.getLogger(__name__)


def _require_internal_token(
    token: str | None = Header(default=None, alias="X-Internal-Service-Token"),
) -> None:
    if not token or token != settings.INTERNAL_SERVICE_TOKEN:
        logger.warning("Unauthorized internal service callback attempt.")
        raise AppError(401, "INTERNAL_CALLER_UNAUTHORIZED", "Invalid internal service token.")


class PaymentResultRequest(BaseModel):
    payment_id: uuid.UUID
    status: Literal["SUCCESS", "FAILED"]
    transaction_id: str | None = None
    processed_at: datetime


class PaymentResultResponse(BaseModel):
    booking_id: uuid.UUID
    status: str
    result: str


@router.post(
    "/bookings/{booking_id}/payment-result",
    response_model=PaymentResultResponse,
    dependencies=[Depends(_require_internal_token)],
)
def apply_payment_result(
    booking_id: uuid.UUID,
    payload: PaymentResultRequest,
    now: datetime = Depends(get_now),
    db: Session = Depends(get_db),
):
    logger.info("Received payment callback for booking_id=%s with status=%s", booking_id, payload.status)
    booking = db.execute(select(Booking).where(Booking.id == booking_id)).scalar_one_or_none()
    if booking is None:
        logger.warning("Booking not found for payment callback: booking_id=%s", booking_id)
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found.")

    if booking.payment_id is not None and booking.payment_id != payload.payment_id:
        logger.warning("Payment reference mismatch for booking_id=%s", booking_id)
        raise AppError(409, "PAYMENT_REFERENCE_MISMATCH", "Callback payment_id does not match booking.")

    now_utc = as_utc(now)

    if booking.status == "CONFIRMED":
        return PaymentResultResponse(booking_id=booking.id, status="CONFIRMED", result="ALREADY_APPLIED")

    if booking.status == "EXPIRED":
        return PaymentResultResponse(booking_id=booking.id, status="EXPIRED", result="EXPIRED_NO_RESURRECTION")

    if booking.status == "CANCELLED":
        raise AppError(409, "INVALID_BOOKING_TRANSITION", "Cannot apply payment callback to a CANCELLED booking.")

    if booking.payment_id is None:
        booking.payment_id = payload.payment_id

    hold_expired = booking.hold_expires_at is None or as_utc(booking.hold_expires_at) <= now_utc
    if hold_expired or payload.status == "FAILED":
        booking.status = "EXPIRED"
    else:
        booking.status = "CONFIRMED"

    db.commit()
    db.refresh(booking)
    logger.info("Booking %s updated to status=%s after payment callback", booking.id, booking.status)
    return PaymentResultResponse(booking_id=booking.id, status=booking.status, result="APPLIED")
