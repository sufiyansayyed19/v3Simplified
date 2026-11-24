# PostgreSQL Database Design (6 Simplified Tables Across 4 Databases)

## 1. Database Ownership Matrix

Each of the 4 microservices connects exclusively to its own PostgreSQL database:

| Service | Database | DB Role | Tables Owned | Schema Creation |
|---|---|---|---|---|
| **User/Auth Service** | `user_db` | `user_auth_user` | `users`, `verification_codes` | `Base.metadata.create_all` |
| **Vehicle Service** | `vehicle_db` | `vehicle_user` | `vehicles` | `Base.metadata.create_all` |
| **Parking Service** | `parking_db` | `parking_user` | `parking_slots`, `bookings` | **Alembic** + `create_all` + auto-seed 100 slots |
| **Payment Service** | `payment_db` | `payment_user` | `payments` | `Base.metadata.create_all` |

---

## 2. User/Auth Database (`user_db` — 2 Tables)

### 2.1 `users`
| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `UUID` | No | Primary key |
| `email` | `VARCHAR(255)` | No | Unique normalized corporate email |
| `name` | `VARCHAR(100)` | Yes | Optional display name |
| `created_at` | `TIMESTAMPTZ` | No | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | No | Update timestamp |

### 2.2 `verification_codes`
| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `UUID` | No | Primary key |
| `email` | `VARCHAR(255)` | No | Indexed corporate email |
| `code_hash` (`code`) | `VARCHAR(255)` | No | 6-digit OTP code |
| `expires_at` | `TIMESTAMPTZ` | No | 5-minute expiration timestamp |
| `attempt_count` | `INTEGER` | No | Default `0` |
| `consumed_at` | `TIMESTAMPTZ` | Yes | Set when verified or superseded |
| `created_at` | `TIMESTAMPTZ` | No | Creation timestamp |

---

## 3. Vehicle Database (`vehicle_db` — 1 Table)

### 3.1 `vehicles`
| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `UUID` | No | Primary key |
| `user_id` | `UUID` | No | Logical reference to `users.id` (indexed) |
| `vehicle_number` | `VARCHAR(20)` | No | Normalized plate (`"MH12AB1234"`) |
| `vehicle_type` | `VARCHAR(10)` | No | `"CAR"` or `"BIKE"` |
| `is_ev` | `BOOLEAN` | No | Electric vehicle flag |
| `is_active` | `BOOLEAN` | No | Soft-delete flag (default `true`) |
| `created_at` | `TIMESTAMPTZ` | No | Creation timestamp |

---

## 4. Parking Database (`parking_db` — 2 Tables)

### 4.1 `parking_slots` (Auto-seeded with 100 slots: `C01–C60`, `B01–B40`)
| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `UUID` | No | Primary key |
| `slot_number` | `VARCHAR(10)` | No | Unique slot label (`C01`..`C60`, `B01`..`B40`) |
| `vehicle_type` | `VARCHAR(10)` | No | `"CAR"` or `"BIKE"` |
| `is_charging_enabled` | `BOOLEAN` | No | `true` for `C51–C60` and `B36–B40` |

### 4.2 `bookings`
| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `UUID` | No | Primary key |
| `user_id` | `UUID` | No | Logical reference to `users.id` (indexed) |
| `vehicle_id` | `UUID` | No | Logical reference to `vehicles.id` |
| `vehicle_number_snapshot` | `VARCHAR(20)` | No | Snapshot of vehicle plate at booking time |
| `vehicle_type_snapshot` | `VARCHAR(10)` | No | Snapshot of `"CAR"` or `"BIKE"` |
| `is_ev_snapshot` | `BOOLEAN` | No | Snapshot of `is_ev` |
| `slot_id` | `UUID` | No | **Real SQL `ForeignKey("parking_slots.id")`** |
| `booking_date` | `DATE` | No | Local booking date (`Asia/Kolkata`) |
| `start_time` | `TIME` | No | Whole-hour start time |
| `end_time` | `TIME` | No | Whole-hour end time |
| `requires_charging` | `BOOLEAN` | No | Whether EV charging was requested |
| `status` | `VARCHAR(20)` | No | `PAYMENT_PENDING`, `CONFIRMED`, `EXPIRED`, `CANCELLED` |
| `amount` | `NUMERIC(10,2)` | No | Total fee (`₹10/hr` normal, `₹20/hr` charging) |
| `hold_expires_at` | `TIMESTAMPTZ` | Yes | 5-minute hold expiry |
| `payment_id` | `UUID` | Yes | Unique logical reference to `payments.id` |
| `created_at` | `TIMESTAMPTZ` | No | Creation timestamp |
| `cancelled_at` | `TIMESTAMPTZ` | Yes | Cancellation timestamp |

---

## 5. Payment Database (`payment_db` — 1 Table)

### 5.1 `payments`
| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `UUID` | No | Primary key |
| `booking_id` | `UUID` | No | Unique logical reference to `bookings.id` |
| `user_id` | `UUID` | No | Logical reference to `users.id` (indexed) |
| `amount` | `NUMERIC(10,2)` | No | Booking fee amount |
| `payment_method` | `VARCHAR(20)` | Yes | `"UPI"`, `"CARD"`, `"WALLET"` |
| `status` | `VARCHAR(20)` | No | `PENDING`, `SUCCESS`, `FAILED` |
| `transaction_id` | `VARCHAR(100)` | Yes | Unique simulated transaction reference (`TXN...`) |
| `expires_at` | `TIMESTAMPTZ` | No | Payment expiry timestamp |
| `created_at` | `TIMESTAMPTZ` | No | Creation timestamp |
