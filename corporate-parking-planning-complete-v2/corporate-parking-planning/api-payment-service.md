# Payment Service API Contract

**Service Path:** `services/payment-service/` | **Port:** `8004` | **Database:** `payment_db` (`payments`)

---

## 1. Responsibilities
Payment Service owns payment records (`payments`) and simulates payment processing (`UPI`, `CARD`, `WALLET`). After persisting a payment result (`SUCCESS` or `FAILED`), it notifies `Parking Service` via `POST /internal/v1/bookings/{booking_id}/payment-result`.

---

## 2. Endpoint Inventory (3 Endpoints: 1 Internal + 2 Public)

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `POST` | `/internal/v1/payments` | `X-Internal-Service-Token` | Called by Parking Service to create a `PENDING` payment |
| `POST` | `/api/v1/payments/{payment_id}/process` | Bearer JWT | Process simulated payment (`UPI`, `CARD`, `WALLET`) |
| `GET` | `/api/v1/payments/{payment_id}` | Bearer JWT | Retrieve payment details for the authenticated owner |

---

## 3. Internal `POST /internal/v1/payments`

### Request
```json
{
  "booking_id": "<booking-uuid>",
  "user_id": "<user-uuid>",
  "amount": 40.00,
  "expires_at": "2026-11-24T10:05:00+05:30"
}
```
Creates a `PENDING` payment (or replays idempotently if `booking_id` already exists with matching `user_id` and `amount`).

---

## 4. `POST /api/v1/payments/{payment_id}/process`

### Request
```json
{
  "payment_method": "UPI"
}
```

### Processing
1. Verifies ownership (`payment.user_id == current_user_id`), `status == "PENDING"`, and `now < expires_at`.
2. Resolves simulated outcome (`SUCCESS` by default, or `FAILED` if `X-Test-Payment-Outcome: FAILED` header is passed in non-production).
3. Saves `payment_method`, `status`, and `transaction_id` (`TXN...`) to `payment_db`.
4. Calls `Parking Service` (`POST /internal/v1/bookings/{booking_id}/payment-result`) with `X-Internal-Service-Token`.
5. Returns `{ "payment_id", "booking_id", "amount", "status", "transaction_id" }` (`200 OK`).

---

## 5. `GET /api/v1/payments/{payment_id}`
Returns the owner's payment record (`200 OK`) or `404 PAYMENT_NOT_FOUND`.
