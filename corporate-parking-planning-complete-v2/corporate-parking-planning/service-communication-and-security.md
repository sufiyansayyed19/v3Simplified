# Service Communication and Security Design

## 1. Overview
The 4 microservices (`user-auth-service`, `vehicle-service`, `parking-service`, `payment-service`) communicate over HTTP using `httpx`. No service accesses another service's PostgreSQL database directly.

---

## 2. User Authentication: Stateless HS256 JWT

- **Signing:** `user-auth-service` (`:8001`) signs access tokens upon OTP verification (`POST /api/v1/auth/company/verify`) using **HS256** and a shared `JWT_SECRET_KEY`:
  ```json
  {
    "sub": "<user-uuid>",
    "iat": 1795350000,
    "exp": 1795353600
  }
  ```
- **Verification:** `user-auth-service`, `vehicle-service`, `parking-service`, and `payment-service` verify the `Authorization: Bearer <token>` header locally using `jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])` and extract `user_id = uuid.UUID(payload["sub"])`.
- **Owner Scoping:** Every vehicle, booking, and payment query filters by `user_id == authenticated_user_id` so a user can never view or modify another user's records (`404` returned if not found or not owned).

---

## 3. Inter-Service HTTP Calls (`httpx`)

| # | Caller | Callee | Endpoint | Auth Header Used | Purpose |
|---:|---|---|---|---|---|
| **1** | `Parking (:8003)` | `Vehicle (:8002)` | `GET /api/v1/vehicles/{vehicle_id}` | Forwarded user `Authorization: Bearer <jwt>` | Verify vehicle ownership, `is_active`, `vehicle_type`, and `is_ev` |
| **2** | `Parking (:8003)` | `Payment (:8004)` | `POST /internal/v1/payments` | `X-Internal-Service-Token: <INTERNAL_SERVICE_TOKEN>` | Create a `PENDING` payment for a new booking |
| **3** | `Payment (:8004)` | `Parking (:8003)` | `POST /internal/v1/bookings/{booking_id}/payment-result` | `X-Internal-Service-Token: <INTERNAL_SERVICE_TOKEN>` | Confirm (`CONFIRMED`) or expire (`EXPIRED`) the booking after payment processing |

---

## 4. Internal Service Authentication (`X-Internal-Service-Token`)

Internal endpoints under `/internal/v1/*` (`POST /internal/v1/payments` on Payment Service and `POST /internal/v1/bookings/{id}/payment-result` on Parking Service) require the `X-Internal-Service-Token` header matching `settings.INTERNAL_SERVICE_TOKEN` (default `"dev-internal-service-token"`). Requests with a missing or invalid token are rejected with `401 INTERNAL_CALLER_UNAUTHORIZED`.
