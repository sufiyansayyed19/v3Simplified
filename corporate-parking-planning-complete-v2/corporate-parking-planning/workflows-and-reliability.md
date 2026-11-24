# End-to-End Workflows and Reliability

## 1. Core End-to-End User Journey

```mermaid
sequenceDiagram
    participant U as Employee (Swagger UI)
    participant A as User/Auth (:8001)
    participant V as Vehicle (:8002)
    participant P as Parking (:8003)
    participant PAY as Payment (:8004)

    U->>A: 1. POST /api/v1/auth/company/send-code & /verify
    A-->>U: HS256 JWT access_token

    U->>V: 2. POST /api/v1/vehicles (Register EV Car)
    V-->>U: 201 {id: vehicle_id}

    U->>P: 3. GET /api/v1/parking/availability
    P->>V: GET /api/v1/vehicles/{vehicle_id} (Bearer JWT)
    V-->>P: {vehicle_type: CAR, is_ev: true, is_active: true}
    P-->>U: 200 {available: true, rate_per_hour: 20.00}

    U->>P: 4. POST /api/v1/parking/bookings
    P->>V: Re-verify vehicle
    P->>P: SELECT compatible parking_slots ... FOR UPDATE
    P->>P: Check user overlap & pick first free slot (e.g. C51)
    P->>P: Commit PAYMENT_PENDING booking (5-min hold + vehicle snapshots)
    P->>PAY: POST /internal/v1/payments (X-Internal-Service-Token)
    PAY-->>P: 201 {payment_id, status: PENDING}
    P-->>U: 201 {booking_id, slot_number: C51, status: PAYMENT_PENDING, payment_id}

    U->>PAY: 5. POST /api/v1/payments/{payment_id}/process {payment_method: UPI}
    PAY->>PAY: Save status = SUCCESS, transaction_id = TXN...
    PAY->>P: POST /internal/v1/bookings/{booking_id}/payment-result
    P-->>PAY: 200 {status: CONFIRMED, result: APPLIED}
    PAY-->>U: 200 {status: SUCCESS, transaction_id: TXN...}

    U->>P: 6. POST /api/v1/parking/bookings/{booking_id}/cancel (before start_time)
    P-->>U: 200 {status: CANCELLED}
```

---

## 2. Concurrency Protection (`SELECT ... FOR UPDATE`)

Inside `POST /api/v1/parking/bookings`:
1. `Parking Service` queries all compatible `ParkingSlot` rows (`vehicle_type == vehicle.vehicle_type` and `is_charging_enabled == payload.requires_charging`) ordered by `slot_number ASC` with `.with_for_update()`.
2. In PostgreSQL, `SELECT ... FOR UPDATE` locks those slot rows for the duration of the transaction, serializing concurrent booking attempts.
3. While holding the row locks, `Parking Service` checks for same-user overlap (`409 USER_BOOKING_OVERLAP`) and occupied slots, picks the first free slot (`409 NO_PARKING_CAPACITY` if all are taken), inserts the `PAYMENT_PENDING` booking, and commits before calling `Payment Service`.

---

## 3. Lazy Hold Expiry (No Background Daemons Needed)

- Every `PAYMENT_PENDING` booking has `hold_expires_at = created_at + 5 minutes`.
- Availability and overlap queries only treat a `PAYMENT_PENDING` booking as active if `hold_expires_at > now()`.
- Whenever `GET /api/v1/parking/bookings`, `GET /api/v1/parking/bookings/{id}`, `POST /cancel`, or the internal payment callback accesses a `PAYMENT_PENDING` booking whose `hold_expires_at <= now()`, it automatically updates `status = "EXPIRED"`.
