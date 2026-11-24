# Quality and Testing Plan

## 1. Automated Test Suites (`.\scripts\run_all_tests.ps1`)

The project includes **7 automated `pytest` suites** covering unit, internal callback, real PostgreSQL concurrency, and live 4-service end-to-end verification:

| # | Test Suite | What It Verifies |
|---:|---|---|
| **1** | `services/user-auth-service/tests/test_auth.py` | `/health`, corporate email domain validation (`403` on non-corporate email), OTP send & verify, replay prevention, and HS256 JWT `/users/me` |
| **2** | `services/vehicle-service/tests/test_vehicles.py` | Vehicle CRUD, license plate normalization (`"mh 12-ab 1234"` → `"MH12AB1234"`), duplicate active plate rejection (`409`), soft delete + re-registration, owner isolation (`404`), and invalid vehicle type rejection (`422`) |
| **3** | `services/parking-service/tests/test_parking.py` | Availability check, booking creation with vehicle snapshots and pricing (`₹20/hr` EV charging, `₹10/hr` normal), same-user overlap rejection (`409`), adjacent interval support, slot capacity exhaustion (`409`), non-EV charging rejection (`422`), past-time & Sunday rejection (`422`), cancellation before `start_time`, and lazy 5-min hold expiry |
| **4** | `services/parking-service/tests/test_internal.py` | `X-Internal-Service-Token` authentication (`401` when missing) and `PAYMENT_PENDING` → `CONFIRMED` callback transition |
| **5** | `services/payment-service/tests/test_payments.py` | Internal payment creation (`201`), owner isolation (`404`), simulated `UPI` payment processing (`SUCCESS` + `TXN...`), and callback delivery |
| **6** | `tests/test_pg_concurrency.py` | **Real PostgreSQL concurrency:** 10 threads simultaneously racing for the 5 EV-bike slots (`B36–B40`) → exactly 5 succeed with unique slots and 5 get `409 NO_PARKING_CAPACITY`; 1 user firing 4 simultaneous overlapping requests → exactly 1 succeeds and 3 get `409 USER_BOOKING_OVERLAP` |
| **7** | `tests/test_e2e_journey.py` | **Live 4-service E2E journey:** starts all 4 microservices (`:18001`–`:18004`) against the 4 PostgreSQL databases and executes Vehicle registration → Availability check → Booking creation → UPI Payment processing → Booking confirmation verification → Booking cancellation |

---

## 2. Standard Error Envelope

All 4 microservices return errors in a consistent JSON structure via `app/core/errors.py`:

```json
{
  "error": {
    "code": "NO_PARKING_CAPACITY",
    "message": "No compatible parking slot is available for the requested interval.",
    "request_id": "<uuid>"
  }
}
```
