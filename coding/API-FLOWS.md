# Corporate Parking Reservation System — API Flow Diagrams

Visual guide to all **17 APIs** across the **4 Microservices** (`8001`–`8004`).

---

## 1. System Architecture Overview

Each microservice runs independently with its own Swagger UI (`/docs`) and isolated PostgreSQL database.

```mermaid
flowchart LR
    Client["Client / Swagger UI"] -->|":8001 /api/v1/auth/* & /users/me"| Auth["User/Auth Service (:8001)"]
    Client -->|":8002 /api/v1/vehicles/* (HS256 JWT)"| Veh["Vehicle Service (:8002)"]
    Client -->|":8003 /api/v1/parking/* (HS256 JWT)"| Park["Parking Service (:8003)"]
    Client -->|":8004 /api/v1/payments/* (HS256 JWT)"| Pay["Payment Service (:8004)"]

    Auth --- UDB[("user_db\n(users, verification_codes)")]
    Veh --- VDB[("vehicle_db\n(vehicles)")]
    Park --- PDB[("parking_db\n(parking_slots, bookings)")]
    Pay --- PAYDB[("payment_db\n(payments)")]

    Park -.->|"1. GET /api/v1/vehicles/{id}\n(Bearer JWT)"| Veh
    Park -.->|"2. POST /internal/v1/payments\n(X-Internal-Service-Token)"| Pay
    Pay -.->|"3. POST /internal/v1/bookings/{id}/payment-result\n(X-Internal-Service-Token)"| Park
```

---

## 2. User/Auth Service (`services/user-auth-service` — Port `8001`, 3 APIs)

1. `POST /api/v1/auth/company/send-code` — Validates `@company.com` email, saves a 6-digit OTP in `verification_codes` (5-min expiry), and prints the OTP to the console.
2. `POST /api/v1/auth/company/verify` — Verifies the 6-digit OTP, marks `is_used = True`, finds or creates the `User` in `users`, and returns an **HS256 JWT `access_token`**.
3. `GET /api/v1/users/me` — Decodes the Bearer JWT and returns `{id, email, name}`.

---

## 3. Vehicle Service (`services/vehicle-service` — Port `8002`, 5 APIs)

Standalone owner-scoped CRUD service on `vehicle_db`:
1. `POST /api/v1/vehicles` — Normalizes plate (e.g. `"mh 12-ab 1234"` → `"MH12AB1234"`), checks for duplicate active plate, inserts `Vehicle`.
2. `GET /api/v1/vehicles` — Lists active vehicles owned by the authenticated user.
3. `GET /api/v1/vehicles/{vehicle_id}` — Fetches a single active vehicle owned by the user (also called by `parking-service` during availability/booking).
4. `PUT /api/v1/vehicles/{vehicle_id}` — Updates vehicle details.
5. `DELETE /api/v1/vehicles/{vehicle_id}` — Soft-deletes the vehicle (`is_active = False`).

---

## 4. Parking Service (`services/parking-service` — Port `8003`, 5 Public + 1 Internal API)

On startup, automatically creates `parking_slots` and `bookings` and seeds the 100 slots (`C01–C50` normal CAR, `C51–C60` EV CAR, `B01–B35` normal BIKE, `B36–B40` EV BIKE).

1. `GET /api/v1/parking/availability` — Validates time rules (`07:00–22:00`, whole hours, today/tomorrow, not Sunday, future `start_time`), calls Vehicle Service to check EV compatibility, and counts available slots.
2. `POST /api/v1/parking/bookings` — Locks compatible `ParkingSlot` rows (`SELECT ... FOR UPDATE`), checks user overlap, allocates the first free slot with a 5-minute `PAYMENT_PENDING` hold, stores vehicle snapshots, and calls Payment Service (`POST /internal/v1/payments`).
3. `GET /api/v1/parking/bookings` — Paginated booking history (lazily expires stale holds).
4. `GET /api/v1/parking/bookings/{booking_id}` — Single booking detail.
5. `POST /api/v1/parking/bookings/{booking_id}/cancel` — Cancels a `CONFIRMED` booking before `start_time`.
6. `POST /internal/v1/bookings/{booking_id}/payment-result` *(Internal)* — Called by Payment Service to transition `PAYMENT_PENDING` → `CONFIRMED` (or `EXPIRED`).

---

## 5. Payment Service (`services/payment-service` — Port `8004`, 1 Internal + 2 Public APIs)

1. `POST /internal/v1/payments` *(Internal)* — Called by Parking Service to create a `PENDING` payment for a booking.
2. `POST /api/v1/payments/{payment_id}/process` — Simulates payment (`UPI`, `CARD`, `WALLET`), generates `TXN...`, updates status to `SUCCESS` (or `FAILED`), and calls Parking Service's `/internal/v1/bookings/{id}/payment-result`.
3. `GET /api/v1/payments/{payment_id}` — Returns payment details.
