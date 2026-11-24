# Edge Cases & Handling Techniques Across Services

> **Scope**: All 4 microservices (`user-auth-service`, `vehicle-service`, `parking-service`, `payment-service`)  
> **Purpose**: Reference guide explaining every real-world edge case handled in the codebase, the exact technique/logic used, and where it is implemented.

---

## Quick Summary Matrix

| Category | Edge Case | Service | Technique / Pattern Used | Error / Result |
| :--- | :--- | :--- | :--- | :--- |
| **Auth** | Non-corporate email login | `user-auth-service` | Domain suffix check after normalization | `403 CORPORATE_EMAIL_REQUIRED` |
| **Auth** | OTP reuse / replay attack | `user-auth-service` | `consumed_at` timestamp + invalidate prior unused OTPs | `401 INVALID_OR_EXPIRED_CODE` |
| **Vehicle** | Plate spacing/casing variants | `vehicle-service` | Pydantic `@field_validator` (`normalize_vehicle_number`) | Normalized e.g. `KA01AB1234` |
| **Vehicle** | Deleting a booked vehicle | `vehicle-service` + `parking-service` | Soft delete (`is_active=False`) + Snapshot columns on `Booking` | History preserved |
| **Parking** | Double-booking race condition | `parking-service` | PostgreSQL `SELECT ... FOR UPDATE` slot row locking | `409 NO_PARKING_CAPACITY` |
| **Parking** | Back-to-back slot bookings | `parking-service` | Half-open interval overlap (`start < req_end AND end > req_start`) | Allowed cleanly |
| **Parking** | Abandoned `PAYMENT_PENDING` hold | `parking-service` | Lazy hold expiry (`_active_booking_filter` + `_expire_stale_holds`) | Auto-released after 5 min |
| **Parking** | Late payment callback after hold expiry | `parking-service` | Expiry check inside `apply_payment_result` (no resurrection) | `EXPIRED_NO_RESURRECTION` |
| **Payment** | Duplicate payment creation call | `payment-service` | Idempotency check on `booking_id` + conflict guard | `200 OK` or `409 PAYMENT_REQUEST_CONFLICT` |
| **Payment** | Double payment / expired window | `payment-service` | State & deadline guards before processing | `409 PAYMENT_ALREADY_PROCESSED` / `PAYMENT_EXPIRED` |

---

## 1. User & Auth Service (`services/user-auth-service`)

Implemented in [auth.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/api/v1/auth.py) and [security.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/core/security.py).

### 1.1 Email Case & Whitespace Variations
* **Edge Case**: User enters `"  Alice@Company.COM "` on send-code and `"alice@company.com"` on verify.
* **Technique**: `normalize_email()` strips whitespace and lowercases the address before domain validation, DB lookup, and storage.

### 1.2 Non-Corporate Email Restriction
* **Edge Case**: External users (`outsider@gmail.com`) attempt to request an OTP.
* **Technique**: `is_allowed_corporate_email()` splits on the last `@` (`rsplit("@", 1)`) and checks strict equality against `settings.COMPANY_EMAIL_DOMAIN` (`company.com`), raising `403 CORPORATE_EMAIL_REQUIRED`.

### 1.3 Multiple OTP Requests & Replay Attacks
* **Edge Case A (Spamming send-code)**: User requests 3 OTPs in a row and tries to use the 1st OTP.
  * **Technique**: In `send_company_code()`, all prior rows for that email where `consumed_at IS NULL` are marked `consumed_at = now` before inserting the new code. Only the latest OTP can ever succeed.
* **Edge Case B (OTP Replay)**: Attacker or user submits the same valid OTP a second time.
  * **Technique**: `verify_company_code()` sets `verification.consumed_at = now` and commits immediately upon first successful verification. A second attempt finds no unconsumed matching code and returns `401 INVALID_OR_EXPIRED_CODE`.

### 1.4 Timezone-Naive vs. Timezone-Aware Timestamps
* **Edge Case**: SQLite (in unit tests) returns naive `datetime` objects whereas PostgreSQL `TIMESTAMP WITH TIME ZONE` returns aware `datetime` objects; comparing naive and aware datetimes in Python raises `TypeError`.
* **Technique**: `_as_utc(dt)` normalizes any naive datetime to UTC before comparing `expires_at <= now`.

### 1.5 First-Time vs. Returning User (JIT Provisioning)
* **Edge Case**: No separate registration endpoint exists; a valid employee logs in for the first time.
* **Technique**: `verify_company_code()` queries `User` by normalized email and auto-creates `User(email=email, name=None)` only after OTP verification succeeds.

---

## 2. Vehicle Service (`services/vehicle-service`)

Implemented in [vehicles.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/vehicle-service/app/api/v1/vehicles.py) and [vehicle.py (schemas)](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/vehicle-service/app/schemas/vehicle.py).

### 2.1 License Plate Formatting Variants
* **Edge Case**: User registers `"KA-01 AB 1234"` and later tries to register `"ka01ab1234"` as a duplicate.
* **Technique**: `normalize_vehicle_number()` strips spaces and hyphens (`re.sub(r"[\s-]+", "", raw.strip()).upper()`) and validates `^[A-Z0-9]{4,20}$` in Pydantic `@field_validator` on both `VehicleCreate` and `VehicleUpdate`.

### 2.2 Duplicate Active Vehicle Check (Create vs. Update)
* **Edge Case**: Updating a vehicle's `is_ev` flag without changing its `vehicle_number` shouldn't trigger a self-duplicate error, while changing its plate to another active vehicle's plate must fail.
* **Technique**:
  * On `create_vehicle()`: checks `(user_id, vehicle_number, is_active=True)`.
  * On `update_vehicle()`: adds `Vehicle.id != vehicle.id` to the duplicate check so self-updates succeed while collisions raise `409 VEHICLE_ALREADY_REGISTERED`.

### 2.3 Cross-User Access (IDOR) Prevention
* **Edge Case**: User A guesses User B's `vehicle_id` UUID and calls `GET`, `PUT`, or `DELETE /api/v1/vehicles/{vehicle_id}`.
* **Technique**: `_get_owned_active_vehicle()` queries with `Vehicle.id == vehicle_id AND Vehicle.user_id == user_id AND Vehicle.is_active.is_(True)` and returns `404 VEHICLE_NOT_FOUND` (avoiding `403` so existence of another user's UUID is not leaked).

### 2.4 Soft Delete & Re-Registration
* **Edge Case**: User deletes a vehicle that was used in past parking bookings, or later wants to re-register the same plate.
* **Technique**: `deactivate_vehicle()` sets `vehicle.is_active = False` instead of deleting the row. Active queries filter `is_active = True`, so the user can re-register the same plate later without violating a global unique constraint, and historical bookings remain intact.

---

## 3. Parking Service (`services/parking-service`)

Implemented in [parking.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/api/v1/parking.py), [rules.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/services/rules.py), [clients.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/services/clients.py), and [internal.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/api/internal.py).

### 3.1 Concurrent Booking Race Condition (Double-Booking Prevention)
* **Edge Case**: Only 1 compatible slot remains (e.g., `C51` EV car slot), and two users click "Book" at the exact same millisecond. Without locking, both transactions would read `occupied = 0` and both would book `C51`.
* **Technique**: `create_booking()` locks all compatible `ParkingSlot` rows using PostgreSQL pessimistic row locking:
  ```python
  if db.bind is not None and db.bind.dialect.name == "postgresql":
      slot_stmt = slot_stmt.with_for_update()
  ```
  Transaction B blocks until Transaction A commits its `PAYMENT_PENDING` booking, then Transaction B sees `C51` as occupied and cleanly returns `409 NO_PARKING_CAPACITY`. (The `dialect.name == "postgresql"` guard keeps SQLite unit tests compatible.)

### 3.2 Time-Interval Overlap & Back-to-Back Bookings
* **Edge Case**: Slot `C01` is booked `09:00–11:00`. A second user requests `11:00–13:00` (allowed) vs. `10:00–12:00` (conflict).
* **Technique**: Half-open interval overlap predicate:
  ```python
  Booking.start_time < end_time,
  Booking.end_time > start_time,
  ```
  When `start_time == 11:00` and existing `end_time == 11:00`, `11:00 > 11:00` is `False`, so back-to-back bookings do not conflict.

### 3.3 Same-User Overlapping Bookings
* **Edge Case**: One employee tries to hoard multiple slots at the same time (e.g., for two different vehicles).
* **Technique**: Before assigning a slot, `create_booking()` checks for any active booking by `auth.user_id` overlapping the requested interval and raises `409 USER_BOOKING_OVERLAP`.

### 3.4 Abandoned Holds & Lazy Hold Expiry (No Background Cron Needed)
* **Edge Case**: User creates a booking (`PAYMENT_PENDING` with a 5-minute `hold_expires_at`) and closes the browser without paying.
* **Technique**: Two-part lazy expiry:
  1. **Immediate slot release**: `_active_booking_filter(now_utc)` only counts `CONFIRMED` bookings or `PAYMENT_PENDING` bookings where `hold_expires_at > now_utc`. As soon as 5 minutes pass, other users immediately see the slot as available—even before the row's `status` column is updated.
  2. **Lazy status cleanup**: `_expire_stale_holds()` updates expired `PAYMENT_PENDING` rows to `EXPIRED` whenever the user views (`list_bookings`, `get_booking`) or attempts to cancel (`cancel_booking`) their bookings.

### 3.5 Vehicle Snapshot Isolation Across Microservices
* **Edge Case**: User books a slot with vehicle `KA01AB1234`, then later edits the plate or deactivates the vehicle in `vehicle-service`.
* **Technique**: `create_booking()` fetches the vehicle from `vehicle-service` once and stores `vehicle_number_snapshot`, `vehicle_type_snapshot`, and `is_ev_snapshot` directly on the `Booking` row in `parking_db`. Past/active bookings never break or mutate if the vehicle changes later.

### 3.6 Business Window, Timezone, EV & Cancellation Rules
* **Business Timezone (`Asia/Kolkata`)**: `validate_booking_interval()` converts `now` to `get_business_tz()` so midnight rollovers and operating hours (`07:00–22:00`) match local facility time rather than UTC.
* **Booking Horizon & Sunday Closure**: Rejects dates other than `today` or `tomorrow`, and rejects `booking_date.weekday() == 6` (`422 BOOKING_WINDOW_VIOLATION`).
* **Whole-Hour & Duration Limits**: Rejects non-zero minutes/seconds, times outside `07:00–22:00`, `end_time <= start_time`, durations `> 12` hours, and `start_dt <= now_local` (`422 INVALID_BOOKING_TIME`).
* **EV Charging Mismatch**: `validate_charging_compatibility()` rejects `requires_charging=True` when `vehicle.is_ev=False` (`422 CHARGING_NOT_SUPPORTED`).
* **Cancellation Cutoff**: `cancel_booking()` runs `_expire_stale_holds()` first, rejects non-`CONFIRMED` bookings (`409 BOOKING_NOT_CANCELLABLE`), and rejects `CONFIRMED` bookings once `now_local >= start_dt` (`can_cancel_booking`).

### 3.7 Late Payment Callbacks & Idempotency (`internal.py`)
* **Late Payment After Hold Expiry (No Resurrection)**: If Payment Service delivers a `SUCCESS` callback after `hold_expires_at <= now_utc` (or if the booking was already marked `EXPIRED`), `apply_payment_result()` does **not** confirm the booking (because another user may already have booked that slot!). It marks it `EXPIRED` and returns `EXPIRED_NO_RESURRECTION`.
* **Idempotent Callback**: If the booking is already `CONFIRMED`, it returns `200 OK` with `result="ALREADY_APPLIED"`.
* **Cancelled Booking / Payment Mismatch**: Callback against a `CANCELLED` booking raises `409 INVALID_BOOKING_TRANSITION`; mismatched `payment_id` raises `409 PAYMENT_REFERENCE_MISMATCH`.
* **Downstream Outage Handling (`clients.py`)**: `VehicleServiceClient` and `PaymentServiceClient` wrap `httpx.Client(timeout=3.0)` errors into clean `503 VEHICLE_SERVICE_UNAVAILABLE` / `503 PAYMENT_SERVICE_UNAVAILABLE` responses.

---

## 4. Payment Service (`services/payment-service`)

Implemented in [payments.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/payment-service/app/api/v1/payments.py) and [parking_callback.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/payment-service/app/services/parking_callback.py).

### 4.1 Idempotent Internal Payment Creation
* **Edge Case**: `parking-service` retries `POST /internal/v1/payments` for the same `booking_id`.
* **Technique**: `create_internal_payment()` checks `Payment.booking_id == payload.booking_id`:
  * If it exists with the **same** `user_id` and `amount`, it returns `200 OK` with the existing `payment_id` (idempotent).
  * If `user_id` or `amount` differs, it raises `409 PAYMENT_REQUEST_CONFLICT`.

### 4.2 Double-Payment & Expired Window Guards
* **Edge Case**: User clicks "Pay" twice rapidly, or submits payment after the 5-minute window expires.
* **Technique**: `process_payment()` enforces:
  1. Ownership check: `(Payment.id == payment_id, Payment.user_id == user_id)` -> `404 PAYMENT_NOT_FOUND`.
  2. Status guard: `payment.status != "PENDING"` -> `409 PAYMENT_ALREADY_PROCESSED`.
  3. Expiry guard: `_as_utc(now_utc) >= _as_utc(payment.expires_at)` -> `409 PAYMENT_EXPIRED`.

### 4.3 Test Payment Override Guarded from Production
* **Edge Case**: `X-Test-Payment-Outcome: FAILED` header is useful for automated testing, but must never let a user fake payment outcomes in production.
* **Technique**: `_resolve_simulated_outcome()` only reads `X-Test-Payment-Outcome` when **both** `settings.ENABLE_TEST_PAYMENT_OVERRIDE` is `True` **and** `settings.ENVIRONMENT.strip().lower() != "production"`.

### 4.4 Resilient Callback Delivery
* **Edge Case**: `parking-service` is temporarily slow or unreachable when `payment-service` sends the result callback.
* **Technique**: `ParkingCallbackClient.deliver_payment_result()` uses a 3.0-second `httpx.Client` timeout and catches `httpx.HTTPError`, returning `False` rather than crashing after the `Payment` row is already committed.
