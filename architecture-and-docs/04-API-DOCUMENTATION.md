# REST API Specification

## 1. API Conventions & Authentication

### 1.1 Service Base URLs
| Service | Local Base URL | OpenAPI / Swagger UI | Health Endpoint |
| :--- | :--- | :--- | :--- |
| **User & Auth Service** | `http://127.0.0.1:8001` | `http://127.0.0.1:8001/docs` | `GET /health` |
| **Vehicle Service** | `http://127.0.0.1:8002` | `http://127.0.0.1:8002/docs` | `GET /health` |
| **Parking Service** | `http://127.0.0.1:8003` | `http://127.0.0.1:8003/docs` | `GET /health` |
| **Payment Service** | `http://127.0.0.1:8004` | `http://127.0.0.1:8004/docs` | `GET /health` |

### 1.2 Authentication Schemes
* **Public Protected Endpoints (`/api/v1/*`)**:
  ```http
  Authorization: Bearer <access_token>
  ```
* **Internal Service-to-Service Endpoints (`/internal/v1/*`)**:
  ```http
  X-Internal-Service-Token: <INTERNAL_SERVICE_TOKEN>
  ```

### 1.3 Standard Error Envelope
Every non-2xx response across all services returns:
```json
{
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "Human-readable explanation.",
    "request_id": "uuid-v4-correlation-id"
  }
}
```

### 1.4 Health Check (All 4 Services)
* **Endpoint**: `GET /health` (Auth: None)
* **Response (`200 OK`)**:
  ```json
  {
    "status": "ok",
    "service": "parking-service"
  }
  ```

---

## 2. User & Auth Service (`:8001`)

### 2.1 Request Corporate OTP
* **Method & Path**: `POST /api/v1/auth/company/send-code`
* **Auth**: None
* **Request Body**:
  ```json
  {
    "email": "alice@company.com"
  }
  ```
* **Success Response (`200 OK`)**:
  ```json
  {
    "message": "Verification code sent successfully"
  }
  ```
* **Errors**:
  * `403 CORPORATE_EMAIL_REQUIRED` — Email domain does not match `company.com`.
  * `422 INVALID_REQUEST` — Malformed email format.

---

### 2.2 Verify OTP & Issue Access Token
* **Method & Path**: `POST /api/v1/auth/company/verify`
* **Auth**: None
* **Request Body**:
  ```json
  {
    "email": "alice@company.com",
    "code": "749201"
  }
  ```
* **Success Response (`200 OK`)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "alice@company.com",
      "name": null
    }
  }
  ```
* **Errors**:
  * `401 INVALID_OR_EXPIRED_CODE` — Code wrong, expired (5-min TTL), superseded, or already used.
  * `422 INVALID_REQUEST` — `code` is not a 6-digit numeric string.

---

### 2.3 Get Current User Profile
* **Method & Path**: `GET /api/v1/users/me`
* **Auth**: `Bearer JWT`
* **Success Response (`200 OK`)**:
  ```json
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "alice@company.com",
    "name": null
  }
  ```
* **Errors**:
  * `401 UNAUTHENTICATED` — Missing, malformed, or expired Bearer token, or user record missing.

---

## 3. Vehicle Service (`:8002`)

### 3.1 Register Vehicle
* **Method & Path**: `POST /api/v1/vehicles`
* **Auth**: `Bearer JWT`
* **Request Body**:
  ```json
  {
    "vehicle_number": "ka-01 ab 1234",
    "vehicle_type": "CAR",
    "is_ev": true
  }
  ```
  *(Note: `vehicle_number` is normalized to `"KA01AB1234"`, 4–20 alphanumeric chars; `vehicle_type` is `"CAR"` or `"BIKE"`.)*
* **Success Response (`201 Created`)**:
  ```json
  {
    "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "vehicle_number": "KA01AB1234",
    "vehicle_type": "CAR",
    "is_ev": true,
    "is_active": true
  }
  ```
* **Errors**:
  * `401 UNAUTHENTICATED`
  * `409 VEHICLE_ALREADY_REGISTERED` — User already has an active vehicle with this normalized plate.
  * `422 INVALID_VEHICLE_DATA` — Invalid plate characters/length or unsupported `vehicle_type`.

---

### 3.2 List Active Vehicles
* **Method & Path**: `GET /api/v1/vehicles`
* **Auth**: `Bearer JWT`
* **Success Response (`200 OK`)**:
  ```json
  {
    "vehicles": [
      {
        "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "vehicle_number": "KA01AB1234",
        "vehicle_type": "CAR",
        "is_ev": true,
        "is_active": true
      }
    ]
  }
  ```

---

### 3.3 Get Single Vehicle
* **Method & Path**: `GET /api/v1/vehicles/{vehicle_id}`
* **Auth**: `Bearer JWT`
* **Success Response (`200 OK`)**: Same schema as `3.1 Register Vehicle`.
* **Errors**:
  * `401 UNAUTHENTICATED`
  * `404 VEHICLE_NOT_FOUND` — Vehicle does not exist, belongs to another user, or is deactivated.

---

### 3.4 Update Vehicle
* **Method & Path**: `PUT /api/v1/vehicles/{vehicle_id}`
* **Auth**: `Bearer JWT`
* **Request Body**:
  ```json
  {
    "vehicle_number": "KA01AB9999",
    "vehicle_type": "CAR",
    "is_ev": false
  }
  ```
* **Success Response (`200 OK`)**: Updated vehicle object.
* **Errors**:
  * `401 UNAUTHENTICATED`
  * `404 VEHICLE_NOT_FOUND`
  * `409 VEHICLE_ALREADY_REGISTERED` — Plate collides with another active vehicle owned by the user.
  * `422 INVALID_VEHICLE_DATA`

---

### 3.5 Deactivate (Soft-Delete) Vehicle
* **Method & Path**: `DELETE /api/v1/vehicles/{vehicle_id}`
* **Auth**: `Bearer JWT`
* **Success Response (`200 OK`)**:
  ```json
  {
    "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "is_active": false,
    "message": "Vehicle removed successfully"
  }
  ```
* **Errors**: `401 UNAUTHENTICATED`, `404 VEHICLE_NOT_FOUND`.

---

## 4. Parking Service (`:8003`)

### 4.1 Check Slot Availability & Hourly Rate
* **Method & Path**: `GET /api/v1/parking/availability`
* **Auth**: `Bearer JWT`
* **Query Parameters**:
  | Parameter | Type | Required | Example |
  | :--- | :--- | :---: | :--- |
  | `date` | `YYYY-MM-DD` | Yes | `2026-11-26` |
  | `start_time` | `HH:MM` | Yes | `09:00` |
  | `end_time` | `HH:MM` | Yes | `12:00` |
  | `vehicle_id` | `UUID` | Yes | `9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d` |
  | `requires_charging` | `boolean` | Yes | `true` |
* **Success Response (`200 OK`)**:
  ```json
  {
    "available": true,
    "available_slots": 10,
    "vehicle_type": "CAR",
    "is_ev": true,
    "requires_charging": true,
    "rate_per_hour": "20.00"
  }
  ```
* **Errors**:
  * `401 UNAUTHENTICATED`
  * `404 VEHICLE_NOT_FOUND` — Vehicle missing, inactive, or not owned by caller.
  * `422 BOOKING_WINDOW_VIOLATION` — Not today/tomorrow, or falls on Sunday.
  * `422 INVALID_BOOKING_TIME` — Non-whole hour, outside `07:00–22:00`, `> 12h`, or in the past.
  * `422 CHARGING_NOT_SUPPORTED` — `requires_charging=true` for a non-EV vehicle.
  * `503 VEHICLE_SERVICE_UNAVAILABLE` — Downstream Vehicle Service unreachable.

---

### 4.2 Create Booking (5-Minute Slot Hold)
* **Method & Path**: `POST /api/v1/parking/bookings`
* **Auth**: `Bearer JWT`
* **Request Body**:
  ```json
  {
    "vehicle_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "date": "2026-11-26",
    "start_time": "09:00",
    "end_time": "12:00",
    "requires_charging": true
  }
  ```
* **Success Response (`201 Created`)**:
  ```json
  {
    "booking_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "vehicle_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "vehicle_number_snapshot": "KA01AB1234",
    "vehicle_type_snapshot": "CAR",
    "is_ev_snapshot": true,
    "slot_number": "C51",
    "date": "2026-11-26",
    "start_time": "09:00",
    "end_time": "12:00",
    "requires_charging": true,
    "amount": "60.00",
    "status": "PAYMENT_PENDING",
    "payment_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "hold_expires_at": "2026-11-25T05:40:00Z",
    "cancelled_at": null
  }
  ```
* **Errors**:
  * All validation errors from `4.1`, plus:
  * `409 USER_BOOKING_OVERLAP` — Caller already has an overlapping active booking.
  * `409 NO_PARKING_CAPACITY` — All compatible slots are occupied for the requested window.
  * `503 PAYMENT_SERVICE_UNAVAILABLE` — Downstream Payment Service unreachable.

---

### 4.3 List User Bookings (Paginated)
* **Method & Path**: `GET /api/v1/parking/bookings`
* **Auth**: `Bearer JWT`
* **Query Parameters**: `page` (int, default `1`, min `1`), `page_size` (int, default `20`, `1..100`)
* **Success Response (`200 OK`)**:
  ```json
  {
    "items": [
      {
        "booking_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "vehicle_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "vehicle_number_snapshot": "KA01AB1234",
        "vehicle_type_snapshot": "CAR",
        "is_ev_snapshot": true,
        "slot_number": "C51",
        "date": "2026-11-26",
        "start_time": "09:00",
        "end_time": "12:00",
        "requires_charging": true,
        "amount": "60.00",
        "status": "CONFIRMED",
        "payment_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "hold_expires_at": "2026-11-25T05:40:00Z",
        "cancelled_at": null
      }
    ],
    "page": 1,
    "page_size": 20,
    "total_items": 1
  }
  ```

---

### 4.4 Get Booking Details
* **Method & Path**: `GET /api/v1/parking/bookings/{booking_id}`
* **Auth**: `Bearer JWT`
* **Success Response (`200 OK`)**: Single `BookingResponse` object (lazily refreshes stale `PAYMENT_PENDING` to `EXPIRED`).
* **Errors**: `401 UNAUTHENTICATED`, `404 BOOKING_NOT_FOUND`.

---

### 4.5 Cancel Confirmed Booking
* **Method & Path**: `POST /api/v1/parking/bookings/{booking_id}/cancel`
* **Auth**: `Bearer JWT`
* **Success Response (`200 OK`)**:
  ```json
  {
    "booking_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "CANCELLED",
    "cancelled_at": "2026-11-25T06:00:00Z"
  }
  ```
* **Errors**:
  * `401 UNAUTHENTICATED`
  * `404 BOOKING_NOT_FOUND`
  * `409 BOOKING_NOT_CANCELLABLE` — Booking is not `CONFIRMED` or start time has already begun/passed.

---

### 4.6 Internal: Apply Payment Result Callback
* **Method & Path**: `POST /internal/v1/bookings/{booking_id}/payment-result`
* **Auth**: Header `X-Internal-Service-Token`
* **Request Body**:
  ```json
  {
    "payment_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "status": "SUCCESS",
    "transaction_id": "TXN8F9C2A104B",
    "processed_at": "2026-11-25T05:36:12Z"
  }
  ```
* **Success Response (`200 OK`)**:
  ```json
  {
    "booking_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "CONFIRMED",
    "result": "APPLIED"
  }
  ```
  *(Possible `result` values: `"APPLIED"`, `"ALREADY_APPLIED"`, `"EXPIRED_NO_RESURRECTION"`.)*
* **Errors**:
  * `401 INTERNAL_CALLER_UNAUTHORIZED`
  * `404 BOOKING_NOT_FOUND`
  * `409 PAYMENT_REFERENCE_MISMATCH` — Callback `payment_id` differs from booking's `payment_id`.
  * `409 INVALID_BOOKING_TRANSITION` — Booking is already `CANCELLED`.

---

## 5. Payment Service (`:8004`)

### 5.1 Internal: Create Pending Payment
* **Method & Path**: `POST /internal/v1/payments`
* **Auth**: Header `X-Internal-Service-Token`
* **Request Body**:
  ```json
  {
    "booking_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "amount": 60.00,
    "expires_at": "2026-11-25T05:40:00Z"
  }
  ```
* **Success Response (`201 Created`, or `200 OK` on idempotent retry)**:
  ```json
  {
    "payment_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "booking_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "amount": "60.00",
    "status": "PENDING",
    "expires_at": "2026-11-25T05:40:00Z"
  }
  ```
* **Errors**:
  * `401 INTERNAL_CALLER_UNAUTHORIZED`
  * `409 PAYMENT_REQUEST_CONFLICT` — Existing payment for `booking_id` has a different `user_id` or `amount`.
  * `422 INVALID_PAYMENT_REQUEST`

---

### 5.2 Process Simulated Payment
* **Method & Path**: `POST /api/v1/payments/{payment_id}/process`
* **Auth**: `Bearer JWT`
* **Optional Header (Non-Production Testing Only)**: `X-Test-Payment-Outcome: SUCCESS | FAILED`
* **Request Body**:
  ```json
  {
    "payment_method": "UPI"
  }
  ```
  *(Supported `payment_method` values: `"UPI"`, `"CARD"`, `"WALLET"`.)*
* **Success Response (`200 OK`)**:
  ```json
  {
    "payment_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "booking_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "amount": "60.00",
    "status": "SUCCESS",
    "transaction_id": "TXN8F9C2A104B"
  }
  ```
* **Errors**:
  * `401 UNAUTHENTICATED`
  * `404 PAYMENT_NOT_FOUND` — Payment missing or belongs to another user.
  * `409 PAYMENT_ALREADY_PROCESSED` — Payment status is already `SUCCESS` or `FAILED`.
  * `409 PAYMENT_EXPIRED` — Current UTC time is at or past `expires_at`.
  * `422 INVALID_PAYMENT_REQUEST` — Unsupported `payment_method`.

---

### 5.3 Get Payment Details
* **Method & Path**: `GET /api/v1/payments/{payment_id}`
* **Auth**: `Bearer JWT`
* **Success Response (`200 OK`)**:
  ```json
  {
    "payment_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "booking_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "amount": "60.00",
    "payment_method": "UPI",
    "status": "SUCCESS",
    "transaction_id": "TXN8F9C2A104B",
    "expires_at": "2026-11-25T05:40:00Z",
    "created_at": "2026-11-25T05:35:00Z"
  }
  ```
* **Errors**: `401 UNAUTHENTICATED`, `404 PAYMENT_NOT_FOUND`.
