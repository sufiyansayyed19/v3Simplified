# Directory & File Purpose Guide

> **Audience**: Personal quick-reference for understanding every folder, file naming pattern, and individual file in `ParkingSimplified`.

---

## 1. Root-Level Repository Layout

```text
ParkingSimplified/
├── services/                              # All 4 independent FastAPI microservices
│   ├── user-auth-service/                 # Port 8001 — Corporate email OTP + HS256 JWT
│   ├── vehicle-service/                   # Port 8002 — Vehicle registration & ownership CRUD
│   ├── parking-service/                   # Port 8003 — Slots, availability, holds, bookings, cancellations
│   └── payment-service/                   # Port 8004 — Simulated payments & callback delivery
├── tests/                                 # Cross-service integration & concurrency test suites
├── scripts/                               # DB setup, multi-service start, and test runner scripts
├── architecture-and-docs/                 # Presentation-ready specs (Architecture, ER, LLD, API Docs)
├── coding/                                # Personal learning guides, notes, and milestone logs
├── corporate-parking-planning-complete-v2/# Original planning & business-rules reference docs
├── .venv/                                 # Shared Python virtual environment (all packages installed here)
├── .vscode/                               # Workspace editor settings (e.g., disabling MSSQL T-SQL warnings)
├── requirements.txt                       # Combined Python dependencies for the whole monorepo
└── .gitignore                             # Files/folders excluded from Git (.venv, .env, __pycache__)
```

---

## 2. Top-Level Folders & Their Purpose

| Folder | Purpose | When You Use It |
| :--- | :--- | :--- |
| **`services/`** | Contains the 4 standalone microservices. Each service has its own `app/`, `tests/`, `.env.example`, and `requirements.txt`. | Whenever reading, editing, or running any service (`:8001`–`:8004`). |
| **`tests/`** | Cross-service tests that span multiple services or real PostgreSQL (`test_pg_concurrency.py`, `test_e2e_journey.py`). | Running full-system verification. |
| **`scripts/`** | Operational scripts for Windows PowerShell (`.ps1`), Linux/Mac Bash (`.sh`), and PostgreSQL (`init_postgres.sql`). | Initializing DBs, starting all 4 ports, or running all 7 test suites. |
| **`architecture-and-docs/`** | Clean, formal diagrams and specifications (`01` to `04`) meant for **showing and explaining** to mentors/architects. | During demos, reviews, and architecture presentations. |
| **`coding/`** | Deep-dive learning guides (`AUTHENTICATION-FLOW-GUIDE.md`, `EDGE-CASES-AND-TECHNIQUES.md`, etc.) + milestone logs (`m0/`–`m7/`). | For your own study and interview/viva preparation. |
| **`.venv/`** | Local Python 3.13 virtual environment shared across all 4 services. | Running `uvicorn`, `pytest`, or `alembic` via `.\.venv\Scripts\python.exe`. |
| **`.vscode/`** | VS Code workspace configuration (`settings.json`). | Editor behavior for this project only. |

---

## 3. Standard Folder Structure Inside Every Microservice

All 4 services in `services/<service-name>/` follow the exact same layered layout:

```text
services/<service-name>/
├── app/
│   ├── main.py          # App entrypoint
│   ├── api/             # HTTP route handlers (controllers)
│   │   ├── v1/          # Public versioned REST endpoints (/api/v1/...)
│   │   └── internal.py  # Service-to-service endpoints (/internal/v1/...) [parking-service]
│   ├── core/            # Infrastructure & cross-cutting setup (config, DB, auth, errors)
│   ├── models/          # SQLAlchemy 2.0 database table definitions
│   ├── schemas/         # Pydantic v2 request/response DTOs & validation
│   └── services/        # Business rules, email sender, and HTTP clients to other services
├── alembic/             # Database migration scripts [parking-service only]
├── tests/               # Service-level pytest unit/integration tests
├── .env.example         # Template of environment variables for this service
└── requirements.txt     # Dependencies required by this individual service
```

---

## 4. File Types & Naming Patterns (What Every File Does)

### A. Entrypoint & Core Infrastructure Files (`app/` & `app/core/`)

| File Name | Where It Exists | What It Does |
| :--- | :--- | :--- |
| **`main.py`** | Every service (`app/main.py`) | Creates the `FastAPI` app, runs startup `lifespan` (`Base.metadata.create_all` + slot seeding in `parking-service`), registers error handlers, mounts routers, and exposes `GET /health`. |
| **`config.py`** | Every service (`app/core/config.py`) | Defines `Settings(BaseSettings)` using `pydantic-settings` to load `.env` variables (`DATABASE_URL`, `JWT_SECRET_KEY`, `INTERNAL_SERVICE_TOKEN`, service URLs, ports). |
| **`database.py`** | Every service (`app/core/database.py`) | Sets up the SQLAlchemy `engine`, `SessionLocal` factory, `Base` declarative class, and the `get_db()` FastAPI dependency that opens/closes a DB session per request. |
| **`security.py`** | Every service (`app/core/security.py`) | Handles JWT verification (`decode_access_token`) and FastAPI `Depends` guards (`get_current_user`, `get_current_user_id`, `get_auth_context`, `require_parking_service_token`). In `user-auth-service`, also handles OTP generation and `create_access_token`. |
| **`errors.py`** | Every service (`app/core/errors.py`) | Defines `AppError(status_code, code, message)` and registers global FastAPI exception handlers so every error returns a uniform `{ "error": { "code", "message", "request_id" } }` JSON envelope. |
| **`clock.py`** | `parking-service` (`app/core/clock.py`) | Provides `get_now()`, `as_utc()`, and `get_business_tz()` (`Asia/Kolkata`) so time rules and hold expirations are timezone-safe and easy to override in tests. |
| **`__init__.py`** | Every Python package folder | Marks the folder as an importable Python package (and in `models/__init__.py`, ensures ORM models are imported so `Base.metadata.create_all()` sees all tables). |

---

### B. Data Layer: Models vs. Schemas (`app/models/` vs. `app/schemas/`)

| File Name | Layer | What It Does |
| :--- | :--- | :--- |
| **`models/auth.py`** | Database (SQLAlchemy) | Defines `users` and `verification_codes` tables in `user_db`. |
| **`models/vehicle.py`** | Database (SQLAlchemy) | Defines `vehicles` table in `vehicle_db`. |
| **`models/parking.py`** | Database (SQLAlchemy) | Defines `parking_slots` and `bookings` tables in `parking_db`, plus `seed_default_slots()` (seeds `C01`–`C60`, `B01`–`B40`). |
| **`models/payment.py`** | Database (SQLAlchemy) | Defines `payments` table in `payment_db`. |
| **`schemas/auth.py`** | API Contract (Pydantic) | Request/response validation models (`SendCodeRequest`, `VerifyCodeRequest`, `AuthTokenResponse`, `UserProfile`). |
| **`schemas/vehicle.py`** | API Contract (Pydantic) | Request/response models (`VehicleCreate`, `VehicleUpdate`, `VehicleResponse`) + `normalize_vehicle_number()` plate validator. |
| **`schemas/parking.py`** | API Contract (Pydantic) | Request/response models (`AvailabilityResponse`, `BookingCreateRequest`, `BookingResponse`, `BookingListResponse`, `BookingCancelResponse`). |
| **`schemas/payment.py`** | API Contract (Pydantic) | Request/response models (`InternalPaymentCreateRequest`, `PaymentProcessRequest`, `PaymentProcessResponse`, `PaymentDetailResponse`). |

> **Easy rule to remember:**  
> - **`models/*.py`** = What gets saved in **PostgreSQL tables**.  
> - **`schemas/*.py`** = What comes in and goes out of **JSON API requests/responses**.

---

### C. API Routes & Business Services (`app/api/` & `app/services/`)

| File Name | Where It Exists | What It Does |
| :--- | :--- | :--- |
| **`api/v1/auth.py`** | `user-auth-service` | Routes for `/api/v1/auth/company/send-code`, `/verify`, and `/api/v1/users/me`. |
| **`api/v1/vehicles.py`** | `vehicle-service` | Routes for `POST/GET /api/v1/vehicles` and `GET/PUT/DELETE /api/v1/vehicles/{vehicle_id}`. |
| **`api/v1/parking.py`** | `parking-service` | Routes for `/availability`, `/bookings`, `/bookings/{id}`, `/bookings/{id}/cancel`, `SELECT ... FOR UPDATE` slot locking, and lazy hold expiry. |
| **`api/internal.py`** | `parking-service` | Internal M2M callback route `POST /internal/v1/bookings/{booking_id}/payment-result` protected by `X-Internal-Service-Token`. |
| **`api/v1/payments.py`** | `payment-service` | Internal `POST /internal/v1/payments` + public `POST /api/v1/payments/{id}/process` and `GET /api/v1/payments/{id}`. |
| **`services/email_sender.py`** | `user-auth-service` | `EmailSender` interface and `ConsoleEmailSender` (prints 6-digit OTP to terminal in dev mode). |
| **`services/rules.py`** | `parking-service` | Pure business-rule functions: operating hours (`07:00–22:00`), today/tomorrow window, Sunday closure, 12h max, EV compatibility, ₹10/₹20 pricing, and cancellation cutoff. |
| **`services/clients.py`** | `parking-service` | `httpx` clients (`VehicleServiceClient`, `PaymentServiceClient`) used by `parking-service` to call `vehicle-service` and `payment-service`. |
| **`services/parking_callback.py`** | `payment-service` | `ParkingCallbackClient` used by `payment-service` to push payment results back to `parking-service`. |

---

### D. Database Migrations (`services/parking-service/alembic/`)

| File Name | What It Does |
| :--- | :--- |
| **`alembic.ini`** | Alembic configuration file pointing to `alembic/` script location. |
| **`alembic/env.py`** | Connects Alembic to `parking-service`'s `settings.DATABASE_URL` and `Base.metadata`. |
| **`alembic/script.py.mako`** | Template used when generating new migration files. |
| **`alembic/versions/0001_create_parking_tables.py`** | Initial versioned migration creating `parking_slots` and `bookings` (`upgrade` / `downgrade`). |

---

### E. Scripts, Environment & Test Files

| File Pattern | Files in Project | What They Do |
| :--- | :--- | :--- |
| **`.env` / `.env.example`** | `services/*/.env.example`, `services/user-auth-service/.env` | Stores local environment variables (DB credentials, JWT secret, ports). `.env.example` is safe to commit; `.env` is ignored by Git. |
| **`tests/test_*.py`** | `test_auth.py`, `test_vehicles.py`, `test_parking.py`, `test_internal.py`, `test_payments.py`, `test_pg_concurrency.py`, `test_e2e_journey.py` | Automated `pytest` suites covering unit logic, internal callbacks, real PostgreSQL row-locking race conditions, and full end-to-end user journeys. |
| **`scripts/*.sql`** | `scripts/init_postgres.sql` | One-time PostgreSQL bootstrap script creating the 4 roles (`user_auth_user`, `vehicle_user`, `parking_user`, `payment_user`) and 4 isolated databases. |
| **`scripts/*.ps1` / `*.sh`** | `start_all.ps1`, `start_all.sh`, `run_all_tests.ps1`, `run_all_tests.sh` | Convenience scripts to launch all 4 services or run all 7 test suites in one command on Windows (`.ps1`) or Linux/Mac (`.sh`). |
