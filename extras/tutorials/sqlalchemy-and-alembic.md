# SQLAlchemy + Alembic Migrations Tutorial — Built From `ParkingSimplified`

> **How to use this tutorial:** This tutorial connects **SQLAlchemy 2.0** (how we define tables and run queries in Python) directly to **Alembic** (how we safely evolve PostgreSQL schemas over time without losing data). Every file path and pattern comes directly from `services/parking-service/`, with plain-English explanations for every new term.

---

## Course Outline (All Root Topics & Subtopics)

1. **Topic 1: How SQLAlchemy & Alembic Work Together**
   - 1.1 What is `Base.metadata` (`DeclarativeBase`)?
   - 1.2 Why `import app.models  # noqa: F401` Is Critical for Both `create_all` and Alembic
   - 1.3 Why `Base.metadata.create_all()` Is Not Enough in Production (Enter Alembic)
2. **Topic 2: SQLAlchemy Internals Used by Alembic (`Engine`, `Session`, `Pool`)**
   - 2.1 `create_engine` vs. `engine_from_config`
   - 2.2 Connection Pooling in App (`pool_pre_ping=True`) vs. `NullPool` in Alembic (`env.py`)
   - 2.3 Transactional DDL in PostgreSQL (`context.begin_transaction()`)
   - 2.4 Python `default=...` vs. SQL `server_default=sa.text(...)`
3. **Topic 3: Inside `ParkingSimplified`'s Alembic Folder (`services/parking-service/`)**
   - 3.1 `alembic.ini` — Configuration, `prepend_sys_path`, Logging & Fallback URL
   - 3.2 `alembic/env.py` — Wiring `settings.DATABASE_URL` and `Base.metadata`
   - 3.3 `alembic/script.py.mako` — How New Migration Files Are Templated
   - 3.4 How PostgreSQL Tracks Applied Migrations (`alembic_version` Table)
4. **Topic 4: Anatomy of a Migration Revision (`0001_create_parking_tables.py`)**
   - 4.1 Revision Headers (`revision`, `down_revision`, Linked Chain)
   - 4.2 Writing `upgrade()` (`op.create_table`, `sa.Column`, `postgresql.UUID`, `sa.ForeignKey`)
   - 4.3 Writing `downgrade()` (Reverse Dependency Order & Safe Rollback)
5. **Topic 5: Real-World Schema Evolution Walkthrough (Adding a Column End-to-End)**
   - 5.1 Step 1: Update the SQLAlchemy Model (`app/models/parking.py`)
   - 5.2 Step 2: Generate a Migration (`alembic revision --autogenerate`)
   - 5.3 Step 3: Inspect & Fix the Generated Revision File
   - 5.4 Step 4: Apply (`alembic upgrade head`) & Roll Back (`alembic downgrade -1`)
6. **Topic 6: Essential Alembic Operations (`op.*`) & Autogenerate Gotchas**
   - 6.1 Most Common `op.*` Commands (`add_column`, `alter_column`, `create_index`, `execute`)
   - 6.2 What `--autogenerate` Detects vs. What It Misses (5 Classic Traps)
7. **Topic 7: Using `create_all()` + Alembic Together (`stamp head` & Best Practices)**
   - 7.1 `ParkingSimplified` Dual Setup: Instant Dev Boot (`create_all`) vs. Versioned Migrations (`alembic`)
   - 7.2 Fixing "Table Already Exists" When Adopting Alembic (`alembic stamp head`)
   - 7.3 Essential Alembic CLI Command Cheat Sheet

---

## Topic 1: How SQLAlchemy & Alembic Work Together

**Subtopics in this section:**
- 1.1 What is `Base.metadata` (`DeclarativeBase`)?
- 1.2 Why `import app.models  # noqa: F401` Is Critical for Both `create_all` and Alembic
- 1.3 Why `Base.metadata.create_all()` Is Not Enough in Production (Enter Alembic)

### 1.1 What is `Base.metadata` (`DeclarativeBase`)?
* **`DeclarativeBase`**: The base class we define in `app/core/database.py`:
  ```python
  class Base(DeclarativeBase):
      pass
  ```
* **`MetaData` (`Base.metadata`)**: Think of `Base.metadata` as an **in-memory blueprint catalog** owned by `Base`. Every time Python loads a class inheriting from `Base` (`class ParkingSlot(Base)`, `class Booking(Base)`), SQLAlchemy automatically registers that table's name, columns, types, unique constraints, indexes, and foreign keys inside `Base.metadata.tables`.
* Both `create_all()` (at FastAPI startup) and **Alembic** (during migrations) read this exact `Base.metadata` blueprint!

### 1.2 Why `import app.models  # noqa: F401` Is Critical for Both `create_all` and Alembic
Look at `services/user-auth-service/app/main.py` and `services/parking-service/alembic/env.py`:
```python
from app.core.database import Base
import app.models  # noqa: F401
```
* **What happens if you forget `import app.models`?**
  If Python has never imported `app/models/parking.py`, the `ParkingSlot` and `Booking` classes haven't executed yet—so `Base.metadata.tables` is **completely empty**!
  * `create_all()` would silently create **zero tables**.
  * `alembic revision --autogenerate` would think you deleted all tables and generate `op.drop_table("bookings")`!
* **`# noqa: F401`**: Tells Python linters (like Ruff/Flake8) *"Don't warn me that `app.models` looks unused—importing it registers all models onto `Base.metadata`!"*

### 1.3 Why `Base.metadata.create_all()` Is Not Enough in Production (Enter Alembic)
`Base.metadata.create_all(bind=engine)` only runs `CREATE TABLE IF NOT EXISTS ...`. It has two fatal gaps for live applications:
1. **Cannot modify existing tables**: Suppose `bookings` is already in PostgreSQL with 50,000 live employee bookings, and you add `gate_number: Mapped[str | None]` to `Booking`. Running `create_all()` sees `bookings` already exists and **does nothing**—your app then crashes on the first query with `column bookings.gate_number does not exist`!
2. **Cannot roll back safely**: If a bad deployment changes a column type and fails, `create_all()` has no undo button.

* **Alembic**: SQLAlchemy's official **database schema migration tool**. Think of Alembic as **Git for your database structure**—every schema change is stored as a numbered Python file with an `upgrade()` (apply forward) and `downgrade()` (undo backward) function.

---

## Topic 2: SQLAlchemy Internals Used by Alembic (`Engine`, `Session`, `Pool`)

**Subtopics in this section:**
- 2.1 `create_engine` vs. `engine_from_config`
- 2.2 Connection Pooling in App (`pool_pre_ping=True`) vs. `NullPool` in Alembic (`env.py`)
- 2.3 Transactional DDL in PostgreSQL (`context.begin_transaction()`)
- 2.4 Python `default=...` vs. SQL `server_default=sa.text(...)`

### 2.1 `create_engine` vs. `engine_from_config`
* In our FastAPI app (`app/core/database.py`), we create the SQLAlchemy `Engine` directly from Python settings:
  ```python
  engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
  ```
* In `services/parking-service/alembic/env.py`, Alembic uses `engine_from_config(...)`:
  ```python
  connectable = engine_from_config(
      config.get_section(config.config_ini_section, {}),
      prefix="sqlalchemy.",
      poolclass=pool.NullPool,
  )
  ```
  `engine_from_config` reads all keys starting with `sqlalchemy.` (like `sqlalchemy.url`) from `alembic.ini` (after we override it with `settings.DATABASE_URL`) and builds an SQLAlchemy `Engine`.

### 2.2 Connection Pooling in App (`pool_pre_ping=True`) vs. `NullPool` in Alembic (`env.py`)
* **Connection Pool**: A cache of open PostgreSQL TCP connections kept alive so a web server handles thousands of requests rapidly without reconnecting each time.
* **Why does our app use pooling (`pool_pre_ping=True`), while Alembic uses `pool.NullPool`?**
  * **FastAPI App**: Stays running for hours/days serving repeated requests $\rightarrow$ **reuse pooled connections**, using `pool_pre_ping=True` (`SELECT 1`) to catch dropped connections.
  * **Alembic CLI**: Starts, runs 1 migration script in ~1 second, and exits immediately $\rightarrow$ keeping a pool open makes zero sense. `NullPool` closes the PostgreSQL connection the moment the `with connectable.connect()` block exits.

### 2.3 Transactional DDL in PostgreSQL (`context.begin_transaction()`)
* **Transactional DDL**: Unlike MySQL (where `CREATE TABLE` auto-commits immediately and cannot roll back), **PostgreSQL supports running `CREATE TABLE` / `ALTER TABLE` inside a transaction**!
* Look at `services/parking-service/alembic/env.py`:
  ```python
  with connectable.connect() as connection:
      context.configure(connection=connection, target_metadata=target_metadata)
      with context.begin_transaction():
          context.run_migrations()
  ```
  If step 2 of a 3-step migration fails in PostgreSQL, `context.begin_transaction()` rolls back step 1 cleanly so your database is never left half-migrated!

### 2.4 Python `default=...` vs. SQL `server_default=sa.text(...)`
Look closely at the difference between our ORM model (`models/parking.py`) and our Alembic migration (`0001_create_parking_tables.py`):

| Setting | Where Defined | Who Computes the Value? | Example in `ParkingSimplified` |
| :--- | :--- | :--- | :--- |
| `default=False` / `default=utcnow` | SQLAlchemy ORM (`models/parking.py`) | **Python / SQLAlchemy** inserts the value when you run `db.add(obj)`. | `status: ... default="PAYMENT_PENDING"` |
| `server_default=sa.text("false")` | PostgreSQL DDL (`0001_create_parking_tables.py`) | **PostgreSQL itself** fills in the default even if someone runs raw `INSERT INTO` in `psql`. | `sa.Column("is_charging_enabled", sa.Boolean(), server_default=sa.text("false"))` |

* **Rule of thumb**: When adding a **new `NOT NULL` column to a table that already has existing rows**, PostgreSQL **requires** a `server_default` (otherwise PostgreSQL doesn't know what value to put into the existing rows!).

---

## Topic 3: Inside `ParkingSimplified`'s Alembic Folder (`services/parking-service/`)

**Subtopics in this section:**
- 3.1 `alembic.ini` — Configuration, `prepend_sys_path`, Logging & Fallback URL
- 3.2 `alembic/env.py` — Wiring `settings.DATABASE_URL` and `Base.metadata`
- 3.3 `alembic/script.py.mako` — How New Migration Files Are Templated
- 3.4 How PostgreSQL Tracks Applied Migrations (`alembic_version` Table)

```text
services/parking-service/
├── alembic.ini                                 # Entry config read by `alembic` CLI
└── alembic/
    ├── env.py                                  # Python script connecting Alembic to our app's Settings & Base
    ├── script.py.mako                          # Template for generating new migration files
    └── versions/
        └── 0001_create_parking_tables.py       # Revision 1: creates parking_slots + bookings
```

### 3.1 `alembic.ini` — Configuration, `prepend_sys_path`, Logging & Fallback URL
From `services/parking-service/alembic.ini`:
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql+psycopg://parking_user:parking_pass@localhost:5432/parking_db
```
* **`script_location = alembic`**: Tells Alembic where `env.py` and `versions/` live.
* **`prepend_sys_path = .`**: Adds `services/parking-service/` to Python's `sys.path` so `from app.core.config import settings` works when you run `python -m alembic ...`!
* **Logging (`[logger_alembic] level = INFO`)**: Prints useful migration progress lines (`Running upgrade -> 0001_create_parking_tables`) to your terminal while keeping noisy SQL echo off (`[logger_sqlalchemy] level = WARN`).

### 3.2 `alembic/env.py` — Wiring `settings.DATABASE_URL` and `Base.metadata`
From `services/parking-service/alembic/env.py`:
```python
from app.core.config import settings
from app.core.database import Base
import app.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata
```
* **Why override `sqlalchemy.url` in `env.py`?**
  Never rely only on the hardcoded URL inside `alembic.ini`! Overriding it with `settings.DATABASE_URL` means if you switch `.env` or pass an environment variable `DATABASE_URL=...` in staging/production, Alembic automatically migrates the exact right database!
* **`target_metadata = Base.metadata`**: Enables Alembic `--autogenerate` to compare your SQLAlchemy Python models against PostgreSQL.

### 3.3 `alembic/script.py.mako` — How New Migration Files Are Templated
* **Mako**: A Python templating engine (`${up_revision}`, `${upgrades}`) used by Alembic.
* Whenever you run `alembic revision ...`, Alembic renders `alembic/script.py.mako` to stamp out a fresh file inside `alembic/versions/` with `from alembic import op`, `import sqlalchemy as sa`, `revision`, `down_revision`, `upgrade()`, and `downgrade()`.

### 3.4 How PostgreSQL Tracks Applied Migrations (`alembic_version` Table)
How does Alembic remember which migrations already ran so it doesn't try to create `bookings` twice?
* The first time `alembic upgrade head` runs on `parking_db`, Alembic automatically creates a tiny 1-row, 1-column table inside PostgreSQL:
  ```sql
  CREATE TABLE alembic_version (
      version_num VARCHAR(32) NOT NULL PRIMARY KEY
  );
  ```
* After `0001_create_parking_tables.py` succeeds, PostgreSQL stores `'0001_create_parking_tables'` in `alembic_version`.
* Running `alembic current` reads that table and confirms your DB is at `0001_create_parking_tables (head)`.

---

## Topic 4: Anatomy of a Migration Revision (`0001_create_parking_tables.py`)

**Subtopics in this section:**
- 4.1 Revision Headers (`revision`, `down_revision`, Linked Chain)
- 4.2 Writing `upgrade()` (`op.create_table`, `sa.Column`, `postgresql.UUID`, `sa.ForeignKey`)
- 4.3 Writing `downgrade()` (Reverse Dependency Order & Safe Rollback)

### 4.1 Revision Headers (`revision`, `down_revision`, Linked Chain)
From `services/parking-service/alembic/versions/0001_create_parking_tables.py`:
```python
revision: str = "0001_create_parking_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```
Alembic migrations form a **singly-linked list** pointing backward via `down_revision`:
```text
None ◀── 0001_create_parking_tables ◀── 0002_add_gate_number (head)
```
* **`down_revision = None`**: Means `0001` is the very first (root) migration.
* **`head`**: Means the latest migration at the tip of the chain.

### 4.2 Writing `upgrade()` (`op.create_table`, `sa.Column`, `postgresql.UUID`, `sa.ForeignKey`)
* **`op` (`from alembic import op`)**: Alembic's **Operations** object that emits DDL (`CREATE TABLE`, `ADD COLUMN`, `DROP TABLE`) inside a migration.

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
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        ...,
        sa.Column("slot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parking_slots.id"), nullable=False),
        ...,
        sa.Column("status", sa.String(20), nullable=False, server_default="PAYMENT_PENDING"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        ...,
    )
```
* Notice the **creation order**: `parking_slots` MUST be created **before** `bookings` because `bookings.slot_id` declares `sa.ForeignKey("parking_slots.id")`!

### 4.3 Writing `downgrade()` (Reverse Dependency Order & Safe Rollback)
```python
def downgrade() -> None:
    op.drop_table("bookings")
    op.drop_table("parking_slots")
```
* **Crucial SQL rule**: `downgrade()` MUST be the **exact reverse** of `upgrade()`. If you tried `op.drop_table("parking_slots")` first, PostgreSQL would reject it with a Foreign Key violation because `bookings.slot_id` still references `parking_slots.id`!

---

## Topic 5: Real-World Schema Evolution Walkthrough (Adding a Column End-to-End)

**Subtopics in this section:**
- 5.1 Step 1: Update the SQLAlchemy Model (`app/models/parking.py`)
- 5.2 Step 2: Generate a Migration (`alembic revision --autogenerate`)
- 5.3 Step 3: Inspect & Fix the Generated Revision File
- 5.4 Step 4: Apply (`alembic upgrade head`) & Roll Back (`alembic downgrade -1`)

Suppose tomorrow your team decides to track when an employee enters the parking lot by adding `checked_in_at` to `bookings` **without wiping existing data**. Here is the exact 4-step workflow:

### 5.1 Step 1: Update the SQLAlchemy Model (`app/models/parking.py`)
Add the new column to `class Booking(Base)`:
```python
checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 5.2 Step 2: Generate a Migration (`alembic revision --autogenerate`)
From `services\parking-service`, ask Alembic to diff `Base.metadata` against `parking_db`:
```powershell
..\..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "add checked_in_at to bookings"
```
Alembic creates a file like `alembic/versions/a1b2c3d4e5f6_add_checked_in_at_to_bookings.py` with `down_revision = "0001_create_parking_tables"`.

### 5.3 Step 3: Inspect & Fix the Generated Revision File
**Always open and read autogenerated migrations before running them!** Verify it looks clean:
```python
def upgrade() -> None:
    op.add_column("bookings", sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    op.drop_column("bookings", "checked_in_at")
```
*(If the new column were `nullable=False`, you would add `server_default=...` here before running `upgrade` so existing rows in PostgreSQL don't fail!)*

### 5.4 Step 4: Apply (`alembic upgrade head`) & Roll Back (`alembic downgrade -1`)
```powershell
# Apply to PostgreSQL (runs ALTER TABLE bookings ADD COLUMN checked_in_at TIMESTAMPTZ)
..\..\.venv\Scripts\python.exe -m alembic upgrade head

# Check current version
..\..\.venv\Scripts\python.exe -m alembic current

# Test rollback safely (runs ALTER TABLE bookings DROP COLUMN checked_in_at)
..\..\.venv\Scripts\python.exe -m alembic downgrade -1
```

---

## Topic 6: Essential Alembic Operations (`op.*`) & Autogenerate Gotchas

**Subtopics in this section:**
- 6.1 Most Common `op.*` Commands (`add_column`, `alter_column`, `create_index`, `execute`)
- 6.2 What `--autogenerate` Detects vs. What It Misses (5 Classic Traps)

### 6.1 Most Common `op.*` Commands (`add_column`, `alter_column`, `create_index`, `execute`)
| Need | Alembic `op.*` Code | SQL Executed by PostgreSQL |
| :--- | :--- | :--- |
| Add a column | `op.add_column("bookings", sa.Column("notes", sa.String(200), nullable=True))` | `ALTER TABLE bookings ADD COLUMN notes VARCHAR(200);` |
| Remove a column | `op.drop_column("bookings", "notes")` | `ALTER TABLE bookings DROP COLUMN notes;` |
| Change nullability/length | `op.alter_column("users", "name", existing_type=sa.String(100), type_=sa.String(150), nullable=False)` | `ALTER TABLE users ALTER COLUMN name ...` |
| Add an index | `op.create_index("ix_bookings_date", "bookings", ["booking_date"])` | `CREATE INDEX ix_bookings_date ON bookings (booking_date);` |
| Run custom SQL backfill | `op.execute("UPDATE bookings SET status = 'EXPIRED' WHERE status = 'PENDING'")` | Executes raw SQL inside the migration transaction |

### 6.2 What `--autogenerate` Detects vs. What It Misses (5 Classic Traps)
`--autogenerate` is a helper, **not** magic. Watch out for these 5 things:
1. **Renaming a column**: If you rename `amount` $\rightarrow$ `total_amount` in Python, `--autogenerate` thinks you want `op.drop_column("amount")` + `op.add_column("total_amount")` — **wiping all existing money data!** Always manually replace drop+add with `op.alter_column("bookings", "amount", new_column_name="total_amount")`.
2. **Missing `import app.models`**: Causes Alembic to generate `op.drop_table(...)` for every model not imported in `env.py`.
3. **Table/Column data backfills**: Alembic only detects schema changes, never data migrations (`UPDATE ...`). Write those yourself using `op.execute(...)`.
4. **PostgreSQL `ENUM` alterations**: Adding a new value to a native PG `ENUM` requires manual `ALTER TYPE ... ADD VALUE` (one reason `ParkingSimplified` uses `VARCHAR(20)` strings like `"PAYMENT_PENDING"` instead of rigid PG `ENUM`s—much easier migrations!).
5. **Forgetting `downgrade()`**: Always make sure `downgrade()` mirrors `upgrade()` cleanly.

---

## Topic 7: Using `create_all()` + Alembic Together (`stamp head` & Best Practices)

**Subtopics in this section:**
- 7.1 `ParkingSimplified` Dual Setup: Instant Dev Boot (`create_all`) vs. Versioned Migrations (`alembic`)
- 7.2 Fixing "Table Already Exists" When Adopting Alembic (`alembic stamp head`)
- 7.3 Essential Alembic CLI Command Cheat Sheet

### 7.1 `ParkingSimplified` Dual Setup: Instant Dev Boot (`create_all`) vs. Versioned Migrations (`alembic`)
In `services/parking-service/`:
* **Quick Local Dev**: When you run `uvicorn app.main:app --port 8003`, `lifespan` runs `Base.metadata.create_all(bind=engine)` and `seed_default_slots(db)` so the app works immediately without requiring extra CLI steps.
* **Production / Schema Evolution**: Alembic (`services/parking-service/alembic/`) manages explicit, repeatable migrations before deploying code updates.
*(In production deployments, teams usually turn off `create_all()` and let CI/CD run `alembic upgrade head` before starting Uvicorn.)*

### 7.2 Fixing "Table Already Exists" When Adopting Alembic (`alembic stamp head`)
**Real scenario you can hit right now in `ParkingSimplified`:**
Suppose Uvicorn already created `parking_slots` and `bookings` via `Base.metadata.create_all()`, and now you run `alembic upgrade head` for the first time:
* Because `alembic_version` doesn't exist yet, Alembic tries to run `0001_create_parking_tables.py` $\rightarrow$ PostgreSQL fails with:
  `DuplicateTable: relation "parking_slots" already exists`!
* **How to fix it without dropping your tables (`alembic stamp`):**
  ```powershell
  ..\..\.venv\Scripts\python.exe -m alembic stamp head
  ```
  `stamp head` does **not** run any SQL `CREATE TABLE`—it simply creates `alembic_version` and writes `0001_create_parking_tables` into it, telling Alembic: *"This database is already up-to-date with revision `0001`; start tracking from `0002` onward!"*

### 7.3 Essential Alembic CLI Command Cheat Sheet
Run inside `services\parking-service`:

```powershell
# 1. Inspect current DB revision vs head
..\..\.venv\Scripts\python.exe -m alembic current
..\..\.venv\Scripts\python.exe -m alembic history

# 2. Apply all pending migrations up to the latest revision
..\..\.venv\Scripts\python.exe -m alembic upgrade head

# 3. Preview exact SQL without touching PostgreSQL (--sql offline mode)
..\..\.venv\Scripts\python.exe -m alembic upgrade head --sql

# 4. Generate a new migration from SQLAlchemy model changes
..\..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"

# 5. Roll back the most recent migration
..\..\.venv\Scripts\python.exe -m alembic downgrade -1

# 6. Mark an existing create_all() database as already at head without recreating tables
..\..\.venv\Scripts\python.exe -m alembic stamp head
```
