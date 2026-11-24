# Python Dependencies (`pip` Packages) Guide

Overview of every Python package installed in [requirements.txt](../requirements.txt) and each service's own `requirements.txt` — what it does, **why we chose it**, and where it is used in this project.

---

## 1. Complete Package Reference

| Package | Category | What It Is For | Why We Chose It | Used In |
|---|---|---|---|---|
| **`fastapi`** | Web Framework | Defines HTTP APIs, path/query/header parsing, dependency injection (`Depends`), OpenAPI/Swagger UI (`/docs`), and exception handlers. | Fast, clean type-annotated Python, built-in Swagger UI for demos, and native Pydantic validation. | All 4 services |
| **`uvicorn[standard]`** | ASGI Server | Runs the FastAPI apps locally on ports `8001`–`8004` with auto-reload (`--reload`). | Standard lightweight server for FastAPI. | All 4 services |
| **`sqlalchemy`** (`>=2.0`) | ORM & DB Access | Maps Python classes (`User`, `VerificationCode`, `Vehicle`, `ParkingSlot`, `Booking`, `Payment`) to PostgreSQL tables, creates tables on startup (`Base.metadata.create_all`), manages transactions (`Session`), and handles row locking (`.with_for_update()`). | Modern SQLAlchemy 2.0 typed syntax (`Mapped`, `mapped_column`) with synchronous `Session`. | All 4 services |
| **`psycopg[binary]`** (`>=3.2`) | PostgreSQL Driver | Low-level database driver that lets SQLAlchemy talk to PostgreSQL (`postgresql+psycopg://...`). | Modern **psycopg v3** with precompiled Windows binaries (`[binary]`). | All 4 services |
| **`alembic`** | Schema Migrations | Demonstrates versioned database schema migrations (`upgrade` / `downgrade`) in `parking-service` (`parking_db`), our core multi-table relational domain (`parking_slots` + `bookings`). | Official migration tool built for SQLAlchemy. | `parking-service` |
| **`pydantic`** (`>=2.7`) | Data Validation | Validates and serializes API request/response schemas (e.g., `VehicleCreate`, `BookingCreateRequest`, `PaymentProcessRequest`) separately from SQLAlchemy ORM models. | Built into FastAPI; enforces strict types, enums (`Literal["CAR", "BIKE"]`), UUIDs, decimals, and custom validators (like vehicle-plate normalization). | All 4 services |
| **`pydantic-settings`** | Configuration | Loads environment variables and `.env` files into strongly typed `Settings` classes (`app/core/config.py`). | Keeps DB URLs, `JWT_SECRET_KEY`, and service URLs configurable with clean defaults. | All 4 services |
| **`email-validator`** | Input Validation | Validates email syntax when using Pydantic's `EmailStr` field type (`SendCodeRequest`, `VerifyCodeRequest`). | Required by Pydantic v2 whenever `EmailStr` is used. | `user-auth-service` |
| **`httpx`** | HTTP Client | Makes outbound HTTP calls between microservices: `Parking → Vehicle`, `Parking → Payment`, and `Payment → Parking`. | Modern HTTP client with clean timeouts and required by FastAPI's `TestClient`. | `parking-service`, `payment-service`, tests |
| **`PyJWT`** | JWT Auth | Signs **HS256** access tokens in `user-auth-service` using `JWT_SECRET_KEY` and verifies them locally in `vehicle-service`, `parking-service`, and `payment-service`. | Minimal, standard JWT library for stateless microservice authentication. | All 4 services |
| **`pytest`** | Testing | Runs all unit, PostgreSQL concurrency (`test_pg_concurrency.py`), and live 4-service E2E (`test_e2e_journey.py`) test suites. | Standard Python test runner with clean fixtures (`@pytest.fixture`) and FastAPI `dependency_overrides` support. | Dev / Tests (`scripts/run_all_tests.ps1`) |

---

## 2. Service-by-Service Dependency Matrix

| Package | User/Auth (`:8001`) | Vehicle (`:8002`) | Parking (`:8003`) | Payment (`:8004`) |
|---|:---:|:---:|:---:|:---:|
| `fastapi` | Yes | Yes | Yes | Yes |
| `uvicorn[standard]` | Yes | Yes | Yes | Yes |
| `pydantic` & `pydantic-settings` | Yes | Yes | Yes | Yes |
| `sqlalchemy` | Yes | Yes | Yes | Yes |
| `psycopg[binary]` | Yes | Yes | Yes | Yes |
| `PyJWT` | Yes | Yes | Yes | Yes |
| `alembic` | No *(uses `create_all`)* | No *(uses `create_all`)* | **Yes** | No *(uses `create_all`)* |
| `httpx` | No | No | Yes | Yes |
| `email-validator` | Yes | No | No | No |
