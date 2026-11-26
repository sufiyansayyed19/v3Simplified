# Business Rules

This document records the simplified, fresher-friendly business rules governing authentication, vehicles, availability, bookings, slot allocation, pricing, payment, and cancellation.

---

## 1. Organization and Parking Capacity

| Resource | Count | Breakdown |
|---|---:|---|
| Total spaces | 100 | 60 car + 40 bike |
| Car spaces | 60 | 50 normal (`C01–C50`) + 10 charging-enabled (`C51–C60`) |
| Bike spaces | 40 | 35 normal (`B01–B35`) + 5 charging-enabled (`B36–B40`) |
| Charging-enabled spaces | 15 | 10 car + 5 bike |

All 100 slots are automatically seeded on `parking-service` startup if `parking_slots` is empty.

---

## 2. Operating Calendar and Simplified Time Rules

1. **Timezone & Operating Days:**
   - Business timezone is `Asia/Kolkata`.
   - Open **Monday through Saturday** (`07:00` to `22:00`).
   - **Closed on Sundays** (`weekday() == 6`).
2. **Booking Horizon:**
   - Bookings are allowed only for **today** or **tomorrow**.
3. **Whole-Hour Future Slots:**
   - `start_time` and `end_time` must be whole hours (`minute == 0`, `second == 0`) within `07:00–22:00`, with `end_time > start_time`.
   - Maximum duration is **12 hours**.
   - **Simple future rule:** `start_time` must be strictly in the future (`start_dt > now`).
4. **Simple Cancellation Rule:**
   - A `CONFIRMED` booking can be cancelled anytime before its scheduled `start_time` (`now < start_dt`).

---

## 3. Vehicle Rules

- Supported vehicle types: `CAR` and `BIKE`.
- Vehicle registration numbers are normalized by trimming, converting to uppercase, and stripping spaces and hyphens (`"mh 12-ab 1234"` → `"MH12AB1234"`).
- A user cannot register two active vehicles with the same normalized plate (`409 VEHICLE_ALREADY_REGISTERED`).
- `DELETE /api/v1/vehicles/{vehicle_id}` performs a **soft delete** (`is_active = false`), allowing a previously removed plate to be re-registered later as a new active row.
- Because `bookings` captures immutable vehicle snapshots (`vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`) at booking creation time, `Vehicle Service` is 100% standalone and does not need to call `Parking Service` during vehicle updates or deactivation.

---

## 4. Charging and Slot Compatibility

| Vehicle | Charging Requested? | Compatible Slot Pool | Hourly Rate |
|---|---|---|---:|
| Non-EV Car | `false` | Normal Car (`C01–C50`) | ₹10/hr |
| Non-EV Car | `true` | Rejected (`422 CHARGING_NOT_SUPPORTED`) | — |
| EV Car | `false` | Normal Car (`C01–C50`) | ₹10/hr |
| EV Car | `true` | Charging Car (`C51–C60`) | ₹20/hr |
| Non-EV Bike | `false` | Normal Bike (`B01–B35`) | ₹10/hr |
| Non-EV Bike | `true` | Rejected (`422 CHARGING_NOT_SUPPORTED`) | — |
| EV Bike | `false` | Normal Bike (`B01–B35`) | ₹10/hr |
| EV Bike | `true` | Charging Bike (`B36–B40`) | ₹20/hr |

---

## 5. Overlap, Temporary Holds, and Booking State Machine

Two intervals overlap when:
`new_start < existing_end AND new_end > existing_start`
(Adjacent intervals such as `10:00–12:00` and `12:00–14:00` do **not** overlap.)

- **No Same-User Overlap:** A user cannot hold two overlapping active bookings (`CONFIRMED` or unexpired `PAYMENT_PENDING`), even across different vehicles (`409 USER_BOOKING_OVERLAP`).
- **5-Minute Hold:** `POST /api/v1/parking/bookings` creates a `PAYMENT_PENDING` booking with `hold_expires_at = now + 5 minutes`.
- **State Transitions:**
  - `PAYMENT_PENDING` → `CONFIRMED` (when payment callback reports `SUCCESS` before `hold_expires_at`).
  - `PAYMENT_PENDING` → `EXPIRED` (when payment fails or `hold_expires_at <= now`).
  - `CONFIRMED` → `CANCELLED` (when user cancels before `start_time`).

---

## 6. Availability and Slot Allocation Rules

- **Informational Availability:** `GET /api/v1/parking/availability` returns a real-time count of compatible free slots (`CONFIRMED` and unexpired `PAYMENT_PENDING` bookings are treated as occupied), but it does **not** reserve a slot.
- **Authoritative Allocation:** `POST /api/v1/parking/bookings` locks compatible `ParkingSlot` rows (`SELECT ... FOR UPDATE`), picks the first unoccupied slot in ascending `slot_number` order (`C01..C60`, `B01..B40`), and rejects with `409 NO_PARKING_CAPACITY` if none remain.
- **No User-Selected Slots & No Waitlist:** Users select a vehicle and time interval; the system auto-assigns the slot. Booking modification/extension is not supported—users cancel and create a new booking.

---

## 7. Authentication and Payment Rules

- **Corporate-Email OTP Only:** Only email addresses matching `COMPANY_EMAIL_DOMAIN` (default `company.com`) are permitted (`403 CORPORATE_EMAIL_REQUIRED`). OTPs are 6 digits, expire in `OTP_EXPIRE_MINUTES` (5 minutes), and are single-use (`consumed_at` is set on verification and prior unused codes are invalidated when a new code is requested).
- **Simulated Payments:** Allowed methods are `UPI`, `CARD`, and `WALLET`. Parking Service calculates `amount` (`₹10/hr` or `₹20/hr`); the client cannot supply an amount or payment status.
- **One Payment Per Booking & No Resurrection:** `payments.booking_id` is unique. Failed or expired payments transition the booking to `EXPIRED` (no retry on the same booking; user creates a new booking). A late `SUCCESS` callback after `hold_expires_at <= now` never resurrects an `EXPIRED` booking.
