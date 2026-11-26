# Topic 4: Database, SQLAlchemy 2.0 & Alembic

This file breaks down **every single SQLAlchemy 2.0 and Alembic built-in** individually—with its import path, purpose, parameters, return type, and real project code example.

**Contents:**
* **A. Engine, Session & Base Setup:** [`create_engine`](#1-create_engine) | [`sessionmaker`](#2-sessionmaker) | [`DeclarativeBase`](#3-declarativebase) | [`Session`](#4-session)
* **B. Model & Column Definitions:** [`Mapped[...]`](#5-mapped) | [`mapped_column(...)`](#6-mapped_column) | [`UUID(as_uuid=True)`](#7-uuidas_uuidtrue) | [`ForeignKey(...)`](#8-foreignkey) | [`relationship(...)`](#9-relationship)
* **C. Query Builders:** [`select(...)`](#10-select) | [`delete(...)`](#11-delete) | [`func.count(...)`](#12-funccount) | [`desc(...)`](#13-desc) | [`and_(...)` & `or_(...)`](#14-and_-and-or_)
* **D. Query Modifiers & DDL:** [`joinedload(...)`](#15-joinedload) | [`with_for_update()`](#16-with_for_update) | [`Base.metadata.create_all(...)`](#17-basemetadatacreate_all)
* **E. Session Execution Methods:** [`db.execute`](#18-dbexecute) | [`db.get`](#19-dbget) | [`db.add`](#20-dbadd) | [`db.add_all`](#21-dbadd_all) | [`db.commit`](#22-dbcommit) | [`db.refresh`](#23-dbrefresh) | [`db.close`](#24-dbclose)
* **F. Result Extractors:** [`scalar_one()`](#25-scalar_one) | [`scalar_one_or_none()`](#26-scalar_one_or_none) | [`scalars().all()`](#27-scalarsall)
* **G. Alembic Migration Built-ins:** [`engine_from_config`](#28-engine_from_config) | [`pool.NullPool`](#29-poolnullpool) | [`context.*`](#30-contextconfigure--contextbegin_transaction--contextrun_migrations) | [`op.create_table` & `op.drop_table`](#31-opcreate_table--opdrop_table) | [`sa.text`](#32-satext)

---

## A. Engine, Session & Base Setup

### 1. `create_engine(...)`
* **Import:** `from sqlalchemy import create_engine`
* **In Simple Words:** Builds the database connection pipeline and manages a reusable pool of TCP connections to PostgreSQL (or SQLite in tests).

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `url` | `str` | **Required** | Database connection string (e.g. `"postgresql+psycopg://user:pass@localhost:5432/parking_db"`). |
| `pool_pre_ping` | `bool` | `False` | Sends a tiny `SELECT 1` health check before reusing a pooled connection so stale/dropped DB connections reconnect automatically. |
| `connect_args` | `dict` | `{}` | Extra driver-level arguments (used in SQLite tests: `{"check_same_thread": False}`). |
| `poolclass` | `type[Pool]` | `QueuePool` | Connection pool implementation (`StaticPool` for in-memory SQLite tests). |

* **Returns:** An `Engine` instance.
* **Project Example (`services/parking-service/app/core/database.py`):**
  ```python
  engine = create_engine(
      settings.DATABASE_URL,
      pool_pre_ping=True,
  )
  ```

---

### 2. `sessionmaker(...)`
* **Import:** `from sqlalchemy.orm import sessionmaker`
* **In Simple Words:** Creates a factory class (`SessionLocal`) that produces isolated `Session` objects for each HTTP request.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `bind` | `Engine` | `None` | Binds created sessions to our `engine`. |
| `autocommit` | `bool` | `False` | Keeps transactions explicit; changes only save when we call `db.commit()`. |
| `autoflush` | `bool` | `False` | Prevents SQLAlchemy from automatically sending pending SQL changes before queries unless requested. |
| `expire_on_commit` | `bool` | `True` | When set to `False`, ORM object attributes remain readable in Python after `db.commit()` without triggering extra `SELECT` queries. |

* **Returns:** A `sessionmaker` factory (`SessionLocal`).
* **Project Example (`services/parking-service/app/core/database.py`):**
  ```python
  SessionLocal = sessionmaker(
      autocommit=False,
      autoflush=False,
      expire_on_commit=False,
      bind=engine,
  )
  ```

---

### 3. `DeclarativeBase`
* **Import:** `from sqlalchemy.orm import DeclarativeBase`
* **In Simple Words:** Parent class for `class Base(DeclarativeBase): pass`. Every SQLAlchemy model inherits from `Base`, which registers all tables inside `Base.metadata`.
* **Project Example (`services/parking-service/app/core/database.py`):**
  ```python
  class Base(DeclarativeBase):
      pass
  ```

---

### 4. `Session`
* **Import:** `from sqlalchemy.orm import Session`
* **In Simple Words:** Represents one active unit-of-work / database transaction. Tracks fetched, added, and modified objects until `commit()` or `close()`.
* **Project Example (`services/parking-service/app/api/v1/parking.py`):**
  ```python
  def list_bookings(
      auth: AuthContext = Depends(get_auth_context),
      db: Session = Depends(get_db),
  ):
      ...
  ```

---

## B. Model & Column Definitions

### 5. `Mapped[...]`
* **Import:** `from sqlalchemy.orm import Mapped`
* **In Simple Words:** SQLAlchemy 2.0 generic type hint placed on model attributes. Gives full IDE autocomplete and tells SQLAlchemy whether a column is nullable (`| None`).
* **Project Example (`services/user-auth-service/app/models/auth.py`):**
  ```python
  class User(Base):
      __tablename__ = "users"
      email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
      name: Mapped[str | None] = mapped_column(String(120), nullable=True)
  ```

---

### 6. `mapped_column(...)`
* **Import:** `from sqlalchemy.orm import mapped_column`
* **In Simple Words:** Configures the actual SQL table column properties (SQL type, primary key, uniqueness, indexes, defaults).

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `__type_pos` | `TypeEngine` | Inferred | SQL column type (e.g., `String(255)`, `Integer`, `Numeric(10, 2)`, `UUID(as_uuid=True)`). |
| `primary_key` | `bool` | `False` | Marks column as the table's `PRIMARY KEY`. |
| `unique` | `bool` | `False` | Adds a SQL `UNIQUE` constraint (no duplicates allowed). |
| `index` | `bool` | `False` | Creates a B-tree index to speed up `WHERE` lookups. |
| `nullable` | `bool` | Inferred | `False` emits SQL `NOT NULL`; `True` allows `NULL`. |
| `default` | `Any \| Callable` | `None` | Python-side default evaluated on `INSERT` (e.g. `uuid.uuid4`, `True`). |
| `onupdate` | `Any \| Callable` | `None` | Python-side callable run automatically whenever a row is updated. |

* **Project Example (`services/parking-service/app/models/parking.py`):**
  ```python
  slot_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
  is_charging_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  ```

---

### 7. `UUID(as_uuid=True)`
* **Import:** `from sqlalchemy.dialects.postgresql import UUID`
* **In Simple Words:** PostgreSQL native 16-byte `UUID` column type.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `as_uuid` | `bool` | `False` | When `True`, SQLAlchemy returns real Python `uuid.UUID` objects instead of raw strings. |

* **Project Example (`services/parking-service/app/models/parking.py`):**
  ```python
  id: Mapped[uuid.UUID] = mapped_column(
      UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
  )
  ```

---

### 8. `ForeignKey(...)`
* **Import:** `from sqlalchemy import ForeignKey`
* **In Simple Words:** Enforces a real SQL `REFERENCES` constraint linking a column to a primary key in another table inside the **same database**.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `column` | `str` | **Required** | Target `"table_name.column_name"` (e.g. `"parking_slots.id"`). |
| `ondelete` | `str \| None` | `None` | Optional SQL behavior on parent delete (e.g. `"CASCADE"`, `"RESTRICT"`). |

* **Project Example (`services/parking-service/app/models/parking.py`):**
  ```python
  slot_id: Mapped[uuid.UUID] = mapped_column(
      UUID(as_uuid=True), ForeignKey("parking_slots.id"), nullable=False, index=True
  )
  ```

---

### 9. `relationship(...)`
* **Import:** `from sqlalchemy.orm import relationship`
* **In Simple Words:** Connects two Python ORM models across a `ForeignKey` so you can navigate directly (`booking.slot.slot_number`) without writing manual joins in Python.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `argument` | `str` | Inferred | Related class name (e.g. `"ParkingSlot"`). |
| `back_populates` | `str \| None` | `None` | Attribute name on the opposite model so both sides stay synchronized in memory. |

* **Project Example (`services/parking-service/app/models/parking.py`):**
  ```python
  class Booking(Base):
      slot: Mapped["ParkingSlot"] = relationship("ParkingSlot", back_populates="bookings")
  ```

---

## C. Query Builders

### 10. `select(...)`
* **Import:** `from sqlalchemy import select`
* **In Simple Words:** Builds a SQL `SELECT` query object (does **not** run until passed to `db.execute(...)`).

| Parameter / Chain Method | What it does |
| :--- | :--- |
| `select(Model)` or `select(Model.col)` | Chooses the ORM model or specific column(s) to fetch. |
| `.where(*criteria)` | Adds SQL `WHERE` filter conditions. |
| `.order_by(*clauses)` | Adds SQL `ORDER BY` sorting. |
| `.offset(n)` / `.limit(n)` | Pagination (`OFFSET` / `LIMIT`). |
| `.distinct()` | Adds SQL `SELECT DISTINCT` to remove duplicate results. |
| `.options(...)` | Attaches loader strategies like `joinedload(...)`. |

* **Project Example (`services/vehicle-service/app/api/v1/vehicles.py`):**
  ```python
  stmt = (
      select(Vehicle)
      .where(Vehicle.user_id == user_id, Vehicle.is_active.is_(True))
      .order_by(Vehicle.created_at.asc())
  )
  ```

---

### 11. `delete(...)`
* **Import:** `from sqlalchemy import delete`
* **In Simple Words:** Builds a bulk SQL `DELETE FROM table` statement (pass to `db.execute(...)`).
* **Parameter:** `table` — ORM model class (e.g. `delete(Booking)`), chained with `.where(...)`.
* **Project Example (`tests/test_pg_concurrency.py`):**
  ```python
  db.execute(delete(Booking).where(Booking.booking_date == target_date))
  db.commit()
  ```

---

### 12. `func.count(...)`
* **Import:** `from sqlalchemy import func`
* **In Simple Words:** Generates SQL `COUNT(column)` to count matching rows directly inside PostgreSQL without loading row data into Python.
* **Parameter:** `column` — e.g., `func.count(Booking.id)`.
* **Project Example (`services/parking-service/app/api/v1/parking.py`):**
  ```python
  total_items = db.execute(
      select(func.count(Booking.id)).where(Booking.user_id == auth.user_id)
  ).scalar_one()
  ```

---

### 13. `desc(...)`
* **Import:** `from sqlalchemy import desc`
* **In Simple Words:** Wraps a column in SQL `DESC` (`ORDER BY created_at DESC`, newest first). Paired with column `.asc()` for ascending order.
* **Project Example (`services/parking-service/app/api/v1/parking.py`):**
  ```python
  stmt = select(Booking).where(Booking.user_id == auth.user_id).order_by(desc(Booking.created_at))
  ```

---

### 14. `and_(...)` and `or_(...)`
* **Import:** `from sqlalchemy import and_, or_`
* **In Simple Words:** Explicitly groups multiple SQL boolean filter expressions with parentheses (`(A AND B) OR C`).
* **Parameters:** `*clauses` — two or more SQLAlchemy boolean conditions.
* **Project Example (`services/parking-service/app/api/v1/parking.py`):**
  ```python
  def _active_booking_filter(now_utc: datetime):
      return or_(
          Booking.status == "CONFIRMED",
          and_(Booking.status == "PAYMENT_PENDING", Booking.hold_expires_at > now_utc),
      )
  ```

---

## D. Query Modifiers & DDL

### 15. `joinedload(...)`
* **Import:** `from sqlalchemy.orm import joinedload`
* **In Simple Words:** Adds a SQL `LEFT OUTER JOIN` to a `select(...)` query so related objects (`Booking.slot`) load in **1 single query**, preventing the N+1 query problem.
* **Parameter:** `attr` — relationship attribute on the model.
* **Project Example (`services/parking-service/app/api/v1/parking.py`):**
  ```python
  stmt = (
      select(Booking)
      .options(joinedload(Booking.slot))
      .where(Booking.id == booking_id, Booking.user_id == auth.user_id)
  )
  ```

---

### 16. `with_for_update()`
* **Import:** Method on a `select(...)` statement (`stmt.with_for_update()`).
* **In Simple Words:** Appends PostgreSQL `FOR UPDATE` to lock selected rows until `db.commit()` finishes. Prevents concurrent race conditions and double-bookings.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `nowait` | `bool` | `False` | If `False`, concurrent transactions wait in line for the lock to release. If `True`, throws an error immediately if locked. |
| `skip_locked` | `bool` | `False` | If `True`, skips rows currently locked by another transaction instead of waiting. |

* **Project Example (`services/parking-service/app/api/v1/parking.py`):**
  ```python
  slot_stmt = (
      select(ParkingSlot)
      .where(
          ParkingSlot.vehicle_type == vehicle.vehicle_type,
          ParkingSlot.is_charging_enabled.is_(payload.requires_charging),
      )
      .order_by(ParkingSlot.slot_number.asc())
      .with_for_update()
  )
  compatible_slots = list(db.execute(slot_stmt).scalars().all())
  ```

---

### 17. `Base.metadata.create_all(...)`
* **Import:** Method on `Base.metadata`.
* **In Simple Words:** Inspects all models inheriting from `Base` and runs `CREATE TABLE IF NOT EXISTS` for each table.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `bind` | `Engine \| Connection` | **Required** | The SQLAlchemy engine pointing to the target database. |
| `checkfirst` | `bool` | `True` | Checks if tables already exist before creating (emits `IF NOT EXISTS`). |

* **Project Example (`services/parking-service/app/main.py`):**
  ```python
  Base.metadata.create_all(bind=engine)
  ```

---

## E. Session Execution Methods

### 18. `db.execute(statement)`
* **Parameters:** `statement` (`select(...)` or `delete(...)` object).
* **What it does:** Sends the compiled SQL statement over the connection to the database and returns a `Result` object.
* **Project Example:**
  ```python
  result = db.execute(select(Booking).where(Booking.id == booking_id))
  ```

---

### 19. `db.get(entity, ident)`
* **Parameters:** `entity` (ORM Model class), `ident` (Primary key value).
* **What it does:** Fetches a single row directly by primary key (`None` if not found).
* **Project Example:**
  ```python
  slot = db.get(ParkingSlot, slot_id)
  ```

---

### 20. `db.add(instance)`
* **Parameters:** `instance` (an ORM model instance).
* **What it does:** Stages a new Python object in the session so it will be `INSERT`ed on the next `db.commit()`.
* **Project Example (`services/parking-service/app/api/v1/parking.py`):**
  ```python
  booking = Booking(...)
  db.add(booking)
  ```

---

### 21. `db.add_all(instances)`
* **Parameters:** `instances` (`Iterable` of ORM objects).
* **What it does:** Stages multiple new ORM rows in the session at once.
* **Project Example (`services/parking-service/app/models/parking.py`):**
  ```python
  db.add_all(slots_to_seed)
  db.commit()
  ```

---

### 22. `db.commit()`
* **Parameters:** None.
* **What it does:** Flushes all staged `INSERT`, `UPDATE`, and `DELETE` operations and commits the database transaction permanently to disk (releasing any `FOR UPDATE` row locks).
* **Project Example:**
  ```python
  db.add(payment)
  db.commit()
  ```

---

### 23. `db.refresh(instance)`
* **Parameters:** `instance` (an ORM object already added/committed).
* **What it does:** Runs a `SELECT` to reload database-generated columns (`id`, `created_at`, `updated_at`) onto the Python object after `db.commit()`.
* **Project Example:**
  ```python
  db.commit()
  db.refresh(booking)  # Populates booking.id and booking.created_at from PostgreSQL
  ```

---

### 24. `db.close()`
* **Parameters:** None.
* **What it does:** Closes the session and returns the underlying database connection back to the engine's pool.
* **Project Example (`services/parking-service/app/core/database.py`):**
  ```python
  def get_db():
      db = SessionLocal()
      try:
          yield db
      finally:
          db.close()
  ```

---

## F. Result Extractors

When you run `result = db.execute(stmt)`, you call one of these extractors on `result`:

### 25. `.scalar_one()`
* **Parameters:** None.
* **Returns:** Single scalar value or ORM object. Raises if 0 or >1 rows matched.
* **Project Example:**
  ```python
  total = db.execute(select(func.count(Booking.id))).scalar_one()
  ```

---

### 26. `.scalar_one_or_none()`
* **Parameters:** None.
* **Returns:** Single ORM object / scalar value, or `None` if 0 rows matched.
* **Project Example (`services/user-auth-service/app/api/v1/auth.py`):**
  ```python
  user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
  ```

---

### 27. `.scalars().all()`
* **Parameters:** None.
* **Returns:** Sequence of matching ORM objects / column values.
* **Project Example (`services/vehicle-service/app/api/v1/vehicles.py`):**
  ```python
  rows = db.execute(select(Vehicle).where(Vehicle.user_id == user_id)).scalars().all()
  ```

---

## G. Alembic Migration Built-ins

### 28. `engine_from_config(...)`
* **Import:** `from sqlalchemy import engine_from_config`
* **In Simple Words:** Reads settings from `alembic.ini` and builds a SQLAlchemy engine for running migrations.

| Parameter | Type | What it does |
| :--- | :--- | :--- |
| `configuration` | `dict` | Parsed INI key-value dictionary (`config.get_section(...)`). |
| `prefix` | `str` | Key prefix to read (`"sqlalchemy."` reads `sqlalchemy.url`, etc.). |
| `poolclass` | `type[Pool]` | Pool strategy (`pool.NullPool`). |

* **Project Example (`services/parking-service/alembic/env.py`):**
  ```python
  connectable = engine_from_config(
      config.get_section(config.config_ini_section, {}),
      prefix="sqlalchemy.",
      poolclass=pool.NullPool,
  )
  ```

---

### 29. `pool.NullPool`
* **Import:** `from sqlalchemy import pool`
* **In Simple Words:** Disables connection pooling so Alembic closes its database connection immediately after migrations complete.
* **Project Example (`services/parking-service/alembic/env.py`):**
  ```python
  from sqlalchemy import engine_from_config, pool

  connectable = engine_from_config(..., poolclass=pool.NullPool)
  ```

---

### 30. `context.configure(...)`, `context.begin_transaction()`, `context.run_migrations()`
* **Import:** `from alembic import context`
* **In Simple Words:** Binds Alembic to your active DB connection and `Base.metadata`, opens a migration transaction, and executes pending `upgrade()` scripts.
* **Project Example (`services/parking-service/alembic/env.py`):**
  ```python
  with connectable.connect() as connection:
      context.configure(connection=connection, target_metadata=target_metadata)
      with context.begin_transaction():
          context.run_migrations()
  ```

---

### 31. `op.create_table(...)` & `op.drop_table(...)`
* **Import:** `from alembic import op`
* **In Simple Words:** Emits `CREATE TABLE` DDL inside `upgrade()` and `DROP TABLE` DDL inside `downgrade()`.
* **Project Example (`services/parking-service/alembic/versions/0001_create_parking_tables.py`):**
  ```python
  def upgrade() -> None:
      op.create_table(
          "parking_slots",
          sa.Column("id", sa.UUID(), nullable=False),
          sa.Column("slot_number", sa.String(length=20), nullable=False),
          sa.PrimaryKeyConstraint("id"),
      )

  def downgrade() -> None:
      op.drop_table("parking_slots")
  ```

---

### 32. `sa.text(...)`
* **Import:** `import sqlalchemy as sa`
* **In Simple Words:** Marks a string as raw SQL rather than a plain string literal.
* **Project Example (`services/parking-service/alembic/versions/0001_create_parking_tables.py`):**
  ```python
  sa.Column("is_charging_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False)
  ```
