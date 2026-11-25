# Entity-Relationship (ER) & Database Design

## 1. Database Topology Overview

The platform enforces strict **Database-per-Service** isolation across four PostgreSQL databases (`user_db`, `vehicle_db`, `parking_db`, `payment_db`).

* **Physical Foreign Keys** exist **only** within the same database (`bookings.slot_id -> parking_slots.id` inside `parking_db`).
* **Cross-Service References** (`user_id`, `vehicle_id`, `booking_id`, `payment_id`) are stored as plain `UUID` columns without cross-database foreign keys, validated via authenticated REST calls and preserved historically via immutable snapshot columns.

---

## 2. Unified System Entity-Relationship Diagram

Solid relationships (`||--o{`) represent **physical database foreign keys** enforced by PostgreSQL. Dashed relationships (`||..o{`, `||..o|`) represent **logical cross-service UUID references** across isolated microservice databases.

```mermaid
erDiagram
    %% user_db (user-auth-service)
    USERS {
        uuid id PK "Primary key"
        varchar_255 email UK "Unique, indexed, normalized lowercase"
        varchar_100 name "Nullable display name"
        timestamptz created_at "UTC creation timestamp"
        timestamptz updated_at "UTC last-updated timestamp"
    }

    VERIFICATION_CODES {
        uuid id PK "Primary key"
        varchar_255 email "Indexed corporate email"
        varchar_255 code_hash "6-digit OTP code (ORM attr: code)"
        timestamptz expires_at "UTC expiry (created_at + 5 min)"
        integer attempt_count "Default 0"
        timestamptz consumed_at "Nullable; set on verify or supersede"
        timestamptz created_at "UTC creation timestamp"
    }

    %% vehicle_db (vehicle-service)
    VEHICLES {
        uuid id PK "Primary key"
        uuid user_id "Indexed logical ref -> USERS.id"
        varchar_20 vehicle_number "Normalized uppercase alphanumeric"
        varchar_10 vehicle_type "CAR | BIKE"
        boolean is_ev "Default false"
        boolean is_active "Soft-delete flag, default true"
        timestamptz created_at "UTC creation timestamp"
    }

    %% parking_db (parking-service)
    PARKING_SLOTS {
        uuid id PK "Primary key"
        varchar_10 slot_number UK "Unique: C01-C60, B01-B40"
        varchar_10 vehicle_type "CAR | BIKE"
        boolean is_charging_enabled "EV charger equipped flag"
    }

    BOOKINGS {
        uuid id PK "Primary key"
        uuid user_id "Indexed logical ref -> USERS.id"
        uuid vehicle_id "Logical ref -> VEHICLES.id"
        varchar_20 vehicle_number_snapshot "Captured at booking time"
        varchar_10 vehicle_type_snapshot "CAR | BIKE snapshot"
        boolean is_ev_snapshot "EV status snapshot"
        uuid slot_id FK "Physical FK -> PARKING_SLOTS.id"
        date booking_date "Facility local date"
        time start_time "Whole hour (07:00-21:00)"
        time end_time "Whole hour (08:00-22:00)"
        boolean requires_charging "Default false"
        varchar_20 status "PAYMENT_PENDING | CONFIRMED | EXPIRED | CANCELLED"
        numeric_10_2 amount "Calculated total fee"
        timestamptz hold_expires_at "Nullable; 5-min payment hold deadline"
        uuid payment_id UK "Unique nullable logical ref -> PAYMENTS.id"
        timestamptz created_at "UTC creation timestamp"
        timestamptz cancelled_at "Nullable UTC cancellation timestamp"
    }

    %% payment_db (payment-service)
    PAYMENTS {
        uuid id PK "Primary key"
        uuid booking_id UK "Unique logical ref -> BOOKINGS.id"
        uuid user_id "Indexed logical ref -> USERS.id"
        numeric_10_2 amount "Booking fee (> 0)"
        varchar_20 payment_method "Nullable: UPI | CARD | WALLET"
        varchar_20 status "PENDING | SUCCESS | FAILED"
        varchar_100 transaction_id UK "Unique nullable simulated TXN ID"
        timestamptz expires_at "Matches booking hold_expires_at"
        timestamptz created_at "UTC creation timestamp"
    }

    %% Intra-database Physical Foreign Key
    PARKING_SLOTS ||--o{ BOOKINGS : "allocated_to (FK slot_id)"

    %% Logical Association within user_db (pre-signup capable)
    USERS |o..o{ VERIFICATION_CODES : "authenticates_by_email"

    %% Cross-Database Logical References
    USERS ||..o{ VEHICLES : "owns (user_id)"
    USERS ||..o{ BOOKINGS : "places (user_id)"
    USERS ||..o{ PAYMENTS : "initiates (user_id)"
    VEHICLES ||..o{ BOOKINGS : "snapshotted_in (vehicle_id)"
    BOOKINGS ||..o| PAYMENTS : "settled_by (booking_id / payment_id)"
```

---

## 3. Database-by-Database Schema Specification

### 3.1 `user_db` — User & Auth Service (`user_auth_user`)

#### Table: `users`
| Column | PostgreSQL Type | Nullable | Default | Constraints / Indexes |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | `NO` | `uuid4()` | `PRIMARY KEY` |
| `email` | `VARCHAR(255)` | `NO` | — | `UNIQUE`, `INDEX` (`ix_users_email`) |
| `name` | `VARCHAR(100)` | `YES` | `NULL` | — |
| `created_at` | `TIMESTAMPTZ` | `NO` | `utcnow()` | — |
| `updated_at` | `TIMESTAMPTZ` | `NO` | `utcnow()` | Auto-updated via `onupdate=utcnow` |

#### Table: `verification_codes`
| Column | PostgreSQL Type | Nullable | Default | Constraints / Indexes |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | `NO` | `uuid4()` | `PRIMARY KEY` |
| `email` | `VARCHAR(255)` | `NO` | — | `INDEX` (`ix_verification_codes_email`); intentionally decoupled from `users.id` so OTPs work prior to first-time user creation |
| `code_hash` | `VARCHAR(255)` | `NO` | — | Mapped to ORM attribute `VerificationCode.code` |
| `expires_at` | `TIMESTAMPTZ` | `NO` | — | `created_at + 5 minutes` |
| `attempt_count` | `INTEGER` | `NO` | `0` | Tracks verification attempts |
| `consumed_at` | `TIMESTAMPTZ` | `YES` | `NULL` | Populated upon verification or when superseded by a newer OTP |
| `created_at` | `TIMESTAMPTZ` | `NO` | `utcnow()` | Ordered `DESC` during verification lookup |

---

### 3.2 `vehicle_db` — Vehicle Service (`vehicle_user`)

#### Table: `vehicles`
| Column | PostgreSQL Type | Nullable | Default | Constraints / Indexes |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | `NO` | `uuid4()` | `PRIMARY KEY` |
| `user_id` | `UUID` | `NO` | — | `INDEX` (`ix_vehicles_user_id`); logical reference to `users.id` |
| `vehicle_number` | `VARCHAR(20)` | `NO` | — | Normalized (`^[A-Z0-9]{4,20}$`); active uniqueness per user enforced in service logic |
| `vehicle_type` | `VARCHAR(10)` | `NO` | — | Domain values: `CAR`, `BIKE` |
| `is_ev` | `BOOLEAN` | `NO` | `false` | Determines EV charging eligibility |
| `is_active` | `BOOLEAN` | `NO` | `true` | Soft-delete flag; preserves historical booking references and permits plate re-registration |
| `created_at` | `TIMESTAMPTZ` | `NO` | `utcnow()` | — |

---

### 3.3 `parking_db` — Parking Service (`parking_user`)

#### Table: `parking_slots`
| Column | PostgreSQL Type | Nullable | Default | Constraints / Indexes |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | `NO` | `uuid4()` | `PRIMARY KEY` |
| `slot_number` | `VARCHAR(10)` | `NO` | — | `UNIQUE` (`C01`–`C60`, `B01`–`B40`) |
| `vehicle_type` | `VARCHAR(10)` | `NO` | — | `CAR` or `BIKE` |
| `is_charging_enabled` | `BOOLEAN` | `NO` | `false` | `true` for `C51`–`C60` and `B36`–`B40` |

**Seeded Slot Distribution (100 Total Slots):**
* `C01`–`C50` (50 slots): `CAR`, `is_charging_enabled = false`
* `C51`–`C60` (10 slots): `CAR`, `is_charging_enabled = true`
* `B01`–`B35` (35 slots): `BIKE`, `is_charging_enabled = false`
* `B36`–`B40` (5 slots): `BIKE`, `is_charging_enabled = true`

#### Table: `bookings`
| Column | PostgreSQL Type | Nullable | Default | Constraints / Indexes |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | `NO` | `uuid4()` | `PRIMARY KEY` |
| `user_id` | `UUID` | `NO` | — | `INDEX` (`ix_bookings_user_id`); logical reference to `users.id` |
| `vehicle_id` | `UUID` | `NO` | — | Logical reference to `vehicles.id` |
| `vehicle_number_snapshot` | `VARCHAR(20)` | `NO` | — | Denormalized snapshot at booking time |
| `vehicle_type_snapshot` | `VARCHAR(10)` | `NO` | — | Denormalized snapshot (`CAR` / `BIKE`) |
| `is_ev_snapshot` | `BOOLEAN` | `NO` | — | Denormalized snapshot |
| `slot_id` | `UUID` | `NO` | — | `FOREIGN KEY REFERENCES parking_slots(id)` |
| `booking_date` | `DATE` | `NO` | — | Facility local date (`Asia/Kolkata`) |
| `start_time` | `TIME` | `NO` | — | Whole hour (`07:00`–`21:00`) |
| `end_time` | `TIME` | `NO` | — | Whole hour (`08:00`–`22:00`) |
| `requires_charging` | `BOOLEAN` | `NO` | `false` | Determines slot pool & hourly rate |
| `status` | `VARCHAR(20)` | `NO` | `'PAYMENT_PENDING'` | `PAYMENT_PENDING`, `CONFIRMED`, `EXPIRED`, `CANCELLED` |
| `amount` | `NUMERIC(10, 2)` | `NO` | — | `hours * rate_per_hour` |
| `hold_expires_at` | `TIMESTAMPTZ` | `YES` | `NULL` | `created_at + 5 minutes` |
| `payment_id` | `UUID` | `YES` | `NULL` | `UNIQUE`; logical reference to `payments.id` |
| `created_at` | `TIMESTAMPTZ` | `NO` | `utcnow()` | — |
| `cancelled_at` | `TIMESTAMPTZ` | `YES` | `NULL` | Populated on user cancellation |

---

### 3.4 `payment_db` — Payment Service (`payment_user`)

#### Table: `payments`
| Column | PostgreSQL Type | Nullable | Default | Constraints / Indexes |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | `NO` | `uuid4()` | `PRIMARY KEY` |
| `booking_id` | `UUID` | `NO` | — | `UNIQUE` (enforces 1-to-1 idempotent payment per booking) |
| `user_id` | `UUID` | `NO` | — | `INDEX` (`ix_payments_user_id`); logical reference to `users.id` |
| `amount` | `NUMERIC(10, 2)` | `NO` | — | Positive decimal amount |
| `payment_method` | `VARCHAR(20)` | `YES` | `NULL` | Populated on process: `UPI`, `CARD`, `WALLET` |
| `status` | `VARCHAR(20)` | `NO` | `'PENDING'` | `PENDING`, `SUCCESS`, `FAILED` |
| `transaction_id` | `VARCHAR(100)` | `YES` | `NULL` | `UNIQUE`; `TXN<10-hex>` on `SUCCESS`, `NULL` on `FAILED` |
| `expires_at` | `TIMESTAMPTZ` | `NO` | — | Synchronized with `bookings.hold_expires_at` |
| `created_at` | `TIMESTAMPTZ` | `NO` | `utcnow()` | — |

---

## 4. Database Security & Schema Governance

1. **Role & Privilege Isolation (`scripts/init_postgres.sql`)**:
   * `REVOKE CONNECT ON DATABASE <db> FROM PUBLIC` blocks unauthorized cross-service connections at the PostgreSQL authentication layer.
   * Each service role owns only its respective database and `public` schema (`ALTER SCHEMA public OWNER TO <role>`).
2. **Schema Lifecycle & Migrations**:
   * Local development boots cleanly via idempotent `Base.metadata.create_all()` + automatic slot seeding (`seed_default_slots`).
   * Versioned schema evolution is demonstrated in `services/parking-service/alembic/` using **Alembic** migrations.
