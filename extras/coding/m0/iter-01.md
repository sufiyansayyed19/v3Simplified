# Milestone 0 (m0) — Iteration 01: Simplified Microservices Architecture & Decisions

## Goal
Finalize a clean, fresher-explainable microservices architecture across the planning and coding documents.

## Key Decisions Finalized
1. **4 Independent Microservices (No Custom Gateway Process):**
   - `services/user-auth-service` (`:8001` → `user_db`)
   - `services/vehicle-service` (`:8002` → `vehicle_db`)
   - `services/parking-service` (`:8003` → `parking_db`)
   - `services/payment-service` (`:8004` → `payment_db`)
   - Each service exposes its own interactive Swagger UI (`/docs`).
2. **Persistence & Schema Management:**
   - Synchronous SQLAlchemy (`Session`) + `psycopg` (v3) + synchronous FastAPI route handlers (`def`).
   - All 4 services run `Base.metadata.create_all(bind=engine)` on startup (`lifespan`), and `parking-service` auto-seeds the 100 parking slots (`C01–C60`, `B01–B40`).
   - **Alembic** is included in `parking-service` (`services/parking-service/alembic/`) to demonstrate versioned migrations on the core relational domain (`parking_slots` + `bookings`).
3. **PostgreSQL Topology:** 4 separate databases (`user_db`, `vehicle_db`, `parking_db`, `payment_db`) with separate roles/credentials and zero cross-DB foreign keys. Inside `parking_db`, `bookings.slot_id` has a real SQL Foreign Key to `parking_slots.id`.
4. **17-Endpoint Simplified Baseline:**
   - **User/Auth (`:8001`, 3 APIs):** Corporate email OTP (`send-code`, `verify`, `users/me`) issuing an **HS256 JWT** signed with `JWT_SECRET_KEY`.
   - **Vehicle (`:8002`, 5 APIs):** Standalone owner-scoped CRUD with plate normalization and soft delete (`is_active = False`).
   - **Parking (`:8003`, 5 Public + 1 Internal API):** Availability, booking creation with `SELECT ... FOR UPDATE` slot locking and vehicle snapshots, history, cancellation, and internal payment-result callback.
   - **Payment (`:8004`, 1 Internal + 2 Public APIs):** Internal payment creation, simulated payment processing (`UPI`/`CARD`/`WALLET`), and payment retrieval.
5. **Simplified Time Rules:**
   - Operating hours `07:00–22:00` (Mon–Sat; Sunday closed), whole-hour slots, max 12 hours.
   - Booking date must be today or tomorrow with `start_time > now`.
   - Confirmed bookings can be cancelled anytime before `start_time`.
