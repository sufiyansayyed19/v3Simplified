# Milestone 5 (m5) — Iteration 01: Payment Service (3 APIs) & Parking Internal Callback

## Goal
Implement **Payment Service** (`services/payment-service/`, port `8004`, DB `payment_db`) and **Parking Service's internal payment callback** (`POST /internal/v1/bookings/{booking_id}/payment-result`).

## What Was Built

### 1. Payment Service (`services/payment-service/`)
- `app/models/payment.py` — `Payment` (`payments` table): `id`, `booking_id` (unique), `user_id`, `amount`, `payment_method` (`UPI`/`CARD`/`WALLET`), `status` (`PENDING`/`SUCCESS`/`FAILED`), `transaction_id`, `expires_at`, `created_at`.
- `app/services/parking_callback.py` — Calls `POST /internal/v1/bookings/{booking_id}/payment-result` with `X-Internal-Service-Token`.
- `app/api/v1/payments.py` — 3 endpoints:
  1. `POST /internal/v1/payments` — Called by Parking Service to create a `PENDING` payment for a booking.
  2. `POST /api/v1/payments/{payment_id}/process` — Processes simulated payment (`UPI`/`CARD`/`WALLET`), stores `SUCCESS` + `TXN...` (or `FAILED`), and notifies Parking Service.
  3. `GET /api/v1/payments/{payment_id}` — Owner-scoped payment retrieval.

### 2. Parking Service Internal Endpoint (`services/parking-service/app/api/internal.py`)
- `POST /internal/v1/bookings/{booking_id}/payment-result` — Verifies `X-Internal-Service-Token`, checks `payment_id` and hold expiry, and transitions `PAYMENT_PENDING` → `CONFIRMED` (or `EXPIRED`).
