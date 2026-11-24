# Decision Register (Simplified Microservices Baseline)

**Document status:** Finalized register reflecting the simplified, fresher-explainable 4-microservice architecture.

---

## 1. Finalized Architecture & Design Decisions

| ID | Decision Area | Finalized Choice |
|---|---|---|
| **D-01** | **Microservices Topology** | 4 independent FastAPI microservices (`user-auth-service :8001`, `vehicle-service :8002`, `parking-service :8003`, `payment-service :8004`) with 4 isolated PostgreSQL databases (`user_db`, `vehicle_db`, `parking_db`, `payment_db`). |
| **D-02** | **API Gateway** | Removed custom FastAPI reverse-proxy Gateway (`gateway/`) so each microservice is demonstrated and tested directly via its own interactive Swagger UI (`/docs`). |
| **D-03** | **Database ORM & Startup** | Synchronous SQLAlchemy 2.0 (`Session`) + `psycopg` v3. All 4 services run `Base.metadata.create_all(bind=engine)` on startup (`lifespan`), and `parking-service` auto-seeds the 100 parking slots (`C01–C60`, `B01–B40`). |
| **D-04** | **Alembic Demonstration** | Configured Alembic in **`parking-service`** (`services/parking-service/alembic/`) to demonstrate versioned schema migrations (`upgrade` / `downgrade`) on the core multi-table relational database (`parking_slots` + `bookings`). |
| **D-05** | **Primary Keys** | `UUID` (`uuid.uuid4`) across all 6 tables and in the JWT `"sub"` claim. |
| **D-06** | **User Authentication** | Corporate-email OTP (`COMPANY_EMAIL_DOMAIN`) with 2 tables (`users`, `verification_codes`), 3 endpoints (`send-code`, `verify`, `users/me`), and stateless **HS256 Bearer JWT** signed with `JWT_SECRET_KEY` (dropped RS256 PEM keys, `auth_identities`, and `refresh_sessions` cookies). |
| **D-07** | **Standalone Vehicle Service** | 5 owner-scoped CRUD endpoints with plate normalization and soft delete (`is_active = false`). Dropped reverse `Vehicle → Parking` dependency call because `bookings` stores immutable vehicle snapshots (`vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`). |
| **D-08** | **Concurrency & Booking Creation** | Uses standard SQLAlchemy `.with_for_update()` (`SELECT ... FOR UPDATE`) on compatible `ParkingSlot` rows inside the booking transaction (dropped `pg_advisory_xact_lock` byte-math and `booking_idempotency_keys` table). |
| **D-09** | **Simplified Time & Cancellation Rules** | 3 clean rules: (1) whole hours `07:00–22:00`, Mon–Sat (Sunday closed), max 12h; (2) booking date is today or tomorrow with `start_time > now`; (3) cancel a `CONFIRMED` booking anytime before `start_time`. |
| **D-10** | **Payment & Internal Auth** | Clean `payments` table (dropped webhook retry metadata columns) and 1 shared `INTERNAL_SERVICE_TOKEN` (`X-Internal-Service-Token`) protecting `/internal/v1/*` calls between Parking and Payment. |
