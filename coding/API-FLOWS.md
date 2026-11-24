# Corporate Parking Reservation System — API Flow Diagrams

Visual guide to all **17 APIs** across the **4 Microservices** (`8001`–`8004`), showing the exact request/response flow, database writes, JWT validation, and inter-service HTTP calls (`httpx`).

---

## 1. System Architecture Overview

Each microservice runs independently with its own Swagger UI (`/docs`) and isolated PostgreSQL database (`user_db`, `vehicle_db`, `parking_db`, `payment_db`).

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

    Park -.->|"1. GET /api/v1/vehicles/{id}\n(Forwarded Bearer JWT)"| Veh
    Park -.->|"2. POST /internal/v1/payments\n(X-Internal-Service-Token)"| Pay
    Pay -.->|"3. POST /internal/v1/bookings/{id}/payment-result\n(X-Internal-Service-Token)"| Park
```

---

## 2. User/Auth Service (`services/user-auth-service` — Port `8001`, 3 APIs)

Authentication is corporate-email OTP based (`COMPANY_EMAIL_DOMAIN`) issuing stateless **HS256 JWT** access tokens.

```mermaid
sequenceDiagram
    participant C as Client / Swagger
    participant A as User/Auth (:8001)
    participant DB as user_db
    participant Mail as ConsoleEmailSender

    Note over C,Mail: 1. Send Corporate Email OTP
    C->>A: POST /api/v1/auth/company/send-code {email}
    A->>A: Normalize email & check COMPANY_EMAIL_DOMAIN (403 if invalid)
    A->>DB: Mark previous unconsumed codes as consumed_at = now
    A->>DB: Insert 6-digit VerificationCode (5-min expiry)
    A->>Mail: Print [DEV EMAIL OTP] To: ... | Code: 123456
    A-->>C: 200 {"message": "Verification code sent successfully"}

    Note over C,Mail: 2. Verify OTP & Issue HS256 JWT
    C->>A: POST /api/v1/auth/company/verify {email, code}
    A->>DB: Load latest unconsumed VerificationCode
    alt Missing, expired, or wrong code
        A-->>C: 401 INVALID_OR_EXPIRED_CODE
    else Valid code
        A->>DB: Set consumed_at = now
        A->>DB: Find or create User in users table
        A->>A: Sign HS256 JWT (sub = user.id, 60-min exp)
        A-->>C: 200 {access_token, token_type: "bearer", expires_in, user}
    end

    Note over C,Mail: 3. Fetch Current User Profile
    C->>A: GET /api/v1/users/me (Authorization: Bearer JWT)
    A->>A: Verify HS256 JWT signature & extract user_id (sub)
    A->>DB: Lookup User by user_id
    A-->>C: 200 {id, email, name}
```

---

## 3. Vehicle Service (`services/vehicle-service` — Port `8002`, 5 APIs)

Standalone owner-scoped CRUD service on `vehicle_db`. All 5 endpoints verify the HS256 Bearer JWT locally.

```mermaid
sequenceDiagram
    participant C as Client / Swagger
    participant V as Vehicle (:8002)
    participant VDB as vehicle_db

    Note over C,VDB: 1. Register Vehicle
    C->>V: POST /api/v1/vehicles {vehicle_number, vehicle_type, is_ev}
    V->>V: Validate HS256 JWT & normalize plate ("mh 12-ab 1234" -> "MH12AB1234")
    V->>VDB: Check duplicate active plate for user_id (409 if exists)
    V->>VDB: Insert Vehicle (is_active = true)
    V-->>C: 201 {id, vehicle_number, vehicle_type, is_ev, is_active: true}

    Note over C,VDB: 2. List & Get Active Vehicles (Owner-Scoped)
    C->>V: GET /api/v1/vehicles  |  GET /api/v1/vehicles/{id}
    V->>VDB: Query WHERE user_id = sub AND is_active = true (404 if non-owned/inactive)
    V-->>C: 200 Vehicle list or single vehicle

    Note over C,VDB: 3. Update & Soft-Deactivate Vehicle
    C->>V: PUT /api/v1/vehicles/{id} {vehicle_number, vehicle_type, is_ev}
    V->>VDB: Verify owner & active status; check duplicate plate; update & commit
    V-->>C: 200 Updated vehicle

    C->>V: DELETE /api/v1/vehicles/{id}
    V->>VDB: Verify owner & active status; set is_active = false
    V-->>C: 200 {id, is_active: false, message: "Vehicle removed successfully"}
```

---

## 4. Parking Service (`services/parking-service` — Port `8003`, 5 Public + 1 Internal API)

### 4.1 Availability & Atomic Booking Creation (`SELECT ... FOR UPDATE` + 5-Min Hold)

```mermaid
sequenceDiagram
    participant C as Client / Swagger
    participant P as Parking (:8003)
    participant V as Vehicle (:8002)
    participant PDB as parking_db
    participant PAY as Payment (:8004)

    Note over C,PDB: 1. Informational Availability Check
    C->>P: GET /api/v1/parking/availability?date&start_time&end_time&vehicle_id&requires_charging
    P->>P: Validate time rules (Mon-Sat, 07:00-22:00, whole hrs, today/tomorrow, start > now)
    P->>V: GET /api/v1/vehicles/{vehicle_id} (Forwarded Bearer JWT)
    V-->>P: {vehicle_type, is_ev, is_active} (404 if non-owned/inactive, 503 if down)
    P->>P: Reject non-EV requesting charging (422 CHARGING_NOT_SUPPORTED)
    P->>PDB: Count compatible slots not overlapping CONFIRMED or unexpired PAYMENT_PENDING
    P-->>C: 200 {available, available_slots, rate_per_hour (10.00 or 20.00)}

    Note over C,PAY: 2. Create Booking (Row Locking + 5-Min Hold + Initiate Payment)
    C->>P: POST /api/v1/parking/bookings {vehicle_id, date, start_time, end_time, requires_charging}
    P->>P: Validate time rules + calculate amount (₹10/hr or ₹20/hr)
    P->>V: GET /api/v1/vehicles/{vehicle_id} (Forwarded Bearer JWT)
    V-->>P: Verified vehicle attributes
    rect rgb(235, 245, 255)
        Note over P,PDB: Single PostgreSQL Transaction
        P->>PDB: SELECT compatible parking_slots ORDER BY slot_number ASC FOR UPDATE
        P->>PDB: Check same-user overlap (409 USER_BOOKING_OVERLAP)
        P->>PDB: Pick first unoccupied slot (409 NO_PARKING_CAPACITY if none)
        P->>PDB: INSERT Booking (PAYMENT_PENDING, 5m hold, vehicle snapshots) & COMMIT
    end
    P->>PAY: POST /internal/v1/payments (X-Internal-Service-Token)
    PAY-->>P: 201 {payment_id, status: PENDING}
    P->>PDB: UPDATE bookings SET payment_id = ... & COMMIT
    P-->>C: 201 {booking_id, slot_number, snapshots, amount, status: PAYMENT_PENDING, payment_id, hold_expires_at}
```

### 4.2 Booking History, Lazy Hold Expiry & Cancellation

```mermaid
sequenceDiagram
    participant C as Client / Swagger
    participant P as Parking (:8003)
    participant PDB as parking_db

    Note over C,PDB: 1. List / Detail (with Lazy Hold Expiry)
    C->>P: GET /api/v1/parking/bookings?page=1&page_size=20  |  GET /api/v1/parking/bookings/{id}
    P->>PDB: Query owner's bookings
    P->>PDB: If any PAYMENT_PENDING has hold_expires_at <= now -> flip to EXPIRED
    P-->>C: 200 Paginated items or single booking

    Note over C,PDB: 2. Cancel Confirmed Booking
    C->>P: POST /api/v1/parking/bookings/{id}/cancel
    P->>PDB: Load owner's booking (404 if missing) & run lazy expiry
    P->>P: Require status == CONFIRMED AND now < start_time
    alt Not confirmed or already started
        P-->>C: 409 BOOKING_NOT_CANCELLABLE
    else Eligible
        P->>PDB: UPDATE status = CANCELLED, cancelled_at = now
        P-->>C: 200 {booking_id, status: CANCELLED, cancelled_at}
    end
```

### 4.3 Booking State Machine

```mermaid
stateDiagram-v2
    [*] --> PAYMENT_PENDING: POST /bookings (5-min hold)
    PAYMENT_PENDING --> CONFIRMED: Payment callback SUCCESS (while hold valid)
    PAYMENT_PENDING --> EXPIRED: Payment callback FAILED
    PAYMENT_PENDING --> EXPIRED: Hold expires (lazy expiry or late callback)
    CONFIRMED --> CANCELLED: POST /cancel (before start_time)
    EXPIRED --> [*]
    CANCELLED --> [*]
```

---

## 5. Payment Service (`services/payment-service` — Port `8004`, 1 Internal + 2 Public APIs)

```mermaid
sequenceDiagram
    participant C as Client / Swagger
    participant PAY as Payment (:8004)
    participant PAYDB as payment_db
    participant P as Parking (:8003)
    participant PDB as parking_db

    Note over P,PAYDB: 1. Internal Payment Creation (Called by Parking Service)
    P->>PAY: POST /internal/v1/payments {booking_id, user_id, amount, expires_at}
    PAY->>PAY: Validate X-Internal-Service-Token (401 if invalid)
    PAY->>PAYDB: Check UNIQUE(booking_id) (200 replay if identical, 409 if mismatch)
    PAY->>PAYDB: INSERT Payment (status = PENDING)
    PAY-->>P: 201 {payment_id, booking_id, amount, status: PENDING, expires_at}

    Note over C,PDB: 2. Process Simulated Payment & Notify Parking
    C->>PAY: POST /api/v1/payments/{id}/process {payment_method: UPI|CARD|WALLET}
    PAY->>PAYDB: Load owner's payment (404 if non-owned)
    PAY->>PAY: Reject if status != PENDING (409) or now >= expires_at (409)
    PAY->>PAY: Resolve outcome (default SUCCESS or non-prod X-Test-Payment-Outcome)
    PAY->>PAYDB: Save payment_method, status (SUCCESS/FAILED), transaction_id (TXN...) & COMMIT
    PAY->>P: POST /internal/v1/bookings/{booking_id}/payment-result (X-Internal-Service-Token)
    P->>P: Validate X-Internal-Service-Token
    P->>PDB: Load booking, verify payment_id, check Parking clock (never resurrect EXPIRED!)
    P->>PDB: Transition PAYMENT_PENDING -> CONFIRMED or EXPIRED (idempotent on duplicates)
    P-->>PAY: 200 {booking_id, status, result: APPLIED | ALREADY_APPLIED}
    PAY-->>C: 200 {payment_id, booking_id, amount, status, transaction_id}

    Note over C,PAYDB: 3. Retrieve Payment Details
    C->>PAY: GET /api/v1/payments/{id}
    PAY->>PAYDB: SELECT WHERE id = payment_id AND user_id = sub (404 if non-owned)
    PAY-->>C: 200 Payment details
```

---

## 6. Complete End-to-End User Journey (All 4 Microservices)

```mermaid
sequenceDiagram
    participant U as Employee (Swagger UI)
    participant A as User/Auth (:8001)
    participant V as Vehicle (:8002)
    participant P as Parking (:8003)
    participant PAY as Payment (:8004)

    U->>A: 1. POST /auth/company/send-code & /verify
    A-->>U: HS256 access_token

    U->>V: 2. POST /api/v1/vehicles (Register EV Car)
    V-->>U: 201 {id: vehicle_id}

    U->>P: 3. GET /api/v1/parking/availability
    P->>V: Verify vehicle ownership & EV flag
    V-->>P: Vehicle OK (CAR, is_ev=true)
    P-->>U: 200 {available: true, rate_per_hour: 20.00}

    U->>P: 4. POST /api/v1/parking/bookings
    P->>V: Re-verify vehicle
    P->>PAY: POST /internal/v1/payments
    PAY-->>P: 201 {payment_id}
    P-->>U: 201 {booking_id, slot_number: "C51", status: PAYMENT_PENDING, payment_id}

    U->>PAY: 5. POST /api/v1/payments/{payment_id}/process {UPI}
    PAY->>P: POST /internal/v1/bookings/{booking_id}/payment-result (SUCCESS)
    P-->>PAY: 200 {status: CONFIRMED}
    PAY-->>U: 200 {status: SUCCESS, transaction_id: "TXN..."}

    U->>P: 6. GET /api/v1/parking/bookings/{booking_id}
    P-->>U: 200 {status: CONFIRMED}

    U->>P: 7. POST /api/v1/parking/bookings/{booking_id}/cancel (before start_time)
    P-->>U: 200 {status: CANCELLED}
```
