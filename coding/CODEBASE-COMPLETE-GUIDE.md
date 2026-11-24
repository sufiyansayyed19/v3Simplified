# Complete Codebase Directory & Function Handbook

A top-to-bottom reference of **every root directory, subdirectory, file, class, and function** in `ParkingSimplified`, explaining **why it exists**, **what it does**, and for every function: **Inputs → Work → Output**.

> **Note:** Auto-generated Python cache folders (`__pycache__/`, `.pytest_cache/`) and the virtual environment (`.venv/`) are intentionally excluded from this guide.

---

## 0. Clean Project Directory Tree

```text
ParkingSimplified/
├── .gitignore
├── requirements.txt
├── coding/
│   ├── API-FLOWS.md
│   ├── API-TESTING-GUIDE.md
│   ├── CODEBASE-COMPLETE-GUIDE.md
│   ├── DEPENDENCIES.md
│   ├── PROGRESS.md
│   ├── RUNNING-COMMANDS.md
│   ├── WHY-WE-USE-EACH-TOOL.md
│   └── m0/ .. m7/ (iter-01.md, iter-02.md)
├── corporate-parking-planning-complete-v2/
│   └── corporate-parking-planning/ (13 planning .md files)
├── scripts/
│   ├── init_postgres.sql
│   ├── run_all_tests.ps1 / .sh
│   └── start_all.ps1 / .sh
├── services/
│   ├── user-auth-service/
│   │   ├── .env / .env.example / requirements.txt
│   │   ├── app/ (main.py, core/, models/, schemas/, services/, api/v1/)
│   │   └── tests/test_auth.py
│   ├── vehicle-service/
│   │   ├── .env.example / requirements.txt
│   │   ├── app/ (main.py, core/, models/, schemas/, services/, api/v1/)
│   │   └── tests/test_vehicles.py
│   ├── parking-service/
│   │   ├── .env.example / requirements.txt / alembic.ini
│   │   ├── alembic/ (env.py, script.py.mako, versions/0001_create_parking_tables.py)
│   │   ├── app/ (main.py, core/, models/, schemas/, services/, api/internal.py, api/v1/)
│   │   └── tests/ (test_parking.py, test_internal.py)
│   └── payment-service/
│       ├── .env.example / requirements.txt
│       ├── app/ (main.py, core/, models/, schemas/, services/, api/v1/)
│       └── tests/test_payments.py
└── tests/
    ├── test_e2e_journey.py
    └── test_pg_concurrency.py
```

---

## 1. Root Directory Files (`ParkingSimplified/`)

### `.gitignore`
- **Why it exists:** Prevents secrets (`.env`), Python virtual environments (`.venv/`, `venv/`), auto-generated caches (`__pycache__/`, `*.py[cod]`, `.pytest_cache/`), and key files (`*.pem`, `*.key`) from being tracked by Git.

### `requirements.txt`
- **Why it exists:** Single root dependency list for local development (`fastapi`, `uvicorn[standard]`, `sqlalchemy`, `psycopg[binary]`, `alembic`, `pydantic`, `pydantic-settings`, `email-validator`, `httpx`, `PyJWT`, `pytest`).

---

## 2. `scripts/` — Database Setup, Service Startup & Test Runner

### `scripts/init_postgres.sql`
- **Why it exists:** Run once as PostgreSQL `postgres` superuser to create the 4 isolated DB roles (`user_auth_user`, `vehicle_user`, `parking_user`, `payment_user`) and 4 isolated databases (`user_db`, `vehicle_db`, `parking_db`, `payment_db`), revoking `PUBLIC` connect rights so services cannot access each other's databases.

### `scripts/start_all.ps1` & `scripts/start_all.sh`
- **Why they exist:** Launch all 4 Uvicorn servers (`:8001`–`:8004`) in parallel using `.venv` Python and print each service's Swagger `/docs` URL.

### `scripts/run_all_tests.ps1` & `scripts/run_all_tests.sh`
- **Why they exist:** Run all 7 `pytest` test files sequentially and exit with status `1` if any test suite fails.

---

## 3. `services/user-auth-service/` — User & Authentication Service (Port `8001`, `user_db`)

Owns `users` and `verification_codes`. Handles corporate email OTP login and HS256 JWT generation.

### Service Root Files
- `.env` / `.env.example` — Environment configuration (`DATABASE_URL`, `COMPANY_EMAIL_DOMAIN`, `JWT_SECRET_KEY`, `OTP_EXPIRE_MINUTES`).
- `requirements.txt` — Service dependencies (`fastapi`, `uvicorn[standard]`, `sqlalchemy`, `psycopg[binary]`, `pydantic`, `pydantic-settings`, `email-validator`, `PyJWT`).

### `app/main.py`
- **`lifespan(app_instance: FastAPI)`**
  - *Inputs:* `app_instance: FastAPI` (managed by FastAPI startup/shutdown).
  - *Work:* If `get_db` is not overridden by tests, calls `Base.metadata.create_all(bind=engine)` to create `users` and `verification_codes` in `user_db`.
  - *Output:* Async generator yielding while the app runs.
- **`health_check()`** (`GET /health`)
  - *Inputs:* None.
  - *Work:* Returns service health status.
  - *Output:* `{"status": "ok", "service": "user-auth-service"}`.

### `app/core/` (Configuration, DB, Errors, Security)
- `app/core/config.py`
  - **`Settings(BaseSettings)`** — Loads `.env` into typed attributes (`SERVICE_NAME`, `HOST`, `PORT`, `DATABASE_URL`, `COMPANY_EMAIL_DOMAIN`, `OTP_EXPIRE_MINUTES`, `EMAIL_SENDER_MODE`, `ENVIRONMENT`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`).
- `app/core/database.py`
  - **`get_db() -> Generator[Session, None, None]`**
    - *Inputs:* None (injected via `Depends(get_db)`).
    - *Work:* Creates a `SessionLocal()` DB session, yields it to the endpoint, and always closes it in `finally`.
    - *Output:* Yields `sqlalchemy.orm.Session`.
- `app/core/errors.py`
  - **`AppError.__init__(status_code, code, message)`** — Stores HTTP status, machine-readable error code, and human-readable message.
  - **`_request_id(request: Request) -> str`**
    - *Inputs:* FastAPI `Request`.
    - *Work:* Reads `request.state.request_id` or generates a fallback UUID.
    - *Output:* Request ID string.
  - **`register_exception_handlers(app: FastAPI) -> None`**
    - *Inputs:* `app: FastAPI`.
    - *Work:* Registers 4 async handlers (`app_error_handler`, `validation_error_handler`, `http_exception_handler`, `unhandled_exception_handler`) returning standardized JSON `{"error": {"code", "message", "request_id"}}`.
    - *Output:* `None`.
- `app/core/security.py`
  - **`normalize_email(email: str) -> str`**
    - *Inputs:* Raw email string.
    - *Work:* Trims whitespace and converts to lowercase.
    - *Output:* Normalized email string.
  - **`is_allowed_corporate_email(normalized_email: str) -> bool`**
    - *Inputs:* Lowercased email string.
    - *Work:* Extracts domain after `@` and compares it to `settings.COMPANY_EMAIL_DOMAIN`.
    - *Output:* `True` if domain matches, else `False`.
  - **`generate_otp_code() -> str`**
    - *Inputs:* None.
    - *Work:* Uses `secrets.randbelow(1_000_000)` to generate a random 6-digit code.
    - *Output:* 6-character zero-padded string (e.g. `"042819"`).
  - **`create_access_token(user_id: uuid.UUID) -> tuple[str, int]`**
    - *Inputs:* `user_id` (`UUID`).
    - *Work:* Encodes `{"sub": str(user_id), "iat": ..., "exp": ...}` using `settings.JWT_SECRET_KEY` and `HS256`.
    - *Output:* `(jwt_token_str, expires_in_seconds)`.
  - **`decode_access_token(token: str) -> uuid.UUID`**
    - *Inputs:* JWT string.
    - *Work:* Decodes and verifies signature/expiry; raises `AppError(401, "UNAUTHENTICATED", ...)` if invalid or expired.
    - *Output:* `uuid.UUID` from `sub`.
  - **`get_current_user(credentials, db) -> User`**
    - *Inputs:* Bearer credentials (`HTTPBearer`) and `db: Session`.
    - *Work:* Extracts and decodes token, queries `User` by `user_id`, raises `401` if missing/not found.
    - *Output:* `User` ORM instance.

### `app/models/`
- `app/models/__init__.py` — Re-exports `User` and `VerificationCode`.
- `app/models/auth.py`
  - **`utcnow() -> datetime`** — Returns `datetime.now(timezone.utc)`.
  - **`User(Base)`** — ORM table `users` (`id`, `email`, `name`, `created_at`, `updated_at`).
  - **`VerificationCode(Base)`** — ORM table `verification_codes` (`id`, `email`, `code` [mapped to DB column `code_hash`], `expires_at`, `attempt_count`, `consumed_at`, `created_at`).

### `app/schemas/`
- `app/schemas/auth.py` — Pydantic models: `SendCodeRequest`, `VerifyCodeRequest`, `MessageResponse`, `UserProfile`, `AuthTokenResponse`.

### `app/services/`
- `app/services/email_sender.py`
  - **`EmailSender.send_otp(email, code, expires_minutes)`** — Abstract base method.
  - **`ConsoleEmailSender.send_otp(email, code, expires_minutes) -> None`**
    - *Inputs:* `email: str`, `code: str`, `expires_minutes: int`.
    - *Work:* Raises `RuntimeError` if `ENVIRONMENT == "production"`; otherwise prints `[DEV EMAIL OTP] To: ... | Code: ...` to stdout.
    - *Output:* `None`.
  - **`get_email_sender() -> EmailSender`**
    - *Inputs:* None (FastAPI dependency).
    - *Work:* Checks `settings.EMAIL_SENDER_MODE` and instantiates `ConsoleEmailSender()`.
    - *Output:* `EmailSender` instance.

### `app/api/v1/auth.py`
- **`_utcnow() -> datetime`** — Returns current UTC `datetime`.
- **`_as_utc(dt: datetime) -> datetime`**
  - *Inputs:* `datetime` (naive or aware).
  - *Work:* Attaches `timezone.utc` if naive (SQLite compatibility).
  - *Output:* Timezone-aware UTC `datetime`.
- **`send_company_code(payload: SendCodeRequest, db, email_sender) -> MessageResponse`** (`POST /api/v1/auth/company/send-code`)
  - *Inputs:* `SendCodeRequest` (`email`), `db`, `email_sender`.
  - *Work:* Normalizes email, rejects non-corporate domain (`403`), marks any prior unconsumed OTPs as consumed, creates a new `VerificationCode` (5-min expiry), commits, and calls `email_sender.send_otp(...)`.
  - *Output:* `MessageResponse("Verification code sent successfully")`.
- **`verify_company_code(payload: VerifyCodeRequest, db) -> AuthTokenResponse`** (`POST /api/v1/auth/company/verify`)
  - *Inputs:* `VerifyCodeRequest` (`email`, `code`), `db`.
  - *Work:* Queries latest unconsumed OTP, rejects if missing/expired/wrong code (`401`), marks `consumed_at`, finds or creates `User`, commits, and generates HS256 JWT.
  - *Output:* `AuthTokenResponse` (`access_token`, `token_type="bearer"`, `expires_in`, `user`).
- **`get_me(current_user: User) -> UserProfile`** (`GET /api/v1/users/me`)
  - *Inputs:* `current_user` (from `Depends(get_current_user)`).
  - *Work:* Converts ORM `User` to `UserProfile`.
  - *Output:* `UserProfile`.

### `tests/test_auth.py`
- **`CapturingEmailSender.send_otp(...)`** — Stores `(email, code)` in `self.sent` list for assertions.
- **`ctx()`** — Creates in-memory SQLite tables and overrides `get_db` and `get_email_sender`.
- **`test_health(ctx)`** — Verifies `GET /health` returns `200`.
- **`test_reject_non_corporate_email(ctx)`** — Verifies `@gmail.com` returns `403 CORPORATE_EMAIL_REQUIRED`.
- **`test_company_otp_login_and_me_flow(ctx)`** — Tests send-code, wrong OTP `401`, valid OTP `200` + JWT, replay `401`, and `/users/me` `200`.

---

## 4. `services/vehicle-service/` — Vehicle Management Service (Port `8002`, `vehicle_db`)

Standalone CRUD service owning `vehicles`.

### Service Root Files
- `.env.example` — Template for `DATABASE_URL` and `JWT_SECRET_KEY`.
- `requirements.txt` — `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `psycopg[binary]`, `pydantic`, `pydantic-settings`, `PyJWT`.

### `app/main.py`
- **`lifespan(app_instance: FastAPI)`** — Creates `vehicles` table via `Base.metadata.create_all(bind=engine)` on startup unless `get_db` is overridden.
- **`health_check()`** (`GET /health`) — Returns `{"status": "ok", "service": "vehicle-service"}`.

### `app/core/`
- `app/core/config.py` — `Settings` (`SERVICE_NAME`, `HOST`, `PORT=8002`, `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`).
- `app/core/database.py` — **`get_db()`** yields and closes a `SessionLocal()`.
- `app/core/errors.py` — **`AppError`**, **`_request_id(request)`**, and **`register_exception_handlers(app)`** (4 handlers returning `INVALID_VEHICLE_DATA` on 422).
- `app/core/security.py`
  - **`decode_access_token(token: str) -> uuid.UUID`** — Decodes HS256 JWT and returns `user_id` (`401` on error).
  - **`get_current_user_id(credentials) -> uuid.UUID`** — Validates `Authorization: Bearer <token>` and returns caller `user_id`.

### `app/models/`
- `app/models/__init__.py` — Exports `Vehicle`.
- `app/models/vehicle.py`
  - **`utcnow() -> datetime`** — Current UTC timestamp.
  - **`Vehicle(Base)`** — ORM table `vehicles` (`id`, `user_id`, `vehicle_number`, `vehicle_type`, `is_ev`, `is_active`, `created_at`).

### `app/schemas/`
- `app/schemas/vehicle.py`
  - **`normalize_vehicle_number(raw: str) -> str`**
    - *Inputs:* Raw registration string (e.g. `"mh 12-ab 1234"`).
    - *Work:* Strips spaces/hyphens, uppercases, validates `^[A-Z0-9]{4,20}$`.
    - *Output:* Normalized uppercase plate (`"MH12AB1234"`).
  - **`VehicleCreate.validate_plate(v)`** & **`VehicleUpdate.validate_plate(v)`** — Pydantic field validators calling `normalize_vehicle_number`.
  - **`VehicleResponse`**, **`VehicleListResponse`**, **`VehicleDeactivateResponse`** — Output schemas.

### `app/api/v1/vehicles.py`
- **`_get_owned_active_vehicle(db, vehicle_id, user_id) -> Vehicle`**
  - *Inputs:* `db`, `vehicle_id`, `user_id`.
  - *Work:* Queries active vehicle matching both `id` and `user_id`; raises `404 VEHICLE_NOT_FOUND` if missing.
  - *Output:* `Vehicle` ORM object.
- **`create_vehicle(payload, user_id, db) -> VehicleResponse`** (`POST /api/v1/vehicles`)
  - *Inputs:* `VehicleCreate`, `user_id`, `db`.
  - *Work:* Checks for duplicate active plate for this user (`409` if found), inserts `Vehicle`, commits, refreshes.
  - *Output:* `VehicleResponse` (`201`).
- **`list_vehicles(user_id, db) -> VehicleListResponse`** (`GET /api/v1/vehicles`)
  - *Inputs:* `user_id`, `db`.
  - *Work:* Queries all active vehicles owned by `user_id` ordered by `created_at ASC`.
  - *Output:* `VehicleListResponse`.
- **`get_vehicle(vehicle_id, user_id, db) -> VehicleResponse`** (`GET /api/v1/vehicles/{vehicle_id}`)
  - *Inputs:* `vehicle_id`, `user_id`, `db`.
  - *Work:* Calls `_get_owned_active_vehicle(...)`.
  - *Output:* `VehicleResponse`.
- **`update_vehicle(vehicle_id, payload, user_id, db) -> VehicleResponse`** (`PUT /api/v1/vehicles/{vehicle_id}`)
  - *Inputs:* `vehicle_id`, `VehicleUpdate`, `user_id`, `db`.
  - *Work:* Loads owned active vehicle, checks another active vehicle doesn't share the new plate (`409`), updates `vehicle_number`, `vehicle_type`, `is_ev`, commits.
  - *Output:* `VehicleResponse`.
- **`deactivate_vehicle(vehicle_id, user_id, db) -> VehicleDeactivateResponse`** (`DELETE /api/v1/vehicles/{vehicle_id}`)
  - *Inputs:* `vehicle_id`, `user_id`, `db`.
  - *Work:* Loads owned active vehicle, sets `is_active = False` (soft delete), commits.
  - *Output:* `VehicleDeactivateResponse`.

### `tests/test_vehicles.py`
- **`_make_jwt(user_id)`** — Mints HS256 test token.
- **`ctx()`** — In-memory SQLite fixture with `headers_a` and `headers_b`.
- **`test_vehicle_crud_normalization_and_reregistration(ctx)`** — Tests create, duplicate `409`, list, update, soft delete, `404` after delete, and re-registration.
- **`test_owner_isolation_and_invalid_type(ctx)`** — Tests cross-user `404` isolation and `422` invalid `vehicle_type`.

---

## 5. `services/parking-service/` — Parking & Booking Service (Port `8003`, `parking_db`)

Core domain service owning `parking_slots` and `bookings` (linked by `bookings.slot_id` FK), plus the Alembic demonstration setup.

### Service Root & `alembic/`
- `.env.example`, `requirements.txt` (includes `alembic` and `httpx`), `alembic.ini`.
- `alembic/env.py`
  - **`run_migrations_online() -> None`** — Configures SQLAlchemy engine from `settings.DATABASE_URL` and runs Alembic migrations against `Base.metadata`.
- `alembic/script.py.mako` — Migration template.
- `alembic/versions/0001_create_parking_tables.py`
  - **`upgrade() -> None`** — Creates `parking_slots` and `bookings` (with `ForeignKey("parking_slots.id")`).
  - **`downgrade() -> None`** — Drops `bookings` and `parking_slots`.

### `app/main.py`
- **`lifespan(app_instance: FastAPI)`**
  - *Inputs:* `app_instance: FastAPI`.
  - *Work:* Unless `get_db` is overridden, creates tables with `Base.metadata.create_all(bind=engine)` and calls `seed_default_slots(db)`.
  - *Output:* Async generator.
- **`health_check()`** (`GET /health`) — Returns `{"status": "ok", "service": "parking-service"}`.

### `app/core/`
- `app/core/config.py` — `Settings` (`PORT=8003`, `BUSINESS_TIMEZONE`, `JWT_SECRET_KEY`, `VEHICLE_SERVICE_URL`, `PAYMENT_SERVICE_URL`, `INTERNAL_SERVICE_TOKEN`).
- `app/core/database.py` — **`get_db()`** yields and closes a `SessionLocal()`.
- `app/core/errors.py` — **`AppError`**, **`_request_id(request)`**, and **`register_exception_handlers(app)`** (`INVALID_BOOKING_REQUEST` on 422).
- `app/core/clock.py`
  - **`get_business_tz()`** — Returns `ZoneInfo("Asia/Kolkata")` (falls back to fixed `+05:30`).
  - **`get_now() -> datetime`** — Returns current `datetime` in business timezone (overridden in tests).
  - **`as_utc(dt: datetime) -> datetime`** — Converts `datetime` to UTC.
- `app/core/security.py`
  - **`AuthContext`** — Dataclass with `user_id: UUID` and `raw_token: str`.
  - **`decode_access_token(token: str) -> uuid.UUID`** — Verifies HS256 JWT.
  - **`get_auth_context(credentials) -> AuthContext`** — Dependency returning `AuthContext` so routes can forward `raw_token` to Vehicle Service.

### `app/models/`
- `app/models/__init__.py` — Exports `ParkingSlot`, `Booking`, `seed_default_slots`.
- `app/models/parking.py`
  - **`utcnow() -> datetime`** — Current UTC timestamp.
  - **`ParkingSlot(Base)`** — ORM table `parking_slots` (`id`, `slot_number`, `vehicle_type`, `is_charging_enabled`).
  - **`Booking(Base)`** — ORM table `bookings` (`id`, `user_id`, `vehicle_id`, `vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`, `slot_id` FK, `booking_date`, `start_time`, `end_time`, `requires_charging`, `status`, `amount`, `hold_expires_at`, `payment_id`, `created_at`, `cancelled_at`).
  - **`seed_default_slots(db: Session) -> None`**
    - *Inputs:* `db: Session`.
    - *Work:* Checks `count(ParkingSlot.id)`; if `0`, inserts 100 slots (`C01–C50` normal CAR, `C51–C60` EV CAR, `B01–B35` normal BIKE, `B36–B40` EV BIKE) and commits.
    - *Output:* `None`.

### `app/schemas/`
- `app/schemas/parking.py` — `AvailabilityResponse`, `BookingCreateRequest`, `BookingResponse`, `BookingListResponse`, `BookingCancelResponse`.

### `app/services/`
- `app/services/rules.py`
  - **`validate_booking_interval(booking_date, start_time, end_time, now) -> None`**
    - *Inputs:* `booking_date: date`, `start_time: time`, `end_time: time`, `now: datetime`.
    - *Work:* Checks: (1) `booking_date` is today or tomorrow, (2) not Sunday (`weekday() == 6`), (3) whole hours (`minute == 0, second == 0`), (4) within `07:00–22:00` and `end_time > start_time`, (5) duration `<= 12` hours, (6) `start_dt > now_local`. Raises `AppError(422, ...)` if any fail.
    - *Output:* `None`.
  - **`validate_charging_compatibility(is_ev: bool, requires_charging: bool) -> None`**
    - *Inputs:* `is_ev`, `requires_charging`.
    - *Work:* Raises `422 CHARGING_NOT_SUPPORTED` if `requires_charging and not is_ev`.
    - *Output:* `None`.
  - **`calculate_hourly_rate(requires_charging: bool) -> Decimal`**
    - *Inputs:* `requires_charging`.
    - *Output:* `Decimal("20.00")` if `requires_charging`, else `Decimal("10.00")`.
  - **`calculate_booking_amount(start_time, end_time, requires_charging) -> Decimal`**
    - *Inputs:* `start_time`, `end_time`, `requires_charging`.
    - *Work:* Computes `(end_time.hour - start_time.hour) * calculate_hourly_rate(requires_charging)`.
    - *Output:* `Decimal` total amount.
  - **`can_cancel_booking(booking_date, start_time, now) -> bool`**
    - *Inputs:* `booking_date`, `start_time`, `now`.
    - *Work:* Compares `now_local < datetime.combine(booking_date, start_time, tzinfo=tz)`.
    - *Output:* `True` or `False`.
- `app/services/clients.py`
  - **`VehicleInfo`** — Dataclass (`id`, `vehicle_number`, `vehicle_type`, `is_ev`, `is_active`).
  - **`VehicleServiceClient.get_owned_vehicle(vehicle_id, bearer_token, request_id=None) -> VehicleInfo`**
    - *Inputs:* `vehicle_id`, `bearer_token`.
    - *Work:* HTTP `GET` to Vehicle Service (`/api/v1/vehicles/{vehicle_id}`) with `Authorization: Bearer <token>`; maps `404` → `404`, `401` → `401`, network/5xx → `503 VEHICLE_SERVICE_UNAVAILABLE`.
    - *Output:* `VehicleInfo`.
  - **`PaymentServiceClient.create_payment(booking_id, user_id, amount, expires_at, request_id=None) -> uuid.UUID`**
    - *Inputs:* `booking_id`, `user_id`, `amount`, `expires_at`.
    - *Work:* HTTP `POST` to Payment Service (`/internal/v1/payments`) with `X-Internal-Service-Token`; raises `503 PAYMENT_SERVICE_UNAVAILABLE` on error.
    - *Output:* `payment_id` (`UUID`).
  - **`get_vehicle_client()`** & **`get_payment_client()`** — Dependency factories.

### `app/api/`
- `app/api/v1/parking.py`
  - **`_active_booking_filter(now_utc)`** — Returns SQLAlchemy `or_(status == "CONFIRMED", and_(status == "PAYMENT_PENDING", hold_expires_at > now_utc))`.
  - **`_format_time(t: time) -> str`** — Formats `time` as `"HH:MM"`.
  - **`_to_booking_response(booking, slot_number) -> BookingResponse`** — Maps `Booking` ORM row + `slot_number` into `BookingResponse`.
  - **`_expire_stale_holds(db, bookings, now_utc) -> None`** — Iterates over `bookings`; if `PAYMENT_PENDING` and `hold_expires_at <= now_utc`, flips `status = "EXPIRED"` and commits.
  - **`check_availability(...) -> AvailabilityResponse`** (`GET /api/v1/parking/availability`)
    - *Inputs:* Query params (`date`, `start_time`, `end_time`, `vehicle_id`, `requires_charging`), `auth`, `now`, `db`, `vehicle_client`.
    - *Work:* Validates interval, fetches vehicle, checks EV compatibility, counts compatible slots minus overlapping active bookings.
    - *Output:* `AvailabilityResponse`.
  - **`create_booking(...) -> BookingResponse`** (`POST /api/v1/parking/bookings`)
    - *Inputs:* `BookingCreateRequest`, `auth`, `now`, `db`, `vehicle_client`, `payment_client`.
    - *Work:* Validates rules + vehicle, queries compatible `ParkingSlot` rows ordered by `slot_number ASC` with `.with_for_update()` (on PostgreSQL), checks same-user overlap (`409 USER_BOOKING_OVERLAP`), finds first unoccupied slot (`409 NO_PARKING_CAPACITY` if none), inserts `PAYMENT_PENDING` booking with 5-min hold + snapshots, commits, calls Payment Service to create payment, saves `payment_id`, commits.
    - *Output:* `BookingResponse` (`201`).
  - **`list_bookings(...) -> BookingListResponse`** (`GET /api/v1/parking/bookings`)
    - *Inputs:* `page`, `page_size`, `auth`, `now`, `db`.
    - *Work:* Queries paginated bookings for `auth.user_id`, expires any stale holds lazily.
    - *Output:* `BookingListResponse`.
  - **`get_booking(...) -> BookingResponse`** (`GET /api/v1/parking/bookings/{booking_id}`)
    - *Inputs:* `booking_id`, `auth`, `now`, `db`.
    - *Work:* Fetches owned booking (`404` if missing), runs lazy hold expiry.
    - *Output:* `BookingResponse`.
  - **`cancel_booking(...) -> BookingCancelResponse`** (`POST /api/v1/parking/bookings/{booking_id}/cancel`)
    - *Inputs:* `booking_id`, `auth`, `now`, `db`.
    - *Work:* Fetches owned booking (`404`), expires stale hold if needed, verifies `status == "CONFIRMED"` and `can_cancel_booking(...)` (`409` otherwise), sets `status = "CANCELLED"` and `cancelled_at = now_utc`, commits.
    - *Output:* `BookingCancelResponse`.
- `app/api/internal.py`
  - **`_require_internal_token(token) -> None`** — Validates `X-Internal-Service-Token == settings.INTERNAL_SERVICE_TOKEN` (`401` otherwise).
  - **`PaymentResultRequest`** & **`PaymentResultResponse`** — Callback schemas.
  - **`apply_payment_result(booking_id, payload, now, db) -> PaymentResultResponse`** (`POST /internal/v1/bookings/{booking_id}/payment-result`)
    - *Inputs:* `booking_id`, `PaymentResultRequest`, `now`, `db`.
    - *Work:* Looks up booking (`404`), checks `payment_id` match (`409`), handles terminal states (`CONFIRMED` → `ALREADY_APPLIED`, `EXPIRED` → `EXPIRED_NO_RESURRECTION`, `CANCELLED` → `409`), transitions `PAYMENT_PENDING` to `CONFIRMED` if `SUCCESS` and hold valid else `EXPIRED`, commits.
    - *Output:* `PaymentResultResponse`.

### `tests/`
- `tests/test_parking.py` — `FakeVehicleClient`, `FakePaymentClient`, `ctx()`, `test_availability_booking_snapshots_and_overlap`, `test_time_rules_and_sunday_closure`, `test_cancellation_and_lazy_hold_expiry`.
- `tests/test_internal.py` — `ctx()`, `test_payment_result_callback`.

---

## 6. `services/payment-service/` — Payment Service (Port `8004`, `payment_db`)

Owns `payments` table. Creates pending payments, simulates payment outcomes, and notifies Parking Service.

### Service Root Files
- `.env.example`, `requirements.txt` (includes `httpx`).

### `app/main.py`
- **`lifespan(app_instance: FastAPI)`** — Runs `Base.metadata.create_all(bind=engine)` on startup unless overridden.
- **`health_check()`** (`GET /health`) — Returns `{"status": "ok", "service": "payment-service"}`.

### `app/core/`
- `app/core/config.py` — `Settings` (`PORT=8004`, `JWT_SECRET_KEY`, `PARKING_SERVICE_URL`, `INTERNAL_SERVICE_TOKEN`, `PAYMENT_SIMULATION_DEFAULT_OUTCOME`, `ENABLE_TEST_PAYMENT_OVERRIDE`, `ENVIRONMENT`).
- `app/core/database.py` — **`get_db()`** yields and closes a `SessionLocal()`.
- `app/core/errors.py` — **`AppError`**, **`_request_id(request)`**, and **`register_exception_handlers(app)`** (`INVALID_PAYMENT_REQUEST` on 422).
- `app/core/security.py`
  - **`decode_access_token(token)`** & **`get_current_user_id(credentials)`** — HS256 JWT validation.
  - **`require_parking_service_token(token)`** — Validates `X-Internal-Service-Token == settings.INTERNAL_SERVICE_TOKEN` (`401` otherwise).

### `app/models/` & `app/schemas/`
- `app/models/payment.py` — **`utcnow()`** and **`Payment(Base)`** (`id`, `booking_id`, `user_id`, `amount`, `payment_method`, `status`, `transaction_id`, `expires_at`, `created_at`).
- `app/schemas/payment.py` — `InternalPaymentCreateRequest`, `InternalPaymentCreateResponse`, `PaymentProcessRequest`, `PaymentProcessResponse`, `PaymentDetailResponse`.

### `app/services/parking_callback.py`
- **`ParkingCallbackClient.deliver_payment_result(booking_id, payment_id, status, transaction_id, processed_at, request_id=None) -> bool`**
  - *Inputs:* Payment result details.
  - *Work:* Sends `POST` to Parking Service (`/internal/v1/bookings/{booking_id}/payment-result`) with `X-Internal-Service-Token`.
  - *Output:* `True` if HTTP 200, else `False`.
- **`get_callback_client()`** — Dependency factory.

### `app/api/v1/payments.py`
- **`get_now_utc() -> datetime`** — Returns current UTC `datetime` (overridden in tests).
- **`_as_utc(dt: datetime) -> datetime`** — Attaches UTC timezone if naive.
- **`_resolve_simulated_outcome(test_override: str | None) -> str`**
  - *Inputs:* Optional `X-Test-Payment-Outcome` header.
  - *Work:* Returns override (`"SUCCESS"` / `"FAILED"`) if enabled in non-production, else uses `settings.PAYMENT_SIMULATION_DEFAULT_OUTCOME`.
  - *Output:* `"SUCCESS"` or `"FAILED"`.
- **`create_internal_payment(payload, response, db) -> InternalPaymentCreateResponse`** (`POST /internal/v1/payments`)
  - *Inputs:* `InternalPaymentCreateRequest`, `response`, `db`.
  - *Work:* Checks if payment exists for `booking_id` (returns `200` if identical, `409` if conflicting); otherwise inserts `PENDING` payment (`201`).
  - *Output:* `InternalPaymentCreateResponse`.
- **`process_payment(payment_id, payload, test_outcome_header, user_id, now_utc, db, callback_client) -> PaymentProcessResponse`** (`POST /api/v1/payments/{payment_id}/process`)
  - *Inputs:* `payment_id`, `PaymentProcessRequest` (`payment_method`), `user_id`, `now_utc`, `db`, `callback_client`.
  - *Work:* Loads owned payment (`404`), ensures `PENDING` (`409`) and unexpired (`409`), determines outcome, generates `TXN...`, updates DB, commits, and calls `callback_client.deliver_payment_result(...)`.
  - *Output:* `PaymentProcessResponse`.
- **`get_payment(payment_id, user_id, db) -> PaymentDetailResponse`** (`GET /api/v1/payments/{payment_id}`)
  - *Inputs:* `payment_id`, `user_id`, `db`.
  - *Work:* Queries owned payment (`404` if missing).
  - *Output:* `PaymentDetailResponse`.

### `tests/test_payments.py`
- **`_make_jwt(user_id)`**, **`CapturingCallbackClient`**, **`ctx()`**, **`test_internal_payment_create_and_process(ctx)`** — Verifies internal token auth, owner isolation, payment processing, and callback trigger.

---

## 7. `tests/` — Real PostgreSQL Concurrency & Live E2E Tests

### `tests/test_pg_concurrency.py`
- **`_make_jwt(user_id)`** — Mints HS256 JWT.
- **`_StubVehicleClient`** & **`_StubPaymentClient`** — In-process stubs isolating the PostgreSQL lock tests.
- **`_ensure_parking_db_ready()`** — Runs `create_all` and `seed_default_slots` on `parking_db`.
- **`_cleanup_bookings(user_ids)`** — Deletes test bookings from `parking_db`.
- **`test_pg_ev_bike_slot_race_no_double_allocation()`** — 10 concurrent threads race for 5 EV-bike slots (`B36–B40`); asserts 5 succeed with unique slots and 5 get `409 NO_PARKING_CAPACITY`.
- **`test_pg_same_user_simultaneous_overlap_serialized()`** — 1 user sends 4 concurrent overlapping requests; asserts 1 succeeds and 3 get `409 USER_BOOKING_OVERLAP`.

### `tests/test_e2e_journey.py`
- **`_wait_for_health(url)`** — Polls `/health` until a spawned server responds `200`.
- **`_next_operating_date_iso()`** — Picks tomorrow (or today if tomorrow is Sunday) in IST.
- **`_make_jwt(user_id)`** — Mints HS256 JWT.
- **`live_stack()`** — Launches all 4 real Uvicorn processes (`:18001`–`:18004`) connected to PostgreSQL and terminates them on teardown.
- **`_cleanup_e2e_user(user_id)`** — Cleans up test rows across `payment_db`, `parking_db`, and `vehicle_db`.
- **`test_full_e2e_corporate_parking_journey(live_stack)`** — Executes register EV car → check availability → create booking → process UPI payment → verify `CONFIRMED` → cancel booking across all 4 live services.

---

## 8. `coding/` & `corporate-parking-planning-complete-v2/` — Documentation

### `coding/`
- `PROGRESS.md` — 4-service port, DB, and table summary.
- `CODEBASE-COMPLETE-GUIDE.md` — This complete directory & function handbook.
- `API-FLOWS.md` — Architecture diagram and 17-API flow summary.
- `API-TESTING-GUIDE.md` — Step-by-step Swagger UI (`/docs`) demo guide.
- `RUNNING-COMMANDS.md` — Setup, DB init, Alembic, startup, and test commands.
- `DEPENDENCIES.md` — Package reference and service dependency matrix.
- `WHY-WE-USE-EACH-TOOL.md` — Plain-English explanation of tools and backend patterns.
- `m0/`–`m7/` (`iter-01.md`, `iter-02.md`) — Milestone logs.

### `corporate-parking-planning-complete-v2/corporate-parking-planning/`
13 design documents covering `README.md`, `project-overview.md`, `business-rules.md`, `architecture.md`, `api-auth-service.md`, `api-vehicle-service.md`, `api-parking-service.md`, `api-payment-service.md`, `database-design.md`, `service-communication-and-security.md`, `workflows-and-reliability.md`, `quality-and-testing-plan.md`, and `decisions-and-open-questions.md`.
