# Feature-to-Code Implementation Map

A quick-reference map linking every **technical feature** in `ParkingSimplified` to the exact **file(s)**, **class(es)**, and **function(s)** that implement it.

---

## 1. Microservices & Architecture

| Feature | Where It Is Implemented | Key Classes / Functions |
|---|---|---|
| **Database-per-Service Isolation** (`user_db`, `vehicle_db`, `parking_db`, `payment_db`) | `scripts/init_postgres.sql`, each service's `app/core/config.py` & `app/core/database.py` | `CREATE ROLE`, `CREATE DATABASE`, `REVOKE CONNECT ... FROM PUBLIC`, `Settings.DATABASE_URL`, `create_engine` |
| **Inter-Service Call: Parking → Vehicle** (`GET /api/v1/vehicles/{id}`) | `services/parking-service/app/services/clients.py`, `services/parking-service/app/api/v1/parking.py` | `VehicleServiceClient.get_owned_vehicle()`, `get_vehicle_client()`, called inside `check_availability()` & `create_booking()` |
| **Inter-Service Call: Parking → Payment** (`POST /internal/v1/payments`) | `services/parking-service/app/services/clients.py`, `services/payment-service/app/api/v1/payments.py` | `PaymentServiceClient.create_payment()`, `get_payment_client()`, `create_internal_payment()` |
| **Inter-Service Callback: Payment → Parking** (`POST /internal/v1/bookings/{id}/payment-result`) | `services/payment-service/app/services/parking_callback.py`, `services/parking-service/app/api/internal.py` | `ParkingCallbackClient.deliver_payment_result()`, `get_callback_client()`, `apply_payment_result()` |
| **OpenAPI / Swagger UI (`/docs`) & Health Checks** | Each service's `app/main.py` | `FastAPI(...)`, `health_check()` (`GET /health`) |
| **Multi-Service Local Launcher** | `scripts/start_all.ps1`, `scripts/start_all.sh` | Launches `uvicorn app.main:app` on ports `8001`–`8004` |

---

## 2. Authentication & Security

| Feature | Where It Is Implemented | Key Classes / Functions |
|---|---|---|
| **Stateless HS256 JWT Signing** | `services/user-auth-service/app/core/security.py`, `app/api/v1/auth.py` | `create_access_token()`, called by `verify_company_code()` |
| **Stateless HS256 JWT Verification (`Depends`)** | `app/core/security.py` in all 4 services | `decode_access_token()`, `get_current_user()` (Auth), `get_current_user_id()` (Vehicle/Payment), `get_auth_context()` (Parking) |
| **Corporate Email Domain Validation** | `services/user-auth-service/app/core/security.py`, `app/api/v1/auth.py` | `normalize_email()`, `is_allowed_corporate_email()`, `send_company_code()` |
| **CSPRNG 6-Digit OTP Generation & Single-Use Consumption** | `services/user-auth-service/app/core/security.py`, `app/api/v1/auth.py`, `app/models/auth.py` | `generate_otp_code()`, `VerificationCode`, `send_company_code()`, `verify_company_code()` |
| **Pluggable OTP Email Sender (Prod-Safe)** | `services/user-auth-service/app/services/email_sender.py` | `EmailSender`, `ConsoleEmailSender.send_otp()`, `get_email_sender()` |
| **Internal Service Token Auth (`X-Internal-Service-Token`)** | `services/parking-service/app/api/internal.py`, `services/payment-service/app/core/security.py` | `_require_internal_token()` (Parking), `require_parking_service_token()` (Payment) |
| **Owner-Scoped Isolation (Non-Disclosing `404`)** | `vehicles.py`, `parking.py`, `payments.py` | `_get_owned_active_vehicle()`, `list_vehicles()`, `list_bookings()`, `get_booking()`, `cancel_booking()`, `process_payment()`, `get_payment()` |

---

## 3. Database, ORM & Migrations

| Feature | Where It Is Implemented | Key Classes / Functions |
|---|---|---|
| **Synchronous SQLAlchemy 2.0 + `psycopg` v3 + Request-Scoped Sessions** | `app/core/database.py` in all 4 services | `engine`, `SessionLocal`, `Base`, `get_db()` |
| **UUID Primary Keys (`uuid.uuid4`)** | `app/models/*.py` across all 4 services | `User`, `VerificationCode`, `Vehicle`, `ParkingSlot`, `Booking`, `Payment` |
| **Same-Database SQL Foreign Key (`bookings.slot_id → parking_slots.id`)** | `services/parking-service/app/models/parking.py` | `Booking.slot_id` (`ForeignKey("parking_slots.id")`), `ParkingSlot.bookings`, `Booking.slot` |
| **Immutable Cross-Service Vehicle Snapshots** | `services/parking-service/app/models/parking.py`, `app/api/v1/parking.py` | `Booking.vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot` populated in `create_booking()` |
| **Automatic Startup Table Creation & 100-Slot Seeding** | `app/main.py` in all 4 services, `services/parking-service/app/models/parking.py` | `lifespan()`, `Base.metadata.create_all(bind=engine)`, `seed_default_slots()` |
| **Alembic Schema Migrations (`parking_db`)** | `services/parking-service/alembic/env.py`, `alembic/versions/0001_create_parking_tables.py` | `run_migrations_online()`, `upgrade()`, `downgrade()` |

---

## 4. Concurrency, State Management & Business Rules

| Feature | Where It Is Implemented | Key Classes / Functions |
|---|---|---|
| **Pessimistic Row Locking (`SELECT ... FOR UPDATE`)** | `services/parking-service/app/api/v1/parking.py` | `create_booking()` using `select(ParkingSlot)...with_for_update()` |
| **Half-Open Interval Overlap Detection** (`new_start < existing_end AND new_end > existing_start`) | `services/parking-service/app/api/v1/parking.py` | `check_availability()`, `create_booking()` (checks both user overlap & slot overlap) |
| **Lazy 5-Minute Hold Expiry (No Background Workers)** | `services/parking-service/app/api/v1/parking.py` | `_active_booking_filter()`, `_expire_stale_holds()`, called in `list_bookings()`, `get_booking()`, `cancel_booking()` |
| **Booking State Machine & No-Resurrection Rule** (`PAYMENT_PENDING → CONFIRMED \| EXPIRED`, `CONFIRMED → CANCELLED`) | `services/parking-service/app/api/internal.py`, `app/api/v1/parking.py` | `apply_payment_result()`, `cancel_booking()` |
| **Operating Hours, Whole-Hour, Sunday Closure & Future-Start Rules** | `services/parking-service/app/services/rules.py` | `validate_booking_interval()`, `can_cancel_booking()` |
| **EV Charging Compatibility & Dynamic Hourly Pricing** (`₹10/hr` vs `₹20/hr`) | `services/parking-service/app/services/rules.py` | `validate_charging_compatibility()`, `calculate_hourly_rate()`, `calculate_booking_amount()` |
| **Soft Deletion & Re-Registration** | `services/vehicle-service/app/api/v1/vehicles.py` | `deactivate_vehicle()` (`is_active = False`), `create_vehicle()` |
| **Idempotent Payment Creation** (`UNIQUE(booking_id)`) | `services/payment-service/app/models/payment.py`, `app/api/v1/payments.py` | `Payment.booking_id` (`unique=True`), `create_internal_payment()` |
| **Deterministic Simulated Payment Processing** (`UPI`, `CARD`, `WALLET`) | `services/payment-service/app/api/v1/payments.py` | `_resolve_simulated_outcome()`, `process_payment()` |

---

## 5. Validation, Error Handling & Testing

| Feature | Where It Is Implemented | Key Classes / Functions |
|---|---|---|
| **Pydantic v2 Validation & Plate Normalization** (`"mh 12-ab 1234"` → `"MH12AB1234"`) | `app/schemas/*.py` in all 4 services | `normalize_vehicle_number()`, `VehicleCreate.validate_plate()`, `VehicleUpdate.validate_plate()`, `BookingCreateRequest`, `PaymentProcessRequest` |
| **Standardized Global Error Envelope** (`{"error": {"code", "message", "request_id"}}`) | `app/core/errors.py` in all 4 services | `AppError`, `_request_id()`, `register_exception_handlers()` |
| **Booking History Pagination** | `services/parking-service/app/api/v1/parking.py`, `app/schemas/parking.py` | `list_bookings()`, `BookingListResponse` |
| **Controllable Business Timezone Clock (`Asia/Kolkata`)** | `services/parking-service/app/core/clock.py`, `services/payment-service/app/api/v1/payments.py` | `get_business_tz()`, `get_now()`, `as_utc()`, `get_now_utc()` |
| **Isolated Unit Tests (In-Memory SQLite + Dependency Overrides)** | `services/*/tests/test_*.py` | `ctx()`, `test_auth.py`, `test_vehicles.py`, `test_parking.py`, `test_internal.py`, `test_payments.py` |
| **Real PostgreSQL Multithreaded Concurrency Tests** | `tests/test_pg_concurrency.py` | `test_pg_ev_bike_slot_race_no_double_allocation()`, `test_pg_same_user_simultaneous_overlap_serialized()` |
| **Live 4-Service End-to-End Integration Test** | `tests/test_e2e_journey.py`, `scripts/run_all_tests.ps1` | `live_stack()`, `test_full_e2e_corporate_parking_journey()` |
