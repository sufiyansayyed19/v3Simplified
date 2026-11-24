# Start-to-End Presentation & Architecture Evaluation Guide

Your complete script and survival playbook for presenting the **Corporate Parking Reservation & Management System** to your **mentor** or **technical architecture examiner**—covering the pitch, pre-demo checklist, architecture explanation, live Swagger demo, test proof, code walkthrough, and top viva questions.

---

## Part 1: Your 30-Second Opening Pitch

Start confidently with this exact framing before touching Swagger or code:

> *"Our project is a **Corporate Parking Reservation & Management System** built using a **4-microservice architecture** in Python with **FastAPI**, **SQLAlchemy**, and **PostgreSQL**. We have 100 parking slots (`C01–C60` for cars, `B01–B40` for bikes, including 15 EV charging slots). Instead of putting everything into one database, we follow the **Database-per-Service** pattern across 4 isolated PostgreSQL databases (`user_db`, `vehicle_db`, `parking_db`, `payment_db`). Services communicate over HTTP using `httpx`, share stateless **HS256 JWT** authentication, prevent double-booking using PostgreSQL **row-level locking (`SELECT ... FOR UPDATE`)**, and include an automated `pytest` suite with real multithreaded PostgreSQL concurrency and live 4-service end-to-end tests."*

---

## Part 2: 5-Minute Pre-Demo Checklist (Do This Before the Examiner Joins)

1. **Ensure `user_db` has no leftover legacy tables** (only needed once if `user_db` was migrated earlier):
   ```powershell
   psql -U postgres -d user_db -c "DROP TABLE IF EXISTS alembic_version, refresh_sessions, auth_identities, verification_codes, users CASCADE;"
   ```
2. **Start all 4 microservices** from the project root:
   ```powershell
   .\scripts\start_all.ps1
   ```
   *(This opens 4 labeled PowerShell windows for ports `8001`–`8004`, automatically creates all tables via `Base.metadata.create_all(bind=engine)`, and seeds all 100 parking slots in `parking_db`.)*
3. **Verify Alembic status in `parking-service`** (optional, in case the examiner asks to see Alembic):
   ```powershell
   cd services\parking-service
   ..\..\.venv\Scripts\python.exe -m alembic current
   cd ..\..
   ```
   Expected output: `0001_create_parking_tables (head)`
4. **Open these 4 Swagger UI tabs side-by-side in your browser:**
   - Tab 1 — **User/Auth (`:8001`)**: `http://127.0.0.1:8001/docs`
   - Tab 2 — **Vehicle (`:8002`)**: `http://127.0.0.1:8002/docs`
   - Tab 3 — **Parking (`:8003`)**: `http://127.0.0.1:8003/docs`
   - Tab 4 — **Payment (`:8004`)**: `http://127.0.0.1:8004/docs`
5. **Keep one clean terminal open at the project root** ready to run `.\scripts\run_all_tests.ps1`.

---

## Part 3: Architecture Walkthrough (Explain First, Demo Second)

Open [API-FLOWS.md](API-FLOWS.md) (or draw this on a whiteboard) and walk the examiner through **4 key architectural pillars**:

```text
User / Swagger UI
   ├── :8001 User/Auth Service  ──▶ user_db    (users, verification_codes)
   ├── :8002 Vehicle Service    ──▶ vehicle_db (vehicles)
   ├── :8003 Parking Service    ──▶ parking_db (parking_slots, bookings)  [Alembic + 100-slot seed]
   └── :8004 Payment Service    ──▶ payment_db (payments)

Inter-Service HTTP Calls (httpx):
   1. Parking (:8003) ──GET /api/v1/vehicles/{id}──────────────────▶ Vehicle (:8002)  [Bearer JWT]
   2. Parking (:8003) ──POST /internal/v1/payments─────────────────▶ Payment (:8004)  [X-Internal-Service-Token]
   3. Payment (:8004) ──POST /internal/v1/bookings/{id}/payment-result ▶ Parking (:8003) [X-Internal-Service-Token]
```

### The 4 Pillars to Highlight
1. **Service & Data Isolation:**
   - 4 microservices, 4 separate PostgreSQL databases, 4 separate DB roles (`init_postgres.sql`).
   - Zero cross-database foreign keys. The **only SQL Foreign Key** is `bookings.slot_id → parking_slots.id` inside `parking_db`.
   - Cross-service IDs (`user_id`, `vehicle_id`, `booking_id`, `payment_id`) are **UUIDs** validated via JWT (`sub`) or `httpx` API calls.
2. **Stateless Auth + Internal Security:**
   - User login issues an **HS256 JWT** (`JWT_SECRET_KEY`). Every service verifies it locally without calling `user-auth-service` on every request.
   - Internal endpoints (`/internal/v1/*`) are protected by `X-Internal-Service-Token`.
3. **Concurrency & Data Integrity:**
   - `POST /api/v1/parking/bookings` uses SQLAlchemy `.with_for_update()` (`SELECT ... FOR UPDATE`) on compatible `ParkingSlot` rows so two users racing for the last slot cannot double-book.
   - `bookings` captures immutable **vehicle snapshots** (`vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`) so booking history stays accurate even if a user edits or soft-deletes a vehicle.
4. **Zero-Daemon Lazy Hold Expiry:**
   - Unpaid bookings get a 5-minute `PAYMENT_PENDING` hold (`hold_expires_at`). Availability queries ignore expired holds, and read/callback endpoints flip expired holds to `EXPIRED` on access—no Redis or Celery daemon required.

---

## Part 4: Live Demo Script (Step-by-Step in Swagger UI)

Follow this exact order in your 4 browser tabs:

### Step 1 — Corporate Email Login (`:8001/docs`)
1. Expand `POST /api/v1/auth/company/send-code` → Try it out:
   ```json
   { "email": "alice@company.com" }
   ```
   - *Point out:* Look at the **User/Auth Service (`8001`) PowerShell window**—the 6-digit OTP is printed there (`[DEV EMAIL OTP] To: alice@company.com | Code: XXXXXX`).
2. Expand `POST /api/v1/auth/company/verify` → Enter `alice@company.com` and the 6-digit OTP → Execute.
3. **Copy the returned `access_token`** (without quotes).
4. Click the green **Authorize 🔒** button at the top-right of **all 4 Swagger tabs (`8001`, `8002`, `8003`, `8004`)** and paste `access_token`.
5. *(Quick check)* Run `GET /api/v1/users/me` on `:8001/docs` → shows Alice's UUID and email.

### Step 2 — Register an EV Car (`:8002/docs`)
1. Expand `POST /api/v1/vehicles` → Try it out with messy casing/spaces:
   ```json
   {
     "vehicle_number": "mh 12-ab 1234",
     "vehicle_type": "CAR",
     "is_ev": true
   }
   ```
2. **Point out in `201` response:** Pydantic automatically normalized `"mh 12-ab 1234"` → `"MH12AB1234"`.
3. **Copy the returned `id`** (`<VEHICLE_ID>`).

### Step 3 — Check Parking Availability (`:8003/docs`)
1. Expand `GET /api/v1/parking/availability` → Enter:
   - `date`: Tomorrow's date (`YYYY-MM-DD`, not Sunday)
   - `start_time`: `10:00`
   - `end_time`: `12:00`
   - `vehicle_id`: `<VEHICLE_ID>`
   - `requires_charging`: `true`
2. **Point out in `200` response:**
   - Parking Service called Vehicle Service over `httpx` behind the scenes to verify ownership and `is_ev: true`.
   - `available_slots: 10` (slots `C51–C60`) and `rate_per_hour: 20.00`.

### Step 4 — Create Booking Hold (`:8003/docs`)
1. Expand `POST /api/v1/parking/bookings` → Execute:
   ```json
   {
     "vehicle_id": "<VEHICLE_ID>",
     "date": "<TOMORROW_DATE>",
     "start_time": "10:00",
     "end_time": "12:00",
     "requires_charging": true
   }
   ```
2. **Point out in `201` response:**
   - Auto-allocated slot **`C51`** (first available EV car slot).
   - Calculated `amount: 40.00` (2 hours × ₹20/hr).
   - Stored vehicle snapshots (`vehicle_number_snapshot: "MH12AB1234"`).
   - Status is **`PAYMENT_PENDING`** with a 5-minute `hold_expires_at`.
   - Parking Service called Payment Service (`POST /internal/v1/payments`) and got **`payment_id`**.
3. **Copy both `booking_id` and `payment_id`**.

### Step 5 — Process Simulated Payment (`:8004/docs`)
1. Expand `POST /api/v1/payments/{payment_id}/process` → Enter `payment_id` and body:
   ```json
   { "payment_method": "UPI" }
   ```
2. **Point out in `200` response:**
   - `status: "SUCCESS"` and generated `transaction_id: "TXN..."`.
   - Payment Service saved the outcome to `payment_db` and automatically sent an internal callback (`POST /internal/v1/bookings/{booking_id}/payment-result`) to Parking Service.

### Step 6 — Verify Booking Confirmed & Cancel (`:8003/docs`)
1. Call `GET /api/v1/parking/bookings/{booking_id}` → **`status` is now `"CONFIRMED"`**!
2. Call `POST /api/v1/parking/bookings/{booking_id}/cancel` → **`status` transitions to `"CANCELLED"`** with `cancelled_at` timestamp (record is preserved, never deleted).

### Step 7 — 3 Quick Edge-Case Demos (Optional Bonus Points)
If the examiner wants to see validation & error handling live:
1. Send `{"email": "user@gmail.com"}` to `send-code` → **`403 CORPORATE_EMAIL_REQUIRED`** (standardized `{ "error": { "code", "message", "request_id" } }` envelope).
2. Try booking `requires_charging: true` with a non-EV vehicle → **`422 CHARGING_NOT_SUPPORTED`**.
3. Call `POST /api/v1/payments/{payment_id}/process` a second time on the already-paid `payment_id` → **`409 PAYMENT_ALREADY_PROCESSED`**.

---

## Part 5: Automated Test Proof (Run in Terminal)

Run the entire automated test suite in front of the examiner:

```powershell
.\scripts\run_all_tests.ps1
```

**What to say while it runs (takes ~15–20 seconds):**
- *"First, it runs 5 isolated unit test suites (`test_auth.py`, `test_vehicles.py`, `test_parking.py`, `test_internal.py`, `test_payments.py`) using in-memory SQLite and FastAPI `dependency_overrides`."*
- *"Next, `test_pg_concurrency.py` runs against **real PostgreSQL (`parking_db`)**: it launches **10 simultaneous threads** racing for the **5 EV-bike slots (`B36–B40`)** and proves exactly 5 succeed with unique slots and 5 get `409 NO_PARKING_CAPACITY`—zero double-bookings. It also fires 4 simultaneous requests from the same user and proves only 1 succeeds (`USER_BOOKING_OVERLAP`)."*
- *"Finally, `test_e2e_journey.py` boots all 4 real Uvicorn servers on ports `18001–18004` against all 4 PostgreSQL databases and runs the full end-to-end journey automatically."*

---

## Part 6: Code Walkthrough Cheat Sheet (If Asked to Open Files)

Open these **5 key files** in order if the examiner asks *"Show me how you wrote it"*:

1. **`services/parking-service/app/main.py`** → Show `lifespan()` calling `Base.metadata.create_all(bind=engine)` and `seed_default_slots(db)`.
2. **`services/parking-service/app/models/parking.py`** → Show `ParkingSlot`, `Booking` (with `ForeignKey("parking_slots.id")` and `*_snapshot` columns), and `seed_default_slots()`.
3. **`services/parking-service/app/api/v1/parking.py`** → Show `create_booking()`:
   - `vehicle_client.get_owned_vehicle(...)` (HTTP call to Vehicle Service)
   - `slot_stmt.with_for_update()` (PostgreSQL row lock)
   - `Booking.start_time < payload.end_time, Booking.end_time > payload.start_time` (overlap check)
   - `payment_client.create_payment(...)` (HTTP call to Payment Service)
4. **`services/parking-service/alembic/versions/0001_create_parking_tables.py`** → Show clean `upgrade()` and `downgrade()` migration functions.
5. **`services/payment-service/app/api/v1/payments.py`** → Show `process_payment()` persisting `SUCCESS` + `TXN...` and calling `callback_client.deliver_payment_result(...)`.

---

## Part 7: Top 15 Examiner & Mentor Viva Questions (With Crisp Answers)

### Q1. Why did you choose Microservices instead of a Monolith?
> *"Each business domain—Identity (`user_db`), Vehicles (`vehicle_db`), Parking Inventory/Bookings (`parking_db`), and Payments (`payment_db`)—has independent data ownership and can be scaled, deployed, and maintained separately. Services never touch each other's databases directly and communicate strictly over REST APIs."*

### Q2. Why didn't you put Foreign Keys for `user_id`, `vehicle_id`, and `booking_id`?
> *"In a Database-per-Service architecture, PostgreSQL cannot enforce foreign keys across separate databases (`parking_db` to `vehicle_db` or `user_db`). So we use a real SQL Foreign Key within the same database (`bookings.slot_id → parking_slots.id`), while cross-service IDs are UUIDs validated via HS256 JWT (`user_id`) and `httpx` API calls (`vehicle_id`, `booking_id`)."*

### Q3. Why did you use `UUID` primary keys instead of auto-increment integers (`1, 2, 3`)?
> *"In distributed microservices, UUIDs (`uuid.uuid4`) are globally unique across all 4 databases without needing a central ID generator, and they prevent users from guessing sequential IDs (`/vehicles/1`, `/vehicles/2`) in URLs."*

### Q4. How do you prevent two users from booking the exact same slot at the same millisecond?
> *"Inside `create_booking()` in `parking-service`, we query all compatible `ParkingSlot` rows ordered by `slot_number ASC` with SQLAlchemy's `.with_for_update()` (`SELECT ... FOR UPDATE`). PostgreSQL locks those rows for the duration of the transaction, forcing concurrent requests to wait until the first transaction commits. We prove this in `tests/test_pg_concurrency.py` with 10 threads racing for 5 slots."*

### Q5. What happens if a user creates a booking and never pays? Do you use Celery or Redis?
> *"No—to keep the system lightweight, we use **Lazy Hold Expiry**. Every `PAYMENT_PENDING` booking gets `hold_expires_at = now + 5 minutes`. Availability and overlap queries ignore `PAYMENT_PENDING` rows whose `hold_expires_at <= now()`, and `GET` or callback endpoints flip expired rows to `EXPIRED` when accessed."*

### Q6. What if Payment succeeds right after the 5-minute hold has expired?
> *"Inside `POST /internal/v1/bookings/{booking_id}/payment-result`, Parking Service checks `hold_expires_at <= now_utc` using its own authoritative clock. If the hold has expired, it marks the booking `EXPIRED` and never resurrects it."*

### Q7. What happens if a user updates or deletes a vehicle after booking? Won't old booking history break?
> *"No, because of two design choices: (1) `DELETE /vehicles/{id}` is a **soft delete** (`is_active = False`), and (2) `bookings` captures immutable **vehicle snapshots** (`vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`) at booking creation time."*

### Q8. Why did you use `HS256` JWT instead of calling `user-auth-service` on every API request?
> *"If Vehicle, Parking, and Payment had to call Auth Service on every single API request, Auth Service would become a bottleneck and single point of failure. With JWTs signed using `JWT_SECRET_KEY`, every microservice verifies tokens locally in memory and extracts `user_id` from the `sub` claim."*

### Q9. How do you stop a regular user from calling `/internal/v1/bookings/{id}/payment-result` to get free parking?
> *"Both internal endpoints (`POST /internal/v1/payments` and `POST /internal/v1/bookings/{id}/payment-result`) require the `X-Internal-Service-Token` header matching `INTERNAL_SERVICE_TOKEN`, returning `401 INTERNAL_CALLER_UNAUTHORIZED` otherwise. In production, internal routes would also sit behind a private VPC/network policy."*

### Q10. Why did you use Alembic only in `parking-service` and `Base.metadata.create_all()` in the other three?
> *"For the simpler single-domain services (`user-auth-service`, `vehicle-service`, `payment-service`), `Base.metadata.create_all(bind=engine)` handles initial table creation cleanly during the sprint. We implemented Alembic in `parking-service` because `parking_db` is our core multi-table relational database (`parking_slots` and `bookings` linked by a Foreign Key), demonstrating versioned `upgrade()` and `downgrade()` migrations where schema evolution matters most."*

### Q11. Why did you choose synchronous SQLAlchemy (`def` handlers + `psycopg` v3) instead of `async` (`asyncpg`)?
> *"Synchronous SQLAlchemy (`Session`) with FastAPI `def` route handlers is cleaner, easier to debug, avoids async session/greenlet pitfalls, and FastAPI automatically runs `def` routes in a threadpool so they don't block the event loop."*

### Q12. Why did you commit the `PAYMENT_PENDING` booking BEFORE calling Payment Service?
> *"We never hold a PostgreSQL database transaction open across an external HTTP call. If Payment Service takes 2–3 seconds to respond, holding a DB connection and `FOR UPDATE` row lock open would stall other users and risk connection pool exhaustion."*

### Q13. What happens if Vehicle Service or Payment Service is down during a booking?
> *"The system **fails closed**: `VehicleServiceClient` and `PaymentServiceClient` catch `httpx.HTTPError` / non-200 responses with a 3-second timeout and return `503 VEHICLE_SERVICE_UNAVAILABLE` or `503 PAYMENT_SERVICE_UNAVAILABLE` rather than proceeding with unverified data."*

### Q14. Why do you have both `Parking` calling `Vehicle` and no `Vehicle` calling `Parking`?
> *"Keeping dependencies strictly **one-way** (`Parking → Vehicle` and `Parking ↔ Payment`) avoids circular dependencies between microservices, so `Vehicle Service` remains 100% standalone."*

### Q15. If you had more time to take this to production, what would you add?
> 1. **API Gateway / Reverse Proxy (Nginx or Kong)** in front of ports `8001–8004` for a single domain entry point and rate limiting.
> 2. **Alembic across all 4 services** and a real **SMTP/SES email provider** implementing `EmailSender`.
> 3. **Real payment gateway (Razorpay/Stripe)** with webhooks, plus a **Background Worker / Outbox pattern** for callback retries and hold cleanup.
> 4. **Dockerfiles + `docker-compose.yml`** for one-command containerized deployment.
