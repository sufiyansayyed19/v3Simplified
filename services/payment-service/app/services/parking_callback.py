from datetime import datetime, timezone
import uuid

import httpx

from app.core.config import settings


class ParkingCallbackClient:
    """Notifies Parking Service when a payment is processed."""

    def deliver_payment_result(
        self,
        booking_id: uuid.UUID,
        payment_id: uuid.UUID,
        status: str,
        transaction_id: str | None,
        processed_at: datetime,
        request_id: str | None = None,
    ) -> bool:
        url = f"{settings.PARKING_SERVICE_URL.rstrip('/')}/internal/v1/bookings/{booking_id}/payment-result"
        headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
        payload = {
            "payment_id": str(payment_id),
            "status": status,
            "transaction_id": transaction_id,
            "processed_at": processed_at.astimezone(timezone.utc).isoformat(),
        }

        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.post(url, json=payload, headers=headers)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False


def get_callback_client() -> ParkingCallbackClient:
    return ParkingCallbackClient()
