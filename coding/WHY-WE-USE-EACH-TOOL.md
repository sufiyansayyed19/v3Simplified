# Why We Use Each Tool & Concept (With Project Examples)

A plain-English learning guide explaining **why** each package and backend pattern exists in our Corporate Parking Reservation System—using real examples from our codebase.

---

## 1. FastAPI — The Web Framework
- **Problem it solves:** Turning Python functions into HTTP REST APIs with automatic JSON parsing, validation, authentication dependencies, and interactive Swagger docs (`/docs`).
- **Project example:** In `services/vehicle-service/app/api/v1/vehicles.py`, writing:
  ```python
  @router.post("", response_model=VehicleResponse, status_code=201)
  def create_vehicle(payload: VehicleCreate, user_id: uuid.UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
  ```
  automatically validates the JSON body, checks the HS256 JWT via `Depends`, opens/closes a DB session, formats the response, and generates `/docs`.

---

## 2. Uvicorn — The Server That Runs FastAPI
- **Problem it solves:** FastAPI is Python code; it needs an ASGI web server to listen on network ports (`8001`–`8004`).
- **Project example:** `python -m uvicorn app.main:app --port 8001 --reload` opens port `8001` for `user-auth-service`.

---

## 3. SQLAlchemy (Synchronous `Session`) — Talking to PostgreSQL in Python
- **Problem it solves:** Lets you work with Python classes (`User`, `Vehicle`, `ParkingSlot`, `Booking`, `Payment`), automatically creates tables on startup via `Base.metadata.create_all(bind=engine)`, and manages transactions safely.
- **Project example:** In `parking-service`, SQLAlchemy lets us lock compatible slot rows during booking creation so two users cannot double-book the same slot:
  ```python
  slot_stmt = select(ParkingSlot).where(...).order_by(ParkingSlot.slot_number.asc()).with_for_update()
  ```
  And our `get_db()` dependency guarantees `db.close()` always runs after every request.

---

## 4. `psycopg` (v3) — The PostgreSQL Driver
- **Problem it solves:** SQLAlchemy is an ORM, not a network driver. `psycopg` is the PostgreSQL driver that speaks PostgreSQL's protocol over TCP port `5432`.
- **Project example:** Every service's `DATABASE_URL` starts with `postgresql+psycopg://...`.

---

## 5. Alembic — Version Control for Database Schemas (Demonstrated in `parking-service`)
- **Problem it solves:** While `Base.metadata.create_all(bind=engine)` is great for creating new tables on startup, in a core relational database with multiple linked tables (`parking_slots` and `bookings` connected by a Foreign Key), you want versioned schema migrations (`upgrade()` and `downgrade()`).
- **Project example:** `services/parking-service/alembic/versions/0001_create_parking_tables.py` defines `upgrade()` and `downgrade()` for `parking_slots` and `bookings`.

---

## 6. Pydantic & `pydantic-settings` — Strict Input Validation & Config
- **Problem it solves:**
  1. **Pydantic** stops invalid data before it reaches the database and keeps API JSON shapes separate from internal DB models.
  2. **`pydantic-settings`** loads `.env` settings into typed Python objects (`app/core/config.py`).
- **Project example:** When a user sends `{"vehicle_number": "mh 12-ab 1234", "vehicle_type": "CAR", "is_ev": true}`, `VehicleCreate` normalizes the plate to `"MH12AB1234"` automatically.

---

## 7. `email-validator` — Validating Email Addresses
- **Problem it solves:** Checks whether an email address has valid syntax when using Pydantic's `EmailStr`.
- **Project example:** In `user-auth-service`, `email: EmailStr` on `SendCodeRequest` rejects malformed emails with `422` before checking `COMPANY_EMAIL_DOMAIN`.

---

## 8. `httpx` — Making HTTP Calls Between Microservices
- **Problem it solves:** In a microservice architecture, services own separate databases (`vehicle_db`, `parking_db`, `payment_db`) and communicate over HTTP.
- **Project examples (3 inter-service calls):**
  1. **Parking (`8003`) → Vehicle (`8002`):** Calls `GET /api/v1/vehicles/{id}` to verify the vehicle belongs to the user and check `is_ev` / `vehicle_type`.
  2. **Parking (`8003`) → Payment (`8004`):** Calls `POST /internal/v1/payments` to create a `PENDING` payment record for a new booking.
  3. **Payment (`8004`) → Parking (`8003`):** Calls `POST /internal/v1/bookings/{id}/payment-result` after payment is processed to confirm the booking.

---

## 9. `PyJWT` — HS256 JWT Authentication
- **Problem it solves:** Allows stateless authentication across all 4 microservices without every service needing to query `user_db`.
- **How it works:**
  - `user-auth-service` signs a JWT containing `{"sub": str(user_id), "exp": ...}` using `JWT_SECRET_KEY` and `HS256`.
  - `vehicle-service`, `parking-service`, and `payment-service` verify the token signature using `JWT_SECRET_KEY` and extract `user_id` from `"sub"`.

---

## 10. Key Backend Patterns Used (Great for Architecture Evaluation)

| Pattern | Why We Use It | Concrete Example in Our Project |
|---|---|---|
| **Database-per-Service** | True microservice isolation (`user_db`, `vehicle_db`, `parking_db`, `payment_db`). | Services never query another service's database directly; they talk over HTTP using `httpx`. |
| **Row Locking (`SELECT ... FOR UPDATE`)** | Prevents double-booking when multiple users book at the exact same moment. | `parking-service` locks compatible `ParkingSlot` rows inside the transaction while checking overlaps and picking a free slot. |
| **Vehicle Snapshots on `bookings`** | Since `vehicles` live in `vehicle_db` and `bookings` live in `parking_db`, storing a snapshot preserves booking history even if a vehicle is later edited or deactivated. | `bookings` stores `vehicle_number_snapshot`, `vehicle_type_snapshot`, and `is_ev_snapshot` at booking time. |
| **`X-Internal-Service-Token`** | Protects `/internal/v1/*` endpoints so external users cannot fake a payment callback. | `Parking ↔ Payment` pass `X-Internal-Service-Token: dev-internal-service-token` on internal calls. |
| **Lazy Hold Expiry** | Avoids needing a background cron/Celery worker to expire unpaid 5-minute holds. | Availability queries ignore `hold_expires_at <= now()`, and reads/callbacks flip expired holds to `EXPIRED` on access. |
