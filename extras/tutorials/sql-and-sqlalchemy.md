# SQL $\rightarrow$ SQLAlchemy 2.0 Learning Tutorial — Built From `ParkingSimplified`

> **How to read this tutorial:** For every database operation in our project, we start with **what SQL looks like first**, explain what PostgreSQL does, and then show **step-by-step how we converted that SQL into SQLAlchemy 2.0 Python code**. New terms are explained briefly in plain English the first time they appear.

---

## Course Outline (All Root Topics & Subtopics)

1. **Topic 1: Pure PostgreSQL Setup & Isolation (`init_postgres.sql`)**
   - 1.1 Why Pure SQL Comes First (Where SQLAlchemy Cannot Help)
   - 1.2 Creating Roles & Isolated Databases (`CREATE ROLE`, `CREATE DATABASE ... OWNER`)
   - 1.3 Blocking Cross-Database Access (`REVOKE CONNECT ... FROM PUBLIC`)
   - 1.4 PostgreSQL 15+ `public` Schema Permissions (`ALTER SCHEMA`, `GRANT ALL`)
2. **Topic 2: Connecting Python to SQL — Engine, Pool & Sessions (`database.py`)**
   - 2.1 How Python Talks to PostgreSQL (`psycopg` Driver vs. SQLAlchemy `Engine`)
   - 2.2 Connection Strings (`postgresql+psycopg://...`) & `pool_pre_ping=True`
   - 2.3 Converting SQL Transactions (`BEGIN` / `COMMIT` / `ROLLBACK`) into `SessionLocal`
   - 2.4 Request-Scoped Cleanup (`get_db()` with `yield`)
   - 2.5 Sync SQLAlchemy (What We Used) vs. `AsyncSession` (Alternative)
3. **Topic 3: Converting SQL `CREATE TABLE` into SQLAlchemy Models (`models/*.py`)**
   - 3.1 `CREATE TABLE` $\rightarrow$ `class TableName(Base)` (`DeclarativeBase`)
   - 3.2 SQL Column Types (`UUID`, `VARCHAR`, `NUMERIC`, `TIMESTAMPTZ`) $\rightarrow$ `Mapped[...]`
   - 3.3 SQL Constraints & `CREATE INDEX` $\rightarrow$ `mapped_column(...)` Flags
   - 3.4 SQL Defaults vs. Python Callables (`default=uuid.uuid4`, `default=utcnow`, `onupdate=utcnow`)
   - 3.5 Keeping SQL Column Name `code_hash` While Using `verification.code` in Python
4. **Topic 4: Converting SQL `FOREIGN KEY` & `JOIN` into `relationship` & `joinedload`**
   - 4.1 SQL `REFERENCES` $\rightarrow$ SQLAlchemy `ForeignKey("parking_slots.id")`
   - 4.2 Why Cross-Database `JOIN`s Don't Exist Here (Snapshot Columns Instead)
   - 4.3 `relationship(..., back_populates=...)` (Python Navigation Layer)
   - 4.4 SQL `LEFT OUTER JOIN` $\rightarrow$ `joinedload(Booking.slot)` (Fixing the N+1 Problem)
5. **Topic 5: Converting SQL CRUD (`INSERT`, `SELECT`, `UPDATE`, `DELETE`) into SQLAlchemy**
   - 5.1 SQL `INSERT INTO` $\rightarrow$ `db.add()`, `db.add_all()`, `db.commit()` & `db.refresh()`
   - 5.2 SQL `SELECT ... WHERE ... IS NULL / !=` & `ASC`/`DESC` $\rightarrow$ `select()`
   - 5.3 SQL Column Projection (`SELECT id`, `DISTINCT`), `COUNT(*)`, `OFFSET` & `LIMIT`
   - 5.4 SQL `UPDATE` (Single-Row Soft Delete & Multi-Row Bulk Invalidation) $\rightarrow$ ORM Mutation
   - 5.5 SQL `DELETE FROM ... WHERE id IN (...)` $\rightarrow$ `delete(Booking)`
6. **Topic 6: Converting Complex SQL Conditions into SQLAlchemy**
   - 6.1 SQL Time Overlap (`start_time < :end AND end_time > :start`) $\rightarrow$ `.where(...)`
   - 6.2 SQL Precedence `(status = 'CONFIRMED' OR (...))` $\rightarrow$ `or_()` & `and_()`
   - 6.3 PostgreSQL `TIMESTAMPTZ` vs. SQLite Naive `DATETIME` (`as_utc()`)
7. **Topic 7: Converting SQL Locking (`SELECT ... FOR UPDATE`) into SQLAlchemy**
   - 7.1 What Happens in Raw SQL Without a Lock (The Double-Booking Race Condition)
   - 7.2 SQL `SELECT ... FOR UPDATE` $\rightarrow$ `.with_for_update()`
   - 7.3 Making `.with_for_update()` Safe Across PostgreSQL & SQLite Tests
   - 7.4 Pessimistic Locking (`FOR UPDATE`) vs. Optimistic Locking (`VERSION` Column Alternative)
8. **Topic 8: Converting DDL Scripts into Alembic Migrations**
   - 8.1 Auto-Running DDL (`Base.metadata.create_all`) & Idempotent `INSERT` Seeding
   - 8.2 Why `create_all()` Cannot Do `ALTER TABLE` (Enter Alembic)
   - 8.3 Raw SQL `CREATE TABLE` / `DROP TABLE` $\rightarrow$ `alembic` `upgrade()` & `downgrade()`
   - 8.4 Running Alembic Commands (`upgrade head`, `current`, `downgrade`)
9. **Topic 9: Testing SQL Queries (SQLite In-Memory vs. Real PostgreSQL)**
   - 9.1 Running SQLAlchemy Against In-Memory SQLite (`StaticPool`)
   - 9.2 Proving `SELECT ... FOR UPDATE` Works on Real PostgreSQL (`test_pg_concurrency.py`)

---

## Topic 1: Pure PostgreSQL Setup & Isolation (`init_postgres.sql`)

**Subtopics in this section:**
- 1.1 Why Pure SQL Comes First (Where SQLAlchemy Cannot Help)
- 1.2 Creating Roles & Isolated Databases (`CREATE ROLE`, `CREATE DATABASE ... OWNER`)
- 1.3 Blocking Cross-Database Access (`REVOKE CONNECT ... FROM PUBLIC`)
- 1.4 PostgreSQL 15+ `public` Schema Permissions (`ALTER SCHEMA`, `GRANT ALL`)

### 1.1 Why Pure SQL Comes First (Where SQLAlchemy Cannot Help)
Before Python or SQLAlchemy can connect to anything, the **PostgreSQL server itself** needs databases and user accounts to exist. SQLAlchemy connects *into* a database (`parking_db`), so creating databases and setting server-level permissions happens in **pure SQL** (`scripts/init_postgres.sql`).

### 1.2 Creating Roles & Isolated Databases (`CREATE ROLE`, `CREATE DATABASE ... OWNER`)
* **Role**: A PostgreSQL login/user account.
* **Database-per-Service**: Each microservice gets its own completely separate database so one service can never accidentally read or lock another service's tables.

```sql
-- Pure SQL in scripts/init_postgres.sql
CREATE ROLE user_auth_user WITH LOGIN PASSWORD 'user_auth_pass';
CREATE ROLE vehicle_user   WITH LOGIN PASSWORD 'vehicle_pass';
CREATE ROLE parking_user   WITH LOGIN PASSWORD 'parking_pass';
CREATE ROLE payment_user   WITH LOGIN PASSWORD 'payment_pass';

CREATE DATABASE user_db    OWNER user_auth_user;
CREATE DATABASE vehicle_db OWNER vehicle_user;
CREATE DATABASE parking_db OWNER parking_user;
CREATE DATABASE payment_db OWNER payment_user;
```

### 1.3 Blocking Cross-Database Access (`REVOKE CONNECT ... FROM PUBLIC`)
* **`PUBLIC`**: Built-in PostgreSQL group representing *"every user on this PostgreSQL server."*
By default, PostgreSQL lets any role connect to any database. These SQL lines lock each database down so only its owning service can connect:

```sql
REVOKE CONNECT ON DATABASE parking_db FROM PUBLIC;
GRANT  CONNECT ON DATABASE parking_db TO parking_user;
```
Now, even if `vehicle_user` tries to connect to `parking_db`, PostgreSQL immediately rejects it.

### 1.4 PostgreSQL 15+ `public` Schema Permissions (`ALTER SCHEMA`, `GRANT ALL`)
* **Schema**: A namespace/folder inside a database (PostgreSQL puts tables inside the `public` schema by default).
* In PostgreSQL 15+, owning a database (`OWNER user_auth_user`) only grants `CREATE` on `public` if the `public` schema belongs to `pg_database_owner` or that user. If a database was created earlier without that ownership, running `CREATE TABLE` raises `InsufficientPrivilege: permission denied for schema public`.
* **Pure SQL Fix (run as `postgres` superuser)**:
  ```sql
  ALTER SCHEMA public OWNER TO user_auth_user;
  GRANT ALL ON SCHEMA public TO user_auth_user;
  ```

---

## Topic 2: Connecting Python to SQL — Engine, Pool & Sessions (`database.py`)

**Subtopics in this section:**
- 2.1 How Python Talks to PostgreSQL (`psycopg` Driver vs. SQLAlchemy `Engine`)
- 2.2 Connection Strings (`postgresql+psycopg://...`) & `pool_pre_ping=True`
- 2.3 Converting SQL Transactions (`BEGIN` / `COMMIT` / `ROLLBACK`) into `SessionLocal`
- 2.4 Request-Scoped Cleanup (`get_db()` with `yield`)
- 2.5 Sync SQLAlchemy (What We Used) vs. `AsyncSession` (Alternative)

### 2.1 How Python Talks to PostgreSQL (`psycopg` Driver vs. SQLAlchemy `Engine`)
* **Database Driver (`psycopg`)**: The low-level library that speaks PostgreSQL's binary network protocol over TCP port `5432`.
* **ORM (Object-Relational Mapper — SQLAlchemy 2.0)**: Sits above `psycopg` and converts Python classes/methods (`Booking`, `select(...)`, `db.commit()`) into parameterized SQL statements (automatically preventing **SQL Injection** attacks).

### 2.2 Connection Strings (`postgresql+psycopg://...`) & `pool_pre_ping=True`
In raw `psycopg`, you might manually open and close a connection every time:
```python
# Raw driver idea (slow if repeated on every API call!):
conn = psycopg.connect("postgresql://parking_user:parking_pass@localhost:5432/parking_db")
```
**How we convert that into SQLAlchemy (`services/parking-service/app/core/database.py`):**
```python
engine = create_engine(
    settings.DATABASE_URL,  # "postgresql+psycopg://parking_user:parking_pass@localhost:5432/parking_db"
    pool_pre_ping=True,
    future=True,
)
```
* **Connection Pool**: Instead of creating a brand-new TCP connection on every HTTP request, `Engine` keeps a pool of open connections ready to reuse.
* **`pool_pre_ping=True`**: Runs a quick `SELECT 1` check before reusing a pooled connection, recovering silently if PostgreSQL restarted.

### 2.3 Converting SQL Transactions (`BEGIN` / `COMMIT` / `ROLLBACK`) into `SessionLocal`
In SQL, modifying data safely looks like:
```sql
BEGIN;
INSERT INTO bookings (...) VALUES (...);
COMMIT; -- or ROLLBACK; if something went wrong
```
**How we convert that into SQLAlchemy (`database.py`):**
```python
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,        # Don't commit every statement automatically; wait for db.commit()
    autoflush=False,         # Don't send SQL before we explicitly want to
    expire_on_commit=False,  # Keep reading booking.id / booking.status after db.commit() without extra SELECTs
)
```

### 2.4 Request-Scoped Cleanup (`get_db()` with `yield`)
```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db      # Hand this request's Session to the FastAPI route
    finally:
        db.close()    # Always close & return connection to pool (even if an error occurred!)
```

### 2.5 Sync SQLAlchemy (What We Used) vs. `AsyncSession` (Alternative)
* **What we used**: Sync `Session` + `psycopg` paired with FastAPI sync `def` routes (running safely in AnyIO's worker threadpool).
* **Alternative**: `create_async_engine("postgresql+asyncpg://...")` + `AsyncSession` + `await db.execute(...)` inside `async def` routes. Sync SQLAlchemy is simpler to trace, works seamlessly with `TestClient`, and handles concurrent writes cleanly via PostgreSQL locks.

---

## Topic 3: Converting SQL `CREATE TABLE` into SQLAlchemy Models (`models/*.py`)

**Subtopics in this section:**
- 3.1 `CREATE TABLE` $\rightarrow$ `class TableName(Base)` (`DeclarativeBase`)
- 3.2 SQL Column Types (`UUID`, `VARCHAR`, `NUMERIC`, `TIMESTAMPTZ`) $\rightarrow$ `Mapped[...]`
- 3.3 SQL Constraints & `CREATE INDEX` $\rightarrow$ `mapped_column(...)` Flags
- 3.4 SQL Defaults vs. Python Callables (`default=uuid.uuid4`, `default=utcnow`, `onupdate=utcnow`)
- 3.5 Keeping SQL Column Name `code_hash` While Using `verification.code` in Python

### 3.1 `CREATE TABLE` $\rightarrow$ `class TableName(Base)` (`DeclarativeBase`)
**First, look at the SQL table we want in `vehicle_db`:**
```sql
CREATE TABLE vehicles (
    id             UUID                     NOT NULL,
    user_id        UUID                     NOT NULL,
    vehicle_number VARCHAR(20)              NOT NULL,
    vehicle_type   VARCHAR(10)              NOT NULL,
    is_ev          BOOLEAN                  NOT NULL,
    is_active      BOOLEAN                  NOT NULL,
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id)
);
CREATE INDEX ix_vehicles_user_id ON vehicles (user_id);
```

**Now look at how we converted that exact SQL into SQLAlchemy (`services/vehicle-service/app/models/vehicle.py`):**
```python
class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    vehicle_number: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_ev: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
```
* **`DeclarativeBase` (`Base`)**: Every model inherits from `Base`, registering its table schema into `Base.metadata`.
* **`__tablename__`**: Exact SQL table name (`"vehicles"`).
* **`Mapped[type]`**: Gives Python IDE autocomplete **and** tells SQLAlchemy `nullable` (`Mapped[str]` $\rightarrow$ `NOT NULL`, `Mapped[str | None]` $\rightarrow$ `NULL`).

### 3.2 SQL Column Types $\rightarrow$ SQLAlchemy `mapped_column(...)` Types

| PostgreSQL SQL Type | SQLAlchemy Python Conversion | Where We Used It | Why |
| :--- | :--- | :--- | :--- |
| `UUID` | `UUID(as_uuid=True)` | `id`, `user_id`, `slot_id` | Globally unique 128-bit IDs across microservices without a shared sequence. |
| `VARCHAR(20)` | `String(20)` | `vehicle_number`, `status` | Variable-length string capped at max length. |
| `NUMERIC(10, 2)` | `Numeric(10, 2)` | `Booking.amount`, `Payment.amount` | Exact base-10 decimal math for money (**never `FLOAT`**). |
| `DATE` | `Date` | `Booking.booking_date` | Calendar date (`2026-11-26`). |
| `TIME` | `Time(timezone=False)` | `Booking.start_time`, `end_time` | Local wall-clock time (`09:00`). |
| `TIMESTAMPTZ` | `DateTime(timezone=True)` | `created_at`, `expires_at` | Exact UTC instant in time. |

### 3.3 SQL Constraints & `CREATE INDEX` $\rightarrow$ `mapped_column(...)` Flags
* SQL `PRIMARY KEY (id)` $\rightarrow$ `primary_key=True`
* SQL `UNIQUE` (e.g., `slot_number`, `email`, `payment_id`, `booking_id`, `transaction_id`) $\rightarrow$ `unique=True`
* SQL `NOT NULL` $\rightarrow$ `nullable=False`
* SQL `CREATE INDEX ix_bookings_user_id ON bookings (user_id)` $\rightarrow$ `index=True` *(creates a fast B-Tree index so filtering by `user_id` doesn't scan the entire table).*

### 3.4 SQL Defaults vs. Python Callables (`default=uuid.uuid4`, `default=utcnow`, `onupdate=utcnow`)
In `services/user-auth-service/app/models/auth.py`:
```python
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
)
```
* **Important Python rule**: Pass `utcnow` and `uuid.uuid4` **without `()`**! That tells SQLAlchemy to execute the function fresh for every new `INSERT` (and `onupdate=utcnow` refreshes `updated_at` on every ORM `UPDATE`).

### 3.5 Keeping SQL Column Name `code_hash` While Using `verification.code` in Python
In SQL (`verification_codes` table), the column is named `code_hash`:
```sql
code_hash VARCHAR(255) NOT NULL
```
In SQLAlchemy (`services/user-auth-service/app/models/auth.py`), we map Python attribute `code` directly to that SQL column name:
```python
code: Mapped[str] = mapped_column("code_hash", String(255), nullable=False)
```
So Python code cleanly reads/writes `verification.code`, while PostgreSQL reads/writes column `code_hash`.

---

## Topic 4: Converting SQL `FOREIGN KEY` & `JOIN` into `relationship` & `joinedload`

**Subtopics in this section:**
- 4.1 SQL `REFERENCES` $\rightarrow$ SQLAlchemy `ForeignKey("parking_slots.id")`
- 4.2 Why Cross-Database `JOIN`s Don't Exist Here (Snapshot Columns Instead)
- 4.3 `relationship(..., back_populates=...)` (Python Navigation Layer)
- 4.4 SQL `LEFT OUTER JOIN` $\rightarrow$ `joinedload(Booking.slot)` (Fixing the N+1 Problem)

### 4.1 SQL `REFERENCES` $\rightarrow$ SQLAlchemy `ForeignKey("parking_slots.id")`
**Raw SQL in `parking_db`:**
```sql
slot_id UUID NOT NULL REFERENCES parking_slots (id)
```
**Converted to SQLAlchemy (`services/parking-service/app/models/parking.py`):**
```python
slot_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), ForeignKey("parking_slots.id"), nullable=False
)
```
PostgreSQL blocks any `INSERT` into `bookings` whose `slot_id` doesn't exist in `parking_slots`.

### 4.2 Why Cross-Database `JOIN`s Don't Exist Here (Snapshot Columns Instead)
Notice `Booking` has `user_id` and `vehicle_id`, **but neither has `ForeignKey(...)`!**
Why? Because `users` is in `user_db` and `vehicles` is in `vehicle_db`, and PostgreSQL cannot enforce foreign keys or `JOIN` across separate databases.
Instead, `bookings` stores `vehicle_number_snapshot`, `vehicle_type_snapshot`, and `is_ev_snapshot` at booking time—eliminating cross-service `JOIN` needs completely!

### 4.3 `relationship(..., back_populates=...)` (Python Navigation Layer)
`ForeignKey` tells PostgreSQL how rows link; `relationship(...)` lets Python jump straight from a `Booking` object to its `ParkingSlot` object (`booking.slot.slot_number`):
```python
# ParkingSlot side:
bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="slot")

# Booking side:
slot: Mapped["ParkingSlot"] = relationship("ParkingSlot", back_populates="bookings")
```

### 4.4 SQL `LEFT OUTER JOIN` $\rightarrow$ `joinedload(Booking.slot)` (Fixing the N+1 Problem)
**What happens without `joinedload` (The N+1 Query Problem):**
If you run `SELECT * FROM bookings WHERE user_id = :uid` (20 rows) and then access `b.slot.slot_number` inside a loop, SQLAlchemy runs **20 extra `SELECT * FROM parking_slots WHERE id = ...` queries** (1 + 20 = 21 round-trips!).

**First, the optimal SQL we actually want:**
```sql
SELECT bookings.*, parking_slots.*
FROM bookings
LEFT OUTER JOIN parking_slots ON parking_slots.id = bookings.slot_id
WHERE bookings.user_id = :user_id
ORDER BY bookings.created_at DESC
LIMIT 20 OFFSET 0;
```
**How we convert that `LEFT OUTER JOIN` into SQLAlchemy (`services/parking-service/app/api/v1/parking.py`):**
```python
select(Booking)
.options(joinedload(Booking.slot))
.where(Booking.user_id == auth.user_id)
.order_by(desc(Booking.created_at))
.offset((page - 1) * page_size)
.limit(page_size)
```
Adding `.options(joinedload(Booking.slot))` tells SQLAlchemy to emit that single `LEFT OUTER JOIN` SQL query instead of 21 separate queries!

---

## Topic 5: Converting SQL CRUD (`INSERT`, `SELECT`, `UPDATE`, `DELETE`) into SQLAlchemy

**Subtopics in this section:**
- 5.1 SQL `INSERT INTO` $\rightarrow$ `db.add()`, `db.add_all()`, `db.commit()` & `db.refresh()`
- 5.2 SQL `SELECT ... WHERE ... IS NULL / !=` & `ASC`/`DESC` $\rightarrow$ `select()`
- 5.3 SQL Column Projection (`SELECT id`, `DISTINCT`), `COUNT(*)`, `OFFSET` & `LIMIT`
- 5.4 SQL `UPDATE` (Single-Row Soft Delete & Multi-Row Bulk Invalidation) $\rightarrow$ ORM Mutation
- 5.5 SQL `DELETE FROM ... WHERE id IN (...)` $\rightarrow$ `delete(Booking)`

### 5.1 SQL `INSERT INTO` $\rightarrow$ `db.add()`, `db.add_all()`, `db.commit()` & `db.refresh()`
**Raw SQL:**
```sql
INSERT INTO vehicles (id, user_id, vehicle_number, vehicle_type, is_ev, is_active, created_at)
VALUES (:id, :user_id, :vehicle_number, :vehicle_type, :is_ev, true, :created_at);
```
**Converted to SQLAlchemy (`services/vehicle-service/app/api/v1/vehicles.py`):**
```python
vehicle = Vehicle(
    user_id=user_id,
    vehicle_number=payload.vehicle_number,
    vehicle_type=payload.vehicle_type,
    is_ev=payload.is_ev,
    is_active=True,
)
db.add(vehicle)      # Stage object in Python session
db.commit()          # Execute INSERT + COMMIT in PostgreSQL
db.refresh(vehicle)  # Sync DB-generated defaults back onto vehicle
```
* **Batch insert (`seed_default_slots`)**: Instead of calling `db.add()` 100 times, `db.add_all(slots)` + one `db.commit()` inserts all 100 `ParkingSlot` rows (`C01`–`C60`, `B01`–`B40`) in one transaction.

### 5.2 SQL `SELECT ... WHERE ... IS NULL / !=` & `ASC`/`DESC` $\rightarrow$ `select()`
**Raw SQL (`user-auth-service` fetching latest unused OTP):**
```sql
SELECT *
FROM verification_codes
WHERE email = :email
  AND consumed_at IS NULL
ORDER BY created_at DESC
LIMIT 1;
```
**Converted to SQLAlchemy (`services/user-auth-service/app/api/v1/auth.py`):**
```python
verification = db.execute(
    select(VerificationCode)
    .where(
        VerificationCode.email == email,
        VerificationCode.consumed_at.is_(None),
    )
    .order_by(desc(VerificationCode.created_at))
    .limit(1)
).scalar_one_or_none()
```
* **Not-Equal Filter (`!=` / `<>`) on Update Duplicate Check** (`services/vehicle-service/app/api/v1/vehicles.py`):
  * **Raw SQL**: `SELECT * FROM vehicles WHERE user_id = :uid AND vehicle_number = :plate AND is_active IS true AND id <> :current_id;`
  * **Converted to SQLAlchemy**: `Vehicle.id != vehicle.id` inside `.where(...)` (so updating your own vehicle doesn't trigger a false duplicate error against itself!).
* **Ascending vs. Descending Sort**: `.order_by(Vehicle.created_at.asc())` (`ORDER BY created_at ASC`) vs. `.order_by(desc(Booking.created_at))` (`ORDER BY created_at DESC`).
* **Watch out for SQL `NULL`!** In SQL, `consumed_at = NULL` is invalid (`IS NULL` is required). So in SQLAlchemy, always use `.is_(None)` (and `.is_(True)` for booleans), **not** `== None`.
* **Result extractors**:
  * `.scalar_one_or_none()` $\rightarrow$ expects 0 or 1 row (returns `None` if missing).
  * `.scalars().all()` $\rightarrow$ returns a `list` of all matching objects/values.
  * `db.get(User, user_id)` $\rightarrow$ shortcut for `SELECT * FROM users WHERE id = :user_id`.

### 5.3 SQL Column Projection (`SELECT id`, `DISTINCT`), `COUNT(*)`, `OFFSET` & `LIMIT`
Instead of always writing `SELECT *` (which fetches every column), when we only need IDs or an existence check, we select **only one column** (**Projection**):
* **Existence Check (`user_overlap` in `parking.py`)**:
  * **Raw SQL**: `SELECT id FROM bookings WHERE user_id = :uid AND ... LIMIT 1;`
  * **Converted to SQLAlchemy**: `select(Booking.id).where(...).limit(1)`
* **Distinct Occupied Slots (`parking.py`)**:
  * **Raw SQL**: `SELECT DISTINCT slot_id FROM bookings WHERE slot_id IN (...) AND ...;`
  * **Converted to SQLAlchemy**: `select(Booking.slot_id).where(Booking.slot_id.in_(compatible_slot_ids), ...).distinct()`
* **Total Count for Pagination (`parking.py`)**:
  * **Raw SQL**: `SELECT count(id) FROM bookings WHERE user_id = :user_id;`
  * **Converted to SQLAlchemy**:
    ```python
    total_items = db.execute(
        select(func.count(Booking.id)).where(Booking.user_id == auth.user_id)
    ).scalar_one()
    ```

### 5.4 SQL `UPDATE` (Single-Row Soft Delete & Multi-Row Bulk Invalidation) $\rightarrow$ ORM Mutation
**Pattern A — Single-Row Soft Delete (Raw SQL):**
```sql
UPDATE vehicles SET is_active = false WHERE id = :vehicle_id;
```
**Converted to SQLAlchemy (`services/vehicle-service/app/api/v1/vehicles.py`):**
```python
vehicle = _get_owned_active_vehicle(db, vehicle_id, user_id)
vehicle.is_active = False
db.commit()
```
Because `vehicle` was loaded inside `db`, SQLAlchemy tracks changes to its attributes automatically and emits the exact `UPDATE` SQL on `db.commit()`.

**Pattern B — Multi-Row Update (`send_company_code` in `auth.py` & `_expire_stale_holds` in `parking.py`):**
* **Raw SQL**: `UPDATE verification_codes SET consumed_at = :now WHERE email = :email AND consumed_at IS NULL;`
* **Converted to SQLAlchemy**: Query the matching rows (`old_codes = db.execute(...).scalars().all()`), mutate each row (`row.consumed_at = now`), and commit once (`if changed: db.commit()` in `_expire_stale_holds`, avoiding unnecessary DB writes when nothing expired!).

### 5.5 SQL `DELETE FROM ... WHERE id IN (...)` $\rightarrow$ `delete(Booking)`
**Raw SQL (cleaning up test rows in `parking_db`):**
```sql
DELETE FROM bookings WHERE user_id IN (:u1, :u2, ...);
```
**Converted to SQLAlchemy (`tests/test_pg_concurrency.py`):**
```python
db.execute(delete(Booking).where(Booking.user_id.in_(user_ids)))
db.commit()
```

---

## Topic 6: Converting Complex SQL Conditions into SQLAlchemy

**Subtopics in this section:**
- 6.1 SQL Time Overlap (`start_time < :end AND end_time > :start`) $\rightarrow$ `.where(...)`
- 6.2 SQL Precedence `(status = 'CONFIRMED' OR (...))` $\rightarrow$ `or_()` & `and_()`
- 6.3 PostgreSQL `TIMESTAMPTZ` vs. SQLite Naive `DATETIME` (`as_utc()`)

### 6.1 SQL Time Overlap (`start_time < :end AND end_time > :start`) $\rightarrow$ `.where(...)`
**Raw SQL to detect whether an existing booking overlaps `[req_start, req_end)`:**
```sql
WHERE booking_date = :req_date
  AND start_time < :req_end
  AND end_time   > :req_start
```
**Converted to SQLAlchemy (`services/parking-service/app/api/v1/parking.py`):**
```python
.where(
    Booking.booking_date == payload.date,
    Booking.start_time < payload.end_time,
    Booking.end_time > payload.start_time,
)
```
* **Why `<` and `>` (not `<=` and `>=`)?** Back-to-back bookings (`09:00–11:00` and `11:00–13:00`) evaluate `11:00 > 11:00` (`False`), so back-to-back bookings are allowed cleanly!

### 6.2 SQL Precedence `(status = 'CONFIRMED' OR (...))` $\rightarrow$ `or_()` & `and_()`
**Raw SQL for determining if a booking still blocks a slot (Lazy Hold Expiry):**
```sql
AND (
    status = 'CONFIRMED'
    OR (status = 'PAYMENT_PENDING' AND hold_expires_at > :now_utc)
)
```
**Converted to SQLAlchemy (`services/parking-service/app/api/v1/parking.py`):**
```python
def _active_booking_filter(now_utc: datetime):
    return or_(
        Booking.status == "CONFIRMED",
        and_(Booking.status == "PAYMENT_PENDING", Booking.hold_expires_at > now_utc),
    )
```
* Multiple arguments inside `.where(A, B)` are joined by `AND`; whenever you need `OR` or nested parentheses, use SQLAlchemy's `or_(...)` and `and_(...)` helpers!

### 6.3 PostgreSQL `TIMESTAMPTZ` vs. SQLite Naive `DATETIME` (`as_utc()`)
* PostgreSQL `DateTime(timezone=True)` returns **aware** datetimes (`tzinfo=UTC`), whereas SQLite returns **naive** datetimes (`tzinfo=None`).
* Comparing aware vs. naive in Python raises `TypeError`, so `as_utc()` in `clock.py`, `auth.py`, and `payments.py` attaches `timezone.utc` whenever `dt.tzinfo is None`.

---

## Topic 7: Converting SQL Locking (`SELECT ... FOR UPDATE`) into SQLAlchemy

**Subtopics in this section:**
- 7.1 What Happens in Raw SQL Without a Lock (The Double-Booking Race Condition)
- 7.2 SQL `SELECT ... FOR UPDATE` $\rightarrow$ `.with_for_update()`
- 7.3 Making `.with_for_update()` Safe Across PostgreSQL & SQLite Tests
- 7.4 Pessimistic Locking (`FOR UPDATE`) vs. Optimistic Locking (`VERSION` Column Alternative)

### 7.1 What Happens in Raw SQL Without a Lock (The Double-Booking Race Condition)
Suppose only 1 EV bike slot (`B40`) is free at `10:00–11:00`, and User A and User B click "Book" simultaneously:
1. Session A runs `SELECT slot_id FROM bookings ...` $\rightarrow$ sees `B40` is free.
2. Session B runs `SELECT slot_id FROM bookings ...` $\rightarrow$ **also** sees `B40` is free!
3. Both A and B run `INSERT INTO bookings (slot_id='B40', ...)` $\rightarrow$ **Double-booked!**

### 7.2 SQL `SELECT ... FOR UPDATE` $\rightarrow$ `.with_for_update()`
**First, the Raw PostgreSQL SQL that fixes this:**
```sql
SELECT *
FROM parking_slots
WHERE vehicle_type = 'BIKE'
  AND is_charging_enabled IS true
ORDER BY slot_number ASC
FOR UPDATE;
```
**How we converted that into SQLAlchemy (`services/parking-service/app/api/v1/parking.py`):**
```python
slot_stmt = (
    select(ParkingSlot)
    .where(
        ParkingSlot.vehicle_type == vehicle.vehicle_type,
        ParkingSlot.is_charging_enabled.is_(payload.requires_charging),
    )
    .order_by(ParkingSlot.slot_number.asc())
)
if db.bind is not None and db.bind.dialect.name == "postgresql":
    slot_stmt = slot_stmt.with_for_update()

compatible_slots = list(db.execute(slot_stmt).scalars().all())
```
* **How PostgreSQL executes `FOR UPDATE`**: Session A acquires row-level locks on `B36`–`B40`. Session B **waits** at `FOR UPDATE` until Session A commits its new `Booking` row, then Session B reads the updated `bookings` table, sees `B40` is taken, and returns `409 NO_PARKING_CAPACITY`.

### 7.3 Making `.with_for_update()` Safe Across PostgreSQL & SQLite Tests
SQLite does not support `FOR UPDATE` syntax. Checking `db.bind.dialect.name == "postgresql"` ensures `.with_for_update()` runs on PostgreSQL (production + `test_pg_concurrency.py`) while SQLite unit tests (`test_parking.py`) still pass cleanly.

### 7.4 Pessimistic Locking (`FOR UPDATE`) vs. Optimistic Locking (Alternative)
* **Pessimistic (`FOR UPDATE`) — What We Used**: Locks compatible slot rows upfront until `COMMIT`. Best when multiple employees rush the last few EV slots simultaneously.
* **Optimistic Locking (Alternative)**: Adds a `version` column and executes `UPDATE ... SET version = version + 1 WHERE id = :id AND version = :old_version`, retrying on `0` updated rows.

---

## Topic 8: Converting DDL Scripts into Alembic Migrations

**Subtopics in this section:**
- 8.1 Auto-Running DDL (`Base.metadata.create_all`) & Idempotent `INSERT` Seeding
- 8.2 Why `create_all()` Cannot Do `ALTER TABLE` (Enter Alembic)
- 8.3 Raw SQL `CREATE TABLE` / `DROP TABLE` $\rightarrow$ `alembic` `upgrade()` & `downgrade()`
- 8.4 Running Alembic Commands (`upgrade head`, `current`, `downgrade`)

### 8.1 Auto-Running DDL (`Base.metadata.create_all`) & Idempotent `INSERT` Seeding
* **DDL (Data Definition Language)**: SQL commands that create/modify table structures (`CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`).
* On service startup, `Base.metadata.create_all(bind=engine)` runs `CREATE TABLE IF NOT EXISTS` for every model, and `seed_default_slots()` checks `COUNT(id) == 0` before inserting `C01`–`C60` and `B01`–`B40`.

### 8.2 Why `create_all()` Cannot Do `ALTER TABLE` (Enter Alembic)
If `bookings` already exists in PostgreSQL and you add a new column in Python, `create_all()` ignores existing tables. **Alembic** tracks schema versions (`alembic_version` table) so you can run `ALTER TABLE` upgrades and `downgrade` rollbacks safely.

### 8.3 Raw SQL `CREATE TABLE` / `DROP TABLE` $\rightarrow$ `alembic` `upgrade()` & `downgrade()`
**Raw SQL we want for `parking_db`:**
```sql
CREATE TABLE parking_slots ( ... );
CREATE TABLE bookings ( ... slot_id UUID NOT NULL REFERENCES parking_slots(id) ... );
-- Rollback:
DROP TABLE bookings;
DROP TABLE parking_slots;
```
**Converted to Alembic Python (`services/parking-service/alembic/versions/0001_create_parking_tables.py`):**
```python
def upgrade() -> None:
    op.create_table(
        "parking_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slot_number", sa.String(10), nullable=False, unique=True),
        sa.Column("vehicle_type", sa.String(10), nullable=False),
        sa.Column("is_charging_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_table(
        "bookings",
        ...,
        sa.Column("slot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parking_slots.id"), nullable=False),
        ...,
    )

def downgrade() -> None:
    op.drop_table("bookings")       # Drop child table first (because of FK to parking_slots!)
    op.drop_table("parking_slots")
```

### 8.4 Running Alembic Commands (`upgrade head`, `current`, `downgrade`)
Run inside `services\parking-service` (configured via `alembic.ini` and `alembic/env.py`):
```powershell
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m alembic current
..\..\.venv\Scripts\python.exe -m alembic downgrade -1
```

---

## Topic 9: Testing SQL Queries (SQLite In-Memory vs. Real PostgreSQL)

**Subtopics in this section:**
- 9.1 Running SQLAlchemy Against In-Memory SQLite (`StaticPool`)
- 9.2 Proving `SELECT ... FOR UPDATE` Works on Real PostgreSQL (`test_pg_concurrency.py`)

### 9.1 Running SQLAlchemy Against In-Memory SQLite (`StaticPool`)
Because our business logic uses standard SQLAlchemy `select(...)`, `add()`, and `commit()`, unit tests swap PostgreSQL for an in-memory SQLite engine (`test_auth.py`, `test_vehicles.py`, `test_parking.py`, `test_payments.py`):
```python
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
```
* **`StaticPool`**: Keeps the single in-memory SQLite database alive across multiple `get_db()` calls within one test.

### 9.2 Proving `SELECT ... FOR UPDATE` Works on Real PostgreSQL (`test_pg_concurrency.py`)
Only real PostgreSQL proves `FOR UPDATE` prevents double-booking:
* `test_pg_ev_bike_slot_race_no_double_allocation()` uses `threading.Barrier(10)` + `ThreadPoolExecutor(10)` against real `parking_db`.
* 10 concurrent users request the 5 EV bike slots (`B36`–`B40`) at the exact same millisecond $\rightarrow$ **5 succeed (`201`) with 5 unique slots**, and **5 fail cleanly (`409 NO_PARKING_CAPACITY`)**, followed by `delete(Booking).where(Booking.user_id.in_(user_ids))` cleanup.
