# Database & Persistence Implementation Guide (Project-Specific)

A focused guide explaining **every database, table, relationship, SQLAlchemy setup, Alembic migration, locking query, and testing strategy** implemented in `ParkingSimplified`.

---

## 1. Database Topology & Isolation (`scripts/init_postgres.sql`)

This project implements the **Database-per-Service** microservice pattern on a single PostgreSQL server using **4 isolated databases** and **4 dedicated roles**:

| Microservice | Port | Database | DB Role / User | Tables Owned |
|---|---:|---|---|---|
| `services/user-auth-service/` | `8001` | `user_db` | `user_auth_user` | `users`, `verification_codes` |
| `services/vehicle-service/` | `8002` | `vehicle_db` | `vehicle_user` | `vehicles` |
| `services/parking-service/` | `8003` | `parking_db` | `parking_user` | `parking_slots`, `bookings` |
| `services/payment-service/` | `8004` | `payment_db` | `payment_user` | `payments` |

How isolation is enforced in `scripts/init_postgres.sql`:
1. Creates 4 separate login roles (`user_auth_user`, `vehicle_user`, `parking_user`, `payment_user`).
2. Creates 4 databases owned by their respective roles (`CREATE DATABASE ... OWNER ...`).
3. Runs `REVOKE CONNECT ON DATABASE ... FROM PUBLIC` and `GRANT CONNECT` only to the owning role, ensuring no service can query another service's database.

---

## 2. How SQLAlchemy Connects in Every Service (`app/core/database.py`)

All 4 services use identical **synchronous SQLAlchemy 2.0** + **`psycopg` v3** boilerplate in `app/core/database.py`:

```python
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- **`DATABASE_URL`** (`postgresql+psycopg://<user>:<pass>@localhost:5432/<db>`) is loaded from `app/core/config.py` / `.env`.
- **`pool_pre_ping=True`** tests stale connections before using them.
- **`autocommit=False, autoflush=False`** ensures explicit transaction control (`db.commit()`).
- **`expire_on_commit=False`** allows accessing attributes on ORM objects (like `booking.id`) after `db.commit()` without triggering extra queries.
- **`get_db()`** is injected via FastAPI `Depends(get_db)` and guarantees `db.close()` runs after every request, even if an exception is raised.

---

## 3. Entity-Relationship Overview (6 Tables Total)

```mermaid
erDiagram
    USERS {
        uuid id PK
        string email UK
        string name
        timestamptz created_at
        timestamptz updated_at
    }
    VERIFICATION_CODES {
        uuid id PK
        string email
        string code_hash
        timestamptz expires_at
        int attempt_count
        timestamptz consumed_at
        timestamptz created_at
    }
    VEHICLES {
        uuid id PK
        uuid user_id
        string vehicle_number
        string vehicle_type
        boolean is_ev
        boolean is_active
        timestamptz created_at
    }
    PARKING_SLOTS {
        uuid id PK
        string slot_number UK
        string vehicle_type
        boolean is_charging_enabled
    }
    BOOKINGS {
        uuid id PK
        uuid user_id
        uuid vehicle_id
        string vehicle_number_snapshot
        string vehicle_type_snapshot
        boolean is_ev_snapshot
        uuid slot_id FK
        date booking_date
        time start_time
        time end_time
        boolean requires_charging
        string status
        numeric amount
        timestamptz hold_expires_at
        uuid payment_id UK
        timestamptz created_at
        timestamptz cancelled_at
    }
    PAYMENTS {
        uuid id PK
        uuid booking_id UK
        uuid user_id
        numeric amount
        string payment_method
        string status
        string transaction_id UK
        timestamptz expires_at
        timestamptz created_at
    }

    PARKING_SLOTS ||--o{ BOOKINGS : "slot_id (SQL FK in parking_db)"
```

### Foreign Key vs. Logical UUID References
- **Real SQL Foreign Key (1 total):** `bookings.slot_id` → `ForeignKey("parking_slots.id")` inside `parking_db`, because both tables live in the same database.
- **Logical Cross-Database References (No SQL FK):**
  - `vehicles.user_id` & `bookings.user_id` & `payments.user_id` → Verified from the signed **HS256 JWT** (`sub` claim).
  - `bookings.vehicle_id` → Verified over HTTP (`Parking → Vehicle`) and captured as immutable snapshots (`vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`).
  - `bookings.payment_id` & `payments.booking_id` → Synchronized over HTTP (`Parking ↔ Payment`).

---

## 4. Table-by-Table Implementation Details

### 4.1 `user_db` (`services/user-auth-service/app/models/auth.py`)
1. **`users`** (`User`): `id` (UUID PK), `email` (String(255), `unique=True`, `index=True`), `name` (String(100), nullable), `created_at`, `updated_at` (`TIMESTAMPTZ`).
2. **`verification_codes`** (`VerificationCode`): `id` (UUID PK), `email` (String(255), `index=True`), `code` mapped to DB column `code_hash` (String(255)), `expires_at` (`TIMESTAMPTZ`), `attempt_count` (Integer, default `0`), `consumed_at` (`TIMESTAMPTZ`, nullable), `created_at`.

### 4.2 `vehicle_db` (`services/vehicle-service/app/models/vehicle.py`)
1. **`vehicles`** (`Vehicle`): `id` (UUID PK), `user_id` (UUID, `index=True`), `vehicle_number` (String(20)), `vehicle_type` (String(10): `"CAR"` or `"BIKE"`), `is_ev` (Boolean, default `False`), `is_active` (Boolean, default `True`), `created_at` (`TIMESTAMPTZ`).
   - **Soft Delete:** `DELETE /api/v1/vehicles/{id}` sets `is_active = False` instead of deleting the row; `POST /api/v1/vehicles` checks duplicates only among rows where `is_active = True`.

### 4.3 `parking_db` (`services/parking-service/app/models/parking.py`)
1. **`parking_slots`** (`ParkingSlot`): `id` (UUID PK), `slot_number` (String(10), `unique=True`), `vehicle_type` (String(10)), `is_charging_enabled` (Boolean, default `False`), relationship `bookings`.
2. **`bookings`** (`Booking`): `id` (UUID PK), `user_id` (UUID, `index=True`), `vehicle_id` (UUID), `vehicle_number_snapshot` (String(20)), `vehicle_type_snapshot` (String(10)), `is_ev_snapshot` (Boolean), `slot_id` (UUID, `ForeignKey("parking_slots.id")`), `booking_date` (`Date`), `start_time` (`Time(timezone=False)`), `end_time` (`Time(timezone=False)`), `requires_charging` (Boolean), `status` (String(20): `PAYMENT_PENDING` / `CONFIRMED` / `EXPIRED` / `CANCELLED`), `amount` (`Numeric(10, 2)`), `hold_expires_at` (`TIMESTAMPTZ`, nullable), `payment_id` (UUID, `unique=True`, nullable), `created_at` (`TIMESTAMPTZ`), `cancelled_at` (`TIMESTAMPTZ`, nullable).

### 4.4 `payment_db` (`services/payment-service/app/models/payment.py`)
1. **`payments`** (`Payment`): `id` (UUID PK), `booking_id` (UUID, `unique=True`), `user_id` (UUID, `index=True`), `amount` (`Numeric(10, 2)`), `payment_method` (String(20), nullable), `status` (String(20): `PENDING` / `SUCCESS` / `FAILED`), `transaction_id` (String(100), `unique=True`, nullable), `expires_at` (`TIMESTAMPTZ`), `created_at` (`TIMESTAMPTZ`).

---

## 5. How Tables Are Created, Seeded, and Migrated

### 5.1 Automatic Startup Creation (`lifespan` in `app/main.py`)
Every service runs `Base.metadata.create_all(bind=engine)` inside its FastAPI `lifespan` hook (skipped automatically during unit tests when `get_db` is overridden):
- `user-auth-service`, `vehicle-service`, `payment-service`: create their tables automatically on startup.
- `parking-service`: creates `parking_slots` and `bookings`, then calls `seed_default_slots(db)`.

### 5.2 Automatic 100-Slot Seeding (`seed_default_slots` in `parking.py`)
If `SELECT count(id) FROM parking_slots` is `0`, `seed_default_slots(db)` inserts:
- `C01–C50`: `CAR`, `is_charging_enabled=False` (50 normal car slots)
- `C51–C60`: `CAR`, `is_charging_enabled=True` (10 EV car slots)
- `B01–B35`: `BIKE`, `is_charging_enabled=False` (35 normal bike slots)
- `B36–B40`: `BIKE`, `is_charging_enabled=True` (5 EV bike slots)

### 5.3 Alembic Migrations (`services/parking-service/alembic/`)
`parking-service` demonstrates versioned schema migrations for `parking_db`:
- `alembic.ini` — Points to `alembic/` script location.
- `alembic/env.py` — Overrides `sqlalchemy.url` with `settings.DATABASE_URL` and attaches `Base.metadata`.
- `alembic/versions/0001_create_parking_tables.py` — Implements `upgrade()` (creates `parking_slots` and `bookings` with FK) and `downgrade()` (drops `bookings` and `parking_slots`).

---

## 6. Key Database Query & Transaction Patterns in Our Code

1. **Row-Level Locking (`SELECT ... FOR UPDATE`):**
   In `services/parking-service/app/api/v1/parking.py` (`create_booking`), compatible `ParkingSlot` rows are locked with `.with_for_update()` (when `db.bind.dialect.name == "postgresql"`), serializing concurrent bookings so two threads cannot claim the same slot.
2. **Transaction Boundary Discipline:**
   `create_booking()` commits the `PAYMENT_PENDING` booking **before** calling `PaymentServiceClient.create_payment()` over HTTP, ensuring PostgreSQL locks are never held open across network calls.
3. **Half-Open Interval Overlap Query:**
   Used in `check_availability()` and `create_booking()`:
   ```python
   Booking.booking_date == booking_date,
   Booking.start_time < end_time,
   Booking.end_time > start_time,
   or_(Booking.status == "CONFIRMED", and_(Booking.status == "PAYMENT_PENDING", Booking.hold_expires_at > now_utc))
   ```
4. **In-Memory SQLite vs. Real PostgreSQL in Tests:**
   - Unit tests (`services/*/tests/test_*.py`) use `sqlite:///:memory:` with `StaticPool` and `app.dependency_overrides[get_db]`.
   - `tests/test_pg_concurrency.py` and `tests/test_e2e_journey.py` run directly against the real PostgreSQL databases.

---

## 7. Quick `psql` Inspection Commands (For Debugging / Demo)

```powershell
# Check user_db tables
psql -U user_auth_user -d user_db -c "\dt"

# Check vehicle_db tables
psql -U vehicle_user -d vehicle_db -c "SELECT id, vehicle_number, vehicle_type, is_ev, is_active FROM vehicles;"

# Check parking_db slot counts and bookings
psql -U parking_user -d parking_db -c "SELECT vehicle_type, is_charging_enabled, count(*) FROM parking_slots GROUP BY 1, 2;"
psql -U parking_user -d parking_db -c "SELECT id, status, amount, booking_date, start_time, end_time FROM bookings;"

# Check payment_db records
psql -U payment_user -d payment_db -c "SELECT id, booking_id, amount, payment_method, status, transaction_id FROM payments;"
```
