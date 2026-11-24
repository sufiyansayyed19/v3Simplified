# Parking Service API Contract

**Service Path:** `services/parking-service/` | **Port:** `8003` | **Database:** `parking_db` (`parking_slots`, `bookings`)

---

## 1. Responsibilities
Parking Service owns the 100 parking slots (`parking_slots`) and all booking records (`bookings`). On startup, it automatically creates its tables and seeds the 100 slots (`C01–C60`, `B01–B40`) if `parking_slots` is empty. It also includes an **Alembic** migration setup (`services/parking-service/alembic/`).

---

## 2. Endpoint Inventory (6 Endpoints: 5 Public + 1 Internal)

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/parking/availability` | Bearer JWT | Check compatible free slot count and hourly rate |
| `POST` | `/api/v1/parking/bookings` | Bearer JWT | Lock & allocate a compatible slot, create 5-min hold, initiate payment |
| `GET` | `/api/v1/parking/bookings` | Bearer JWT | List user's bookings (paginated, with lazy hold expiry) |
| `GET` | `/api/v1/parking/bookings/{booking_id}` | Bearer JWT | Retrieve single booking detail (with lazy hold expiry) |
| `POST` | `/api/v1/parking/bookings/{booking_id}/cancel` | Bearer JWT | Cancel a `CONFIRMED` booking before `start_time` |
| `POST` | `/internal/v1/bookings/{booking_id}/payment-result` | `X-Internal-Service-Token` | Internal callback from Payment Service to confirm or expire a booking |

---

## 3. `GET /api/v1/parking/availability`

Query parameters: `date`, `start_time`, `end_time`, `vehicle_id`, `requires_charging`.
1. Validates simplified time rules (`07:00–22:00`, whole hours, today/tomorrow, not Sunday, `start_time > now`).
2. Calls `Vehicle Service` (`GET /api/v1/vehicles/{vehicle_id}`) with the user's Bearer JWT.
3. Rejects non-EV requesting charging (`422 CHARGING_NOT_SUPPORTED`).
4. Counts compatible slots not occupied by overlapping `CONFIRMED` or unexpired `PAYMENT_PENDING` bookings.

---

## 4. `POST /api/v1/parking/bookings`

### Request Body
```json
{
  "vehicle_id": "<vehicle-uuid>",
  "date": "2026-11-25",
  "start_time": "10:00",
  "end_time": "12:00",
  "requires_charging": true
}
```

### Processing
1. Validates time rules and calls `Vehicle Service` to fetch vehicle details.
2. Locks compatible `ParkingSlot` rows ordered by `slot_number ASC` using SQLAlchemy `.with_for_update()` (`SELECT ... FOR UPDATE`).
3. Checks that the user has no overlapping active booking (`409 USER_BOOKING_OVERLAP`).
4. Picks the first unoccupied compatible slot (`409 NO_PARKING_CAPACITY` if none).
5. Inserts `Booking` with `status = "PAYMENT_PENDING"`, `hold_expires_at = now + 5 min`, `amount` (`₹10/hr` or `₹20/hr`), and vehicle snapshots (`vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`), then commits.
6. Calls `Payment Service` (`POST /internal/v1/payments`) with `X-Internal-Service-Token`, saves `payment_id` on the booking, and returns `201 Created`.

---

## 5. `GET /api/v1/parking/bookings`, `GET /{booking_id}` & `POST /{booking_id}/cancel`
- `GET` endpoints lazily flip any `PAYMENT_PENDING` booking with `hold_expires_at <= now` to `EXPIRED`.
- `POST /api/v1/parking/bookings/{booking_id}/cancel` requires `status == "CONFIRMED"` and `now < start_time` (`409 BOOKING_NOT_CANCELLABLE` otherwise), transitioning the booking to `CANCELLED`.

---

## 6. Internal `POST /internal/v1/bookings/{booking_id}/payment-result`
Protected by `X-Internal-Service-Token`. Transitions a `PAYMENT_PENDING` booking to `CONFIRMED` if `status == "SUCCESS"` and the 5-minute hold has not expired; otherwise transitions it to `EXPIRED`.
