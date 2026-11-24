# Milestone 1 (m1) — Iteration 01: Monorepo & Database Foundation

## Goal
Scaffold the monorepo structure (`services/*`), set up isolated synchronous SQLAlchemy + `psycopg` v3 foundations for each of the 4 microservices, add PostgreSQL database/role initialization SQL, configure Alembic in `parking-service`, and verify `/health` on all 4 FastAPI apps.

## What Was Built

### 1. Monorepo Layout
- `services/user-auth-service/` — User/Auth Service (`PORT=8001`, `user_db`).
- `services/vehicle-service/` — Vehicle Service (`PORT=8002`, `vehicle_db`).
- `services/parking-service/` — Parking Service (`PORT=8003`, `parking_db`).
- `services/payment-service/` — Payment Service (`PORT=8004`, `payment_db`).

### 2. Service-Local Persistence & Schema Setup
Each of the 4 microservices independently owns:
- `app/core/config.py` — Pydantic Settings loading its own `.env`.
- `app/core/database.py` — Synchronous SQLAlchemy `create_engine` (`postgresql+psycopg://`), `SessionLocal`, `Base`, and request-scoped `get_db()` generator dependency.
- `app/main.py` — Runs `Base.metadata.create_all(bind=engine)` on startup (`lifespan`) and exposes `GET /health`.
- `services/parking-service/alembic/` — Alembic migration configuration and `0001_create_parking_tables.py` for `parking_db`.
