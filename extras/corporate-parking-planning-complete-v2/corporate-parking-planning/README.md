# Corporate Parking Reservation and Management System

## Planning Documentation (Simplified Microservices Baseline)

This folder is the planning and architectural documentation package for the **Corporate Parking Reservation and Management System**, aligned with the simplified 4-microservice implementation.

## How to Read This Documentation

| # | File | Purpose | Status |
|---:|---|---|---|
| 00 | `README.md` | Navigation, project summary, and service/API inventory | Complete |
| 01 | `project-overview.md` | Product purpose, scope, users, assumptions, and boundaries | Complete |
| 02 | `business-rules.md` | Booking, availability, vehicle, charging, payment, and cancellation rules | Complete |
| 03 | `architecture.md` | Microservices responsibilities, data ownership, and interaction views | Complete |
| 04 | `api-auth-service.md` | User/Auth Service API contracts (3 APIs) | Complete |
| 05 | `api-vehicle-service.md` | Vehicle Service API contracts (5 APIs) | Complete |
| 06 | `api-parking-service.md` | Parking Service API contracts (6 APIs: 5 public + 1 internal) | Complete |
| 07 | `api-payment-service.md` | Payment Service API contracts (3 APIs: 2 public + 1 internal) | Complete |
| 08 | `database-design.md` | PostgreSQL tables (6 tables across 4 DBs), columns, types, and relationships | Complete |
| 09 | `service-communication-and-security.md` | Service interactions, HS256 JWT auth, and `X-Internal-Service-Token` security | Complete |
| 10 | `workflows-and-reliability.md` | End-to-end journeys, state transitions, `FOR UPDATE` concurrency, and lazy expiry | Complete |
| 11 | `quality-and-testing-plan.md` | Error conventions, security checks, and unit/concurrency/E2E test scenarios | Complete |
| 12 | `decisions-and-open-questions.md` | Consolidated decision register for the simplified microservices baseline | Complete |

---

## Project at a Glance

The system manages a pool of **100 corporate parking spaces** (`C01–C60` for cars, `B01–B40` for bikes). Eligible employees authenticate with their corporate email via a 6-digit OTP, register their vehicles, check parking availability, reserve a compatible slot (with a 5-minute payment hold), and complete a simulated payment (`UPI`, `CARD`, or `WALLET`) to confirm the booking.

### Microservice Inventory (4 Services, 4 PostgreSQL Databases)

| Service | Local Port | PostgreSQL DB | Tables Owned | Primary Responsibility |
|---|---:|---|---|---|
| **User/Auth Service** | `8001` | `user_db` | `users`, `verification_codes` | Corporate-email OTP verification and HS256 JWT issuance |
| **Vehicle Service** | `8002` | `vehicle_db` | `vehicles` | Standalone owner-scoped vehicle CRUD and soft deactivation |
| **Parking Service** | `8003` | `parking_db` | `parking_slots`, `bookings` | Availability, `FOR UPDATE` slot locking, bookings, fee calculation, cancellation |
| **Payment Service** | `8004` | `payment_db` | `payments` | Simulated payment lifecycle and callback notification to Parking |

---

## API Inventory Count (17 Operations Total)

| Service | Operations | Endpoints |
|---|---:|---|
| **User/Auth (`:8001`)** | 3 | `POST /api/v1/auth/company/send-code`, `POST /api/v1/auth/company/verify`, `GET /api/v1/users/me` |
| **Vehicle (`:8002`)** | 5 | `POST /api/v1/vehicles`, `GET /api/v1/vehicles`, `GET /api/v1/vehicles/{id}`, `PUT /api/v1/vehicles/{id}`, `DELETE /api/v1/vehicles/{id}` |
| **Parking (`:8003`)** | 6 | `GET /api/v1/parking/availability`, `POST /api/v1/parking/bookings`, `GET /api/v1/parking/bookings`, `GET /api/v1/parking/bookings/{id}`, `POST /api/v1/parking/bookings/{id}/cancel` + `POST /internal/v1/bookings/{id}/payment-result` |
| **Payment (`:8004`)** | 3 | `POST /internal/v1/payments`, `POST /api/v1/payments/{id}/process`, `GET /api/v1/payments/{id}` |
| **Total** | **17** | 15 public APIs + 2 internal service-to-service APIs |

---

## Agreed Technology Baseline

- **Repository layout:** Monorepo with `services/user-auth-service`, `services/vehicle-service`, `services/parking-service`, and `services/payment-service`.
- **Language & Web Framework:** Python + FastAPI with synchronous route handlers (`def`) and interactive Swagger UI (`/docs`) on every service.
- **Persistence / ORM:** Synchronous SQLAlchemy (`Session`) with `psycopg` (v3) PostgreSQL driver and request-scoped `get_db()` dependencies.
- **Schema Management:** Automatic table creation on startup via `Base.metadata.create_all(bind=engine)` across all 4 services (plus automatic 100-slot seeding in `parking-service`), and **Alembic** configured in `parking-service` (`services/parking-service/alembic/`) to demonstrate versioned schema migrations on the core relational domain.
- **Authentication:** Stateless **HS256 JWT** signed with `JWT_SECRET_KEY` for user requests, and `X-Internal-Service-Token` (`INTERNAL_SERVICE_TOKEN`) for internal service-to-service endpoints (`/internal/v1/*`).
