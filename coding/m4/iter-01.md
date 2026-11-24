# Milestone 4 (m4) — Iteration 01: Parking Service Core (5 Public APIs + 100-Slot Seed)

## Goal
Implement the core **Parking Service** (`services/parking-service/`, port `8003`, DB `parking_db`) with its 2 tables (`parking_slots`, `bookings`), Alembic migration + automatic 100-slot startup seeding (`C01–C60`, `B01–B40`), simplified time & pricing rules, `SELECT ... FOR UPDATE` slot locking, vehicle snapshots, lazy hold expiry, and all 5 public APIs.

## What Was Built

### 1. ORM Models, Alembic & Auto-Seeder
- `app/models/parking.py` — 2 SQLAlchemy models:
  - `parking_slots` (`id`, `slot_number` unique, `vehicle_type`, `is_charging_enabled`).
  - `bookings` (`id`, `user_id`, `vehicle_id`, `vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`, `slot_id` ForeignKey to `parking_slots.id`, `booking_date`, `start_time`, `end_time`, `requires_charging`, `status`, `amount`, `hold_expires_at`, `payment_id`, `created_at`, `cancelled_at`).
  - `seed_default_slots(db)` — Automatically seeds the 100 slots on startup if `parking_slots` is empty.
- `alembic/versions/0001_create_parking_tables.py` — Alembic migration creating `parking_slots` and `bookings`.

### 2. Business Rules & Downstream Clients
- `app/services/rules.py` — Enforces today/tomorrow horizon, Sunday closure, `07:00–22:00` whole-hour slots, max 12h duration, future `start_time > now`, EV charging compatibility, `₹10/hr` vs `₹20/hr` pricing, and cancellation before `start_time`.
- `app/services/clients.py` — `VehicleServiceClient` (forwards user Bearer JWT) and `PaymentServiceClient` (passes `X-Internal-Service-Token`).

### 3. All 5 Public API Endpoints (`app/api/v1/parking.py`)
1. `GET /api/v1/parking/availability` — Compatible free slot count & hourly rate.
2. `POST /api/v1/parking/bookings` — Locks compatible slots with `.with_for_update()`, checks user & slot overlap, saves 5-min `PAYMENT_PENDING` hold + vehicle snapshots, calls Payment Service, and saves `payment_id`.
3. `GET /api/v1/parking/bookings` — Paginated booking history with lazy hold expiry.
4. `GET /api/v1/parking/bookings/{booking_id}` — Owner-scoped booking detail with lazy hold expiry.
5. `POST /api/v1/parking/bookings/{booking_id}/cancel` — Cancels a `CONFIRMED` booking before `start_time`.
