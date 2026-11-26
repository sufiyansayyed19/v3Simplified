# API Manual Testing Guide (All 17 APIs + `/health`)

Complete step-by-step handbook to test **every single endpoint** across all **4 Microservices** using **Swagger UI (`/docs`)** or **`curl.exe`**, including exact request bodies, headers, query/path parameters, expected responses, and negative test cases.

---

## 0. Before You Start

1. **One-time `user_db` check** *(only needed if you previously ran old Alembic migrations as `postgres`)*:
   ```powershell
   psql -U postgres -d user_db -c "DROP TABLE IF EXISTS alembic_version, refresh_sessions, auth_identities, verification_codes, users CASCADE;"
   ```
2. **Start all 4 microservices:**
   ```powershell
   .\scripts\start_all.ps1
   ```
   *(All tables are created automatically on startup, and `parking_db` is auto-seeded with 100 slots `C01–C60`, `B01–B40`.)*

3. **Open all 4 Swagger UI tabs:**
   - **User/Auth Service (`8001`):** `http://127.0.0.1:8001/docs`
   - **Vehicle Service (`8002`):** `http://127.0.0.1:8002/docs`
   - **Parking Service (`8003`):** `http://127.0.0.1:8003/docs`
   - **Payment Service (`8004`):** `http://127.0.0.1:8004/docs`

4. **Quick Health Check (all 4 services):**
   - `GET http://127.0.0.1:8001/health` → `{"status": "ok", "service": "user-auth-service"}`
   - `GET http://127.0.0.1:8002/health` → `{"status": "ok", "service": "vehicle-service"}`
   - `GET http://127.0.0.1:8003/health` → `{"status": "ok", "service": "parking-service"}`
   - `GET http://127.0.0.1:8004/health` → `{"status": "ok", "service": "payment-service"}`

### Cheat Sheet: Where Every Value Comes From

| Placeholder | Where You Get It |
|---|---|
| `<OTP_CODE>` | Printed in the **User/Auth Service (`8001`) PowerShell window** as `[DEV EMAIL OTP] To: ... \| Code: 123456` |
| `<ACCESS_TOKEN>` | Returned as `access_token` from `POST /api/v1/auth/company/verify` (valid for 60 min) |
| `<VEHICLE_ID>` | Returned as `id` from `POST /api/v1/vehicles` or `GET /api/v1/vehicles` |
| `<BOOKING_ID>` | Returned as `booking_id` from `POST /api/v1/parking/bookings` |
| `<PAYMENT_ID>` | Returned as `payment_id` from `POST /api/v1/parking/bookings` |
| `<DATE>` | Today or tomorrow in `YYYY-MM-DD` (Monday–Saturday only; **not Sunday**) |
| `<INTERNAL_TOKEN>` | Value of `INTERNAL_SERVICE_TOKEN` in `config.py` / `.env` → `dev-internal-service-token` |

> **How to Authorize in Swagger UI:** Click the green **Authorize 🔒** button at the top-right of `:8001/docs`, `:8002/docs`, `:8003/docs`, and `:8004/docs`, and paste **only** `<ACCESS_TOKEN>` (do **not** type `Bearer ` or quotes).

---

## 1. User/Auth Service (`http://127.0.0.1:8001/docs` — 3 APIs)

### 1.1 `POST /api/v1/auth/company/send-code`
- **Auth:** Public (none required)
- **Request Body:**
  ```json
  {
    "email": "employee@company.com"
  }
  ```
- **Expected Response (`200 OK`):**
  ```json
  {
    "message": "Verification code sent successfully"
  }
  ```
- **Next Step:** Check the **User/Auth (`8001`) terminal** and copy the 6-digit `<OTP_CODE>`.
- **Negative Tests:**
  - Send `{"email": "user@gmail.com"}` → **`403 Forbidden`** (`CORPORATE_EMAIL_REQUIRED`).
  - Send `{"email": "not-an-email"}` → **`422 Unprocessable Entity`** (`INVALID_REQUEST`).

### 1.2 `POST /api/v1/auth/company/verify`
- **Auth:** Public (none required)
- **Request Body:**
  ```json
  {
    "email": "employee@company.com",
    "code": "<OTP_CODE>"
  }
  ```
- **Expected Response (`200 OK`):**
  ```json
  {
    "access_token": "<ACCESS_TOKEN>",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "<USER_UUID>",
      "email": "employee@company.com",
      "name": null
    }
  }
  ```
- **Save & Authorize:** Copy `access_token` and click **Authorize 🔒** on all 4 Swagger tabs (`8001`–`8004`).
- **Negative Tests:**
  - Wrong 6-digit code (e.g. `"000000"`) → **`401 Unauthorized`** (`INVALID_OR_EXPIRED_CODE`).
  - Re-submitting the exact same `<OTP_CODE>` after a successful verify → **`401 Unauthorized`** (OTP is single-use).

### 1.3 `GET /api/v1/users/me`
- **Auth:** Bearer JWT (`Authorization: Bearer <ACCESS_TOKEN>`)
- **Parameters / Body:** None
- **Expected Response (`200 OK`):**
  ```json
  {
    "id": "<USER_UUID>",
    "email": "employee@company.com",
    "name": null
  }
  ```
- **Negative Test:** Call without Authorize / invalid token → **`401 Unauthorized`** (`UNAUTHENTICATED`).

---

## 2. Vehicle Service (`http://127.0.0.1:8002/docs` — 5 APIs)

> All 5 endpoints require **Authorize 🔒** (`Authorization: Bearer <ACCESS_TOKEN>`).
> **Note for sequential testing:** Register your main EV car in step 2.1 (`<VEHICLE_ID>`), test `GET`/`PUT` in steps 2.2–2.4, and test `DELETE` on a *second* test vehicle (or after finishing Section 3 & 4) so `<VEHICLE_ID>` stays active for booking!

### 2.1 `POST /api/v1/vehicles`
- **Request Body:**
  ```json
  {
    "vehicle_number": "mh 12-ab 1234",
    "vehicle_type": "CAR",
    "is_ev": true
  }
  ```
  *(Allowed `vehicle_type`: `"CAR"` or `"BIKE"`. Plate is normalized by stripping spaces/hyphens and uppercasing.)*
- **Expected Response (`201 Created`):**
  ```json
  {
    "id": "<VEHICLE_ID>",
    "vehicle_number": "MH12AB1234",
    "vehicle_type": "CAR",
    "is_ev": true,
    "is_active": true
  }
  ```
- **Save:** Copy `id` as `<VEHICLE_ID>`.
- **Negative Tests:**
  - Submit `"MH12AB1234"` again for the same user → **`409 Conflict`** (`VEHICLE_ALREADY_REGISTERED`).
  - Submit `"vehicle_type": "TRUCK"` → **`422 Unprocessable Entity`** (`INVALID_VEHICLE_DATA`).

### 2.2 `GET /api/v1/vehicles`
- **Parameters / Body:** None
- **Expected Response (`200 OK`):**
  ```json
  {
    "vehicles": [
      {
        "id": "<VEHICLE_ID>",
        "vehicle_number": "MH12AB1234",
        "vehicle_type": "CAR",
        "is_ev": true,
        "is_active": true
      }
    ]
  }
  ```

### 2.3 `GET /api/v1/vehicles/{vehicle_id}`
- **Path Parameter:** `vehicle_id` = `<VEHICLE_ID>`
- **Expected Response (`200 OK`):** Single vehicle JSON object.
- **Negative Test:** Random UUID or another user's vehicle ID → **`404 Not Found`** (`VEHICLE_NOT_FOUND`).

### 2.4 `PUT /api/v1/vehicles/{vehicle_id}`
- **Path Parameter:** `vehicle_id` = `<VEHICLE_ID>`
- **Request Body** *(all 3 fields required; keep `is_ev: true` if using this vehicle for EV charging in Section 3)*:
  ```json
  {
    "vehicle_number": "MH 12-AB 9999",
    "vehicle_type": "CAR",
    "is_ev": true
  }
  ```
- **Expected Response (`200 OK`):** Updated vehicle with `"vehicle_number": "MH12AB9999"`.
- **Negative Test:** Update `vehicle_number` to a plate already used by another active vehicle of yours → **`409 Conflict`** (`VEHICLE_ALREADY_REGISTERED`).

### 2.5 `DELETE /api/v1/vehicles/{vehicle_id}`
- **Path Parameter:** `vehicle_id` = `<TEMP_VEHICLE_ID>` *(create a spare `"KA01CD5678"` `BIKE` to test `DELETE`, or run this at the end after Section 4!)*
- **Parameters / Body:** None (soft-deactivates `is_active = false`).
- **Expected Response (`200 OK`):**
  ```json
  {
    "id": "<TEMP_VEHICLE_ID>",
    "is_active": false,
    "message": "Vehicle removed successfully"
  }
  ```
- **Verify Soft Delete:** Calling `GET /api/v1/vehicles/{id}` afterward returns **`404 VEHICLE_NOT_FOUND`**, and `POST /api/v1/vehicles` lets you re-register the same plate as a new active row!

---

## 3. Parking Service — Public APIs (`http://127.0.0.1:8003/docs` — 5 Public APIs)

> All 5 endpoints require **Authorize 🔒** (`Authorization: Bearer <ACCESS_TOKEN>`).
> **Time Rules Reminder:** Today or tomorrow (Mon–Sat; Sunday closed), whole hours between `07:00` and `22:00`, max `12` hours, `start_time` strictly in the future (`start_dt > now`).

### 3.1 `GET /api/v1/parking/availability`
- **Query Parameters:**
  - `date`: `<DATE>` (e.g. tomorrow `2026-11-25`)
  - `start_time`: `10:00`
  - `end_time`: `12:00`
  - `vehicle_id`: `<VEHICLE_ID>`
  - `requires_charging`: `true`
- **Expected Response (`200 OK`):**
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
- **Negative Tests:**
  - `start_time=10:15` (non-whole hour) → **`422`** (`INVALID_BOOKING_TIME`).
  - `requires_charging=true` with a non-EV vehicle → **`422`** (`CHARGING_NOT_SUPPORTED`).
  - `date` set to a Sunday or 3 days from now → **`422`** (`BOOKING_WINDOW_VIOLATION`).

### 3.2 `POST /api/v1/parking/bookings`
- **Request Body:**
  ```json
  {
    "vehicle_id": "<VEHICLE_ID>",
    "date": "<DATE>",
    "start_time": "10:00",
    "end_time": "12:00",
    "requires_charging": true
  }
  ```
- **Expected Response (`201 Created`):**
  ```json
  {
    "booking_id": "<BOOKING_ID>",
    "vehicle_id": "<VEHICLE_ID>",
    "vehicle_number_snapshot": "MH12AB9999",
    "vehicle_type_snapshot": "CAR",
    "is_ev_snapshot": true,
    "slot_number": "C51",
    "date": "<DATE>",
    "start_time": "10:00",
    "end_time": "12:00",
    "requires_charging": true,
    "amount": "40.00",
    "status": "PAYMENT_PENDING",
    "payment_id": "<PAYMENT_ID>",
    "hold_expires_at": "2026-11-24T...",
    "cancelled_at": null
  }
  ```
- **Save:** Copy `booking_id` (`<BOOKING_ID>`) and `payment_id` (`<PAYMENT_ID>`).
- **Negative Test:** Re-submit the same overlapping time (`11:00`–`13:00`) while the hold is active → **`409 Conflict`** (`USER_BOOKING_OVERLAP`). *(Adjacent `12:00`–`14:00` succeeds!)*

### 3.3 `GET /api/v1/parking/bookings`
- **Query Parameters (optional):** `page=1`, `page_size=20` (max `100`)
- **Expected Response (`200 OK`):**
  ```json
  {
    "items": [ ... ],
    "page": 1,
    "page_size": 20,
    "total_items": 1
  }
  ```
  *(Any `PAYMENT_PENDING` booking older than 5 minutes is lazily flipped to `EXPIRED`.)*

### 3.4 `GET /api/v1/parking/bookings/{booking_id}`
- **Path Parameter:** `booking_id` = `<BOOKING_ID>`
- **Expected Response (`200 OK`):** Full booking object. Check `status` here (`PAYMENT_PENDING` before payment, `CONFIRMED` after Section 4.1, `CANCELLED` after Section 3.5).
- **Negative Test:** Random UUID or another user's `booking_id` → **`404 Not Found`** (`BOOKING_NOT_FOUND`).

### 3.5 `POST /api/v1/parking/bookings/{booking_id}/cancel`
> **Run Section 4.1 (Payment) first** so your booking becomes `CONFIRMED`!
- **Path Parameter:** `booking_id` = `<BOOKING_ID>`
- **Request Body:** None
- **Expected Response (`200 OK`):**
  ```json
  {
    "booking_id": "<BOOKING_ID>",
    "status": "CANCELLED",
    "cancelled_at": "2026-11-24T..."
  }
  ```
- **Negative Tests:**
  - Try cancelling while still `PAYMENT_PENDING` → **`409 Conflict`** (`BOOKING_NOT_CANCELLABLE`).
  - Try cancelling an already-`CANCELLED` booking → **`409 Conflict`** (`BOOKING_NOT_CANCELLABLE`).

---

## 4. Payment Service — Public APIs (`http://127.0.0.1:8004/docs` — 2 Public APIs)

> Both endpoints require **Authorize 🔒** (`Authorization: Bearer <ACCESS_TOKEN>`).

### 4.1 `POST /api/v1/payments/{payment_id}/process`
- **Path Parameter:** `payment_id` = `<PAYMENT_ID>` (from Step 3.2)
- **Optional Header (Dev Testing Only):** `X-Test-Payment-Outcome` (`"SUCCESS"` or `"FAILED"`; omit to use default `"SUCCESS"`)
- **Request Body:**
  ```json
  {
    "payment_method": "UPI"
  }
  ```
  *(Allowed values: `"UPI"`, `"CARD"`, `"WALLET"`.)*
- **Expected Response (`200 OK`):**
  ```json
  {
    "payment_id": "<PAYMENT_ID>",
    "booking_id": "<BOOKING_ID>",
    "amount": "40.00",
    "status": "SUCCESS",
    "transaction_id": "TXN..."
  }
  ```
- **What Happens Automatically:** Payment Service saves `SUCCESS` in `payment_db` and sends `POST /internal/v1/bookings/{booking_id}/payment-result` to Parking Service (`8003`).
- **Next:** Go back to `:8003/docs` and run Step **3.4 (`GET /api/v1/parking/bookings/{booking_id}`)** → confirm `status` is now **`CONFIRMED`**, then run Step **3.5 (`/cancel`)**!
- **Negative Tests:**
  - Call `/process` a second time on the same `<PAYMENT_ID>` → **`409 Conflict`** (`PAYMENT_ALREADY_PROCESSED`).
  - Pass `payment_method: "CRYPTO"` → **`422 Unprocessable Entity`** (`INVALID_PAYMENT_REQUEST`).
  - Pass header `X-Test-Payment-Outcome: FAILED` on a *new* booking's payment → returns `"status": "FAILED", "transaction_id": null` and Parking marks that booking **`EXPIRED`**.

### 4.2 `GET /api/v1/payments/{payment_id}`
- **Path Parameter:** `payment_id` = `<PAYMENT_ID>`
- **Expected Response (`200 OK`):**
  ```json
  {
    "payment_id": "<PAYMENT_ID>",
    "booking_id": "<BOOKING_ID>",
    "amount": "40.00",
    "payment_method": "UPI",
    "status": "SUCCESS",
    "transaction_id": "TXN...",
    "expires_at": "2026-11-24T...",
    "created_at": "2026-11-24T..."
  }
  ```
- **Negative Test:** Random UUID or another user's `payment_id` → **`404 Not Found`** (`PAYMENT_NOT_FOUND`).

---

## 5. Internal Service-to-Service APIs (2 APIs — Protected by `X-Internal-Service-Token`)

These endpoints are called automatically between `Parking (:8003)` and `Payment (:8004)`. To test them directly in Swagger UI or PowerShell, pass the header:
- `X-Internal-Service-Token: dev-internal-service-token`

### 5.1 `POST http://127.0.0.1:8004/internal/v1/payments` *(Payment Service)*
- **Header:** `X-Internal-Service-Token: dev-internal-service-token`
- **Request Body:**
  ```json
  {
    "booking_id": "11111111-1111-4111-8111-111111111111",
    "user_id": "<USER_UUID>",
    "amount": 40.00,
    "expires_at": "2026-11-25T10:05:00+05:30"
  }
  ```
- **Expected Response:** `201 Created` on first call (`200 OK` on identical replay with same `booking_id`, `user_id`, and `amount`; `409 PAYMENT_REQUEST_CONFLICT` if `amount` differs; `401 INTERNAL_CALLER_UNAUTHORIZED` if token is missing/wrong).

### 5.2 `POST http://127.0.0.1:8003/internal/v1/bookings/{booking_id}/payment-result` *(Parking Service)*
- **Header:** `X-Internal-Service-Token: dev-internal-service-token`
- **Path Parameter:** `booking_id` = `<BOOKING_ID>`
- **Request Body:**
  ```json
  {
    "payment_id": "<PAYMENT_ID>",
    "status": "SUCCESS",
    "transaction_id": "TXN1234567890",
    "processed_at": "2026-11-24T10:02:00+05:30"
  }
  ```
- **Expected Response:** `200 OK` (`{"booking_id": "...", "status": "CONFIRMED", "result": "APPLIED"}` or `"ALREADY_APPLIED"`, or `401 INTERNAL_CALLER_UNAUTHORIZED` if token is missing/wrong).
