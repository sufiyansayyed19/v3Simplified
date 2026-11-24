# API Manual Testing Guide (Swagger UI Walkthrough)

Step-by-step guide to demo all **4 Microservices** directly in their interactive **Swagger UI (`/docs`)**.

---

## 0. Start All 4 Services

```powershell
.\scripts\start_all.ps1
```

Open the 4 Swagger tabs in your browser:
1. **User/Auth Service:** `http://127.0.0.1:8001/docs`
2. **Vehicle Service:** `http://127.0.0.1:8002/docs`
3. **Parking Service:** `http://127.0.0.1:8003/docs`
4. **Payment Service:** `http://127.0.0.1:8004/docs`

---

## 1. User/Auth Service (`http://127.0.0.1:8001/docs` — 3 APIs)

### 1.1 `POST /api/v1/auth/company/send-code`
- **Body:**
  ```json
  {
    "email": "employee@company.com"
  }
  ```
- **Next:** Look at the **User/Auth Service (`8001`) terminal** to copy the 6-digit OTP printed as:
  `[DEV EMAIL OTP] To: employee@company.com | Code: 123456 | Expires in 5 min`

### 1.2 `POST /api/v1/auth/company/verify`
- **Body:**
  ```json
  {
    "email": "employee@company.com",
    "code": "123456"
  }
  ```
- **Response (`200 OK`):** Copy the `access_token` value.
- **Authorize Swagger Tabs:** Click the green **Authorize** button at the top-right of `:8001/docs`, `:8002/docs`, `:8003/docs`, and `:8004/docs` and paste your `access_token`.

### 1.3 `GET /api/v1/users/me`
- Returns `{ "id": "...", "email": "employee@company.com", "name": null }`.

---

## 2. Vehicle Service (`http://127.0.0.1:8002/docs` — 5 APIs)

### 2.1 `POST /api/v1/vehicles`
- **Body:**
  ```json
  {
    "vehicle_number": "mh 12-ab 1234",
    "vehicle_type": "CAR",
    "is_ev": true
  }
  ```
- **Response (`201 Created`):** Plate is normalized to `"MH12AB1234"`. Copy the returned `id` (`<VEHICLE_ID>`).

### 2.2 `GET /api/v1/vehicles` & `GET /api/v1/vehicles/{vehicle_id}`
- Lists or fetches your active vehicles.

### 2.3 `PUT /api/v1/vehicles/{vehicle_id}` & `DELETE /api/v1/vehicles/{vehicle_id}`
- Updates or soft-deactivates (`is_active = false`) a vehicle.

---

## 3. Parking Service (`http://127.0.0.1:8003/docs` — 5 Public + 1 Internal API)

### 3.1 `GET /api/v1/parking/availability`
- **Query Params:**
  - `date`: Tomorrow's date in `YYYY-MM-DD` (not Sunday)
  - `start_time`: `10:00`
  - `end_time`: `12:00`
  - `vehicle_id`: `<VEHICLE_ID>`
  - `requires_charging`: `true`
- **Response (`200 OK`):** Shows `available: true`, `available_slots: 10`, `rate_per_hour: 20.00`.

### 3.2 `POST /api/v1/parking/bookings`
- **Body:**
  ```json
  {
    "vehicle_id": "<VEHICLE_ID>",
    "date": "2026-11-25",
    "start_time": "10:00",
    "end_time": "12:00",
    "requires_charging": true
  }
  ```
- **Response (`201 Created`):** Allocates slot `C51`, sets status to `PAYMENT_PENDING` (5-min hold), calculates `amount: 40.00`, and returns `booking_id` and `payment_id`. Copy both!

---

## 4. Payment Service (`http://127.0.0.1:8004/docs` — 2 Public + 1 Internal API)

### 4.1 `POST /api/v1/payments/{payment_id}/process`
- **Path param:** `payment_id` from step 3.2.
- **Body:**
  ```json
  {
    "payment_method": "UPI"
  }
  ```
- **Response (`200 OK`):** Marks payment `SUCCESS` with `transaction_id: "TXN..."` and automatically notifies Parking Service to confirm the booking!

### 4.2 Verify Booking Confirmation & Cancellation (Back on `:8003/docs`)
1. Call `GET /api/v1/parking/bookings/{booking_id}` → `status` is now **`CONFIRMED`**.
2. Call `POST /api/v1/parking/bookings/{booking_id}/cancel` → `status` transitions to **`CANCELLED`**.
