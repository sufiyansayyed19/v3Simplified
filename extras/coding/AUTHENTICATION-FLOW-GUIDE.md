# Authentication Architecture & Pipeline Flow Guide

> **System**: Corporate Parking Simplified Microservices Platform  
> **Protocol**: Corporate Email OTP + Stateless HS256 Bearer JWT + Inter-Service Shared Secrets  
> **Scope**: `user-auth-service`, `vehicle-service`, `parking-service`, `payment-service`

---

## 1. Executive Architecture Overview

In this microservice architecture, authentication and authorization are built around three core principles:
1. **Passwordless Corporate Email OTP**: Users never manage or leak passwords. Login requires verifying a 6-digit one-time passcode delivered strictly to an authorized corporate email domain (`@company.com`).
2. **Stateless HS256 JWT (Zero-Database-Lookup Verification)**: Once the User/Auth Service mints a JWT, downstream microservices (`vehicle-service`, `parking-service`, `payment-service`) verify signatures and extract the caller's `user_id` **locally** using a shared secret (`JWT_SECRET_KEY`). Downstream services do **not** query `user_db` or make HTTP calls back to `user-auth-service` for token verification.
3. **Machine-to-Machine (M2M) Internal Authentication**: Internal administrative and callback endpoints (`/internal/v1/*`) are isolated from public users and authenticated using a dedicated HTTP header: `X-Internal-Service-Token`.

```mermaid
flowchart TD
    User([Corporate User])
    AuthSvc["User/Auth Service (:8001)\nuser_db (PostgreSQL)"]
    VehicleSvc["Vehicle Service (:8002)\nvehicle_db (PostgreSQL)"]
    ParkingSvc["Parking Service (:8003)\nparking_db (PostgreSQL)"]
    PaymentSvc["Payment Service (:8004)\npayment_db (PostgreSQL)"]

    User -->|1. Request OTP / Verify OTP| AuthSvc
    AuthSvc -- "2. Returns HS256 JWT (sub=user_id)" --> User
    User -->|"3. Bearer JWT (local decode)"| VehicleSvc
    User -->|"4. Bearer JWT (local decode)"| ParkingSvc
    ParkingSvc -->|"5. Propagate Bearer JWT"| VehicleSvc
    ParkingSvc -->|"6. M2M Internal Token"| PaymentSvc
    PaymentSvc -->|"7. M2M Callback Token"| ParkingSvc
```

---

## 2. Authentication Pipeline Map: Files & Functions

| Pipeline Stage | Service & File Path | Functions / Classes | Responsibility |
| :--- | :--- | :--- | :--- |
| **Domain & Email Validation** | [security.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/core/security.py) | `normalize_email()`, `is_allowed_corporate_email()` | Trims/lowercases email; enforces `@company.com` whitelist domain. |
| **CSPRNG OTP Generation** | [security.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/core/security.py) | `generate_otp_code()` | Cryptographically secure 6-digit code generation using `secrets.randbelow(1_000_000)`. |
| **OTP Dispatch & Persistence** | [auth.py (API)](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/api/v1/auth.py)<br>[email_sender.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/services/email_sender.py) | `send_company_code()`<br>`ConsoleEmailSender.send_otp()` | Invalidates previous unconsumed codes, persists new `VerificationCode` (expires in 5 min), dispatches OTP. |
| **OTP Verification & User Upsert** | [auth.py (API)](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/api/v1/auth.py) | `verify_company_code()` | Verifies latest unconsumed OTP against expiry; sets `consumed_at = now`; auto-provisions `User` record if new. |
| **JWT Token Minting** | [security.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/core/security.py) | `create_access_token()` | Packages claims (`sub`, `iat`, `exp`), signs with HS256 and `JWT_SECRET_KEY`. |
| **Auth Service Profile Check** | [auth.py (API)](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/api/v1/auth.py)<br>[security.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/core/security.py) | `get_me()`<br>`get_current_user()` | Decodes Bearer token and fetches current user entity from `user_db`. |
| **Vehicle Service Local Auth** | [security.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/vehicle-service/app/core/security.py) | `decode_access_token()`<br>`get_current_user_id()` | Extracts user UUID from Bearer token without DB calls; enforces tenant isolation on vehicles. |
| **Parking Service Local Auth** | [security.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/core/security.py) | `get_auth_context()`<br>`AuthContext` | Extracts user UUID and retains raw Bearer token for downstream forwarding to Vehicle Service. |
| **Payment Service Local Auth** | [security.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/payment-service/app/core/security.py) | `get_current_user_id()` | Authenticates user paying or checking payment status for payment ownership verification. |
| **M2M Inter-Service Security** | [clients.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/services/clients.py)<br>[internal.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/api/internal.py)<br>[parking_callback.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/payment-service/app/services/parking_callback.py) | `_require_internal_token()`<br>`require_parking_service_token()` | Validates `X-Internal-Service-Token` header on `/internal/v1/*` endpoints. |

---

## 3. End-to-End Flow Walkthrough

### Phase 1: Requesting the Corporate OTP

```mermaid
sequenceDiagram
    autonumber
    actor Employee as Corporate User
    participant AuthAPI as user-auth-service (/api/v1/auth)
    participant Sec as app/core/security.py
    participant DB as user_db (PostgreSQL)
    participant Mailer as ConsoleEmailSender

    Employee->>AuthAPI: POST /api/v1/auth/company/send-code {"email": "user@company.com"}
    AuthAPI->>Sec: normalize_email("user@company.com")
    AuthAPI->>Sec: is_allowed_corporate_email("user@company.com")
    alt Not @company.com
        Sec-->>AuthAPI: False
        AuthAPI-->>Employee: 403 Forbidden (CORPORATE_EMAIL_REQUIRED)
    end
    AuthAPI->>DB: UPDATE verification_codes SET consumed_at = NOW() WHERE email = email AND consumed_at IS NULL
    AuthAPI->>Sec: generate_otp_code() -> "749201"
    AuthAPI->>DB: INSERT INTO verification_codes (id, email, code, expires_at) VALUES (...)
    AuthAPI->>Mailer: send_otp(email, code="749201", expires_minutes=5)
    Mailer-->>AuthAPI: Logged / Dispatched
    AuthAPI-->>Employee: 200 OK {"message": "Verification code sent successfully"}
```

#### Detailed Code Mechanics:
1. **Email Normalization & Whitelisting**:
   - `normalize_email()` strips whitespace and lowercases string.
   - `is_allowed_corporate_email()` verifies `email.rsplit("@", 1)[1] == settings.COMPANY_EMAIL_DOMAIN` (`company.com`). If not, it raises `AppError(403, "CORPORATE_EMAIL_REQUIRED", "Only corporate email addresses are allowed.")`.
2. **Invalidating Stale Codes**:
   - To prevent multiple active codes for the same user, any existing code where `consumed_at IS NULL` has `consumed_at` set to the current UTC timestamp.
3. **CSPRNG Code Generation**:
   - `generate_otp_code()` calls Python's cryptographically secure `secrets.randbelow(1_000_000)` and formats it as a zero-padded 6-digit string (`f"{...:06d}"`).
4. **Database Record**:
   - Saved in table `verification_codes` with `expires_at = now + 5 minutes`.
5. **Console Email Dispatch**:
   - In development/testing, `ConsoleEmailSender.send_otp()` prints the code directly to standard out (`stdout`), making testing instantaneous without relying on external third-party email gateways.

---

### Phase 2: Verifying OTP & Minting JWT

```mermaid
sequenceDiagram
    autonumber
    actor Employee as Corporate User
    participant AuthAPI as user-auth-service (/api/v1/auth)
    participant DB as user_db (PostgreSQL)
    participant Sec as app/core/security.py

    Employee->>AuthAPI: POST /api/v1/auth/company/verify {"email": "user@company.com", "code": "749201"}
    AuthAPI->>DB: SELECT * FROM verification_codes WHERE email = email AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1
    alt Code missing / Expired / Mismatch
        AuthAPI-->>Employee: 401 Unauthorized (INVALID_OR_EXPIRED_CODE)
    end
    AuthAPI->>DB: UPDATE verification_codes SET consumed_at = NOW() WHERE id = code.id
    AuthAPI->>DB: SELECT * FROM users WHERE email = email
    opt User does not exist
        AuthAPI->>DB: INSERT INTO users (id, email, name, created_at, updated_at) VALUES (...)
    end
    AuthAPI->>Sec: create_access_token(user.id)
    Sec-->>AuthAPI: token (HS256 string), expires_in (3600s / 1h)
    AuthAPI-->>Employee: 200 OK {access_token, token_type: "bearer", expires_in: 3600, user: {...}}
```

#### Detailed Code Mechanics:
1. **Verification Queries & Replay Protection**:
   - `verify_company_code()` fetches the latest unconsumed code for the email.
   - It checks:
     - Is there an unconsumed record?
     - Has `expires_at` passed? (`_as_utc(verification.expires_at) <= now`)
     - Does the OTP string match? (`verification.code != payload.code`)
   - If any check fails, it immediately returns `401 INVALID_OR_EXPIRED_CODE`.
   - Once verified, `verification.consumed_at = now` is committed immediately, making OTP reuse impossible.
2. **Automatic Provisioning (JIT User Provisioning)**:
   - If no record exists in `users` table for this email, a new `User(id=uuid.uuid4(), email=email, name=None)` is created.
3. **Token Creation (`create_access_token`)**:
   - Payload claims:
     - `sub`: `str(user.id)` (standard JWT Subject claim holding user UUID)
     - `iat`: issued-at epoch timestamp in UTC
     - `exp`: expiration timestamp (`iat + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60`, default 240 mins)
   - Signed using `jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")`.

---

### Phase 3: Token Verification in Downstream Services (Zero DB Lookups)

When the user calls any downstream API (e.g. `POST /api/v1/vehicles` or `POST /api/v1/parking/holds`), the token is validated locally without contacting `user-auth-service`.

```mermaid
sequenceDiagram
    autonumber
    actor Employee as Corporate User
    participant VehAPI as vehicle-service (:8002)
    participant VehSec as vehicle-service app/core/security.py
    participant VehDB as vehicle_db (PostgreSQL)

    Employee->>VehAPI: GET /api/v1/vehicles [Header: Authorization: Bearer <jwt>]
    VehAPI->>VehSec: get_current_user_id(credentials)
    VehSec->>VehSec: decode_access_token(token)
    Note over VehSec: jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
    alt Signature invalid or expired
        VehSec-->>VehAPI: raises AppError(401, UNAUTHENTICATED)
        VehAPI-->>Employee: 401 Unauthorized
    end
    VehSec-->>VehAPI: returns user_id (UUID)
    VehAPI->>VehDB: SELECT * FROM vehicles WHERE user_id = :user_id AND is_active = TRUE
    VehDB-->>VehAPI: List of user's vehicles
    VehAPI-->>Employee: 200 OK [vehicles]
```

#### Why This Is an Enterprise Best Practice:
1. **High Performance**: No network hop from `vehicle-service` to `user-auth-service` on every request.
2. **Resilience**: Even if `user-auth-service` experiences downtime or restarts, existing authenticated users can continue registering vehicles, booking slots, and making payments until token expiry.
3. **Tenant Isolation**: By extracting `user_id` strictly from the signed cryptographic token, users can only access or modify records where `user_id == current_user_id`.

---

### Phase 4: Token Propagation in Distributed Operations

When booking a parking slot, `parking-service` needs to verify vehicle ownership with `vehicle-service`.

```mermaid
sequenceDiagram
    autonumber
    actor Employee as Corporate User
    participant ParkAPI as parking-service (:8003)
    participant ParkSec as parking-service app/core/security.py
    participant VehClient as parking-service VehicleServiceClient
    participant VehAPI as vehicle-service (:8002)

    Employee->>ParkAPI: POST /api/v1/parking/holds {"vehicle_id": "...", ...}<br>Header: Authorization: Bearer <jwt>
    ParkAPI->>ParkSec: get_auth_context()
    ParkSec-->>ParkAPI: AuthContext(user_id=UUID, raw_token="<jwt>")
    
    ParkAPI->>VehClient: get_owned_vehicle(vehicle_id, bearer_token=raw_token)
    VehClient->>VehAPI: GET /api/v1/vehicles/{vehicle_id}<br>Header: Authorization: Bearer <jwt>
    
    Note over VehAPI: vehicle-service validates JWT locally.<br>Verifies vehicle belongs to this user.
    VehAPI-->>VehClient: 200 OK {"id": "...", "vehicle_number": "KA-01-AB-1234", "is_active": true}
    VehClient-->>ParkAPI: VehicleInfo(...)
    Note over ParkAPI: Proceeds with slot allocation and snapshot
```

#### Detailed Code Mechanics:
- In `services/parking-service/app/core/security.py`, `get_auth_context()` extracts both:
  - `user_id`: decoded `uuid.UUID`
  - `raw_token`: the original string from `credentials.credentials`
- `VehicleServiceClient` passes `headers={"Authorization": f"Bearer {bearer_token}"}`.
- If an attacker attempts to hold a slot using another employee's vehicle ID, `vehicle-service` rejects the call with `404 VEHICLE_NOT_FOUND` because the vehicle does not belong to the token's `user_id`.

---

### Phase 5: Machine-to-Machine (M2M) Internal Authentication

Internal inter-service operations do not represent an end-user action; they represent asynchronous background orchestration between services.

```mermaid
sequenceDiagram
    autonumber
    participant ParkSvc as parking-service (:8003)
    participant PayClient as parking-service PaymentServiceClient
    participant PayAPI as payment-service (:8004)
    participant PayCB as payment-service ParkingCallbackClient
    participant ParkInternal as parking-service (/internal/v1/*)

    Note over ParkSvc: Hold Created -> Trigger Payment Record Creation
    ParkSvc->>PayClient: create_payment(booking_id, user_id, amount, expires_at)
    PayClient->>PayAPI: POST /internal/v1/payments<br>Header: X-Internal-Service-Token: <token>
    Note over PayAPI: require_parking_service_token checks header
    PayAPI-->>PayClient: 201 Created {"payment_id": "..."}

    Note over PayAPI: User Pays via UPI/CARD -> Payment Succeeded
    PayAPI->>PayCB: deliver_payment_result(...)
    PayCB->>ParkInternal: POST /internal/v1/bookings/{id}/payment-result<br>Header: X-Internal-Service-Token: <token>
    Note over ParkInternal: _require_internal_token checks header
    ParkInternal-->>PayCB: 200 OK {"status": "CONFIRMED", "result": "APPLIED"}
```

#### Detailed Code Mechanics:
- Protected Endpoints:
  - `POST /internal/v1/payments` on Payment Service
  - `POST /internal/v1/bookings/{booking_id}/payment-result` on Parking Service
- Security Check:
  ```python
  def _require_internal_token(
      token: str | None = Header(default=None, alias="X-Internal-Service-Token"),
  ) -> None:
      if not token or token != settings.INTERNAL_SERVICE_TOKEN:
          raise AppError(401, "INTERNAL_CALLER_UNAUTHORIZED", "Invalid internal service token.")
  ```
- Any request without this secret header is immediately rejected with HTTP `401 INTERNAL_CALLER_UNAUTHORIZED`.

---

## 4. Security Controls & Error Reference

| Scenario | HTTP Status | Error Code | Description / Remedy |
| :--- | :---: | :--- | :--- |
| Non-corporate email submitted | `403` | `CORPORATE_EMAIL_REQUIRED` | Only addresses ending in `@company.com` are accepted. |
| Code incorrect or expired | `401` | `INVALID_OR_EXPIRED_CODE` | Code does not match database record or 5-minute validity window elapsed. |
| Reused OTP code | `401` | `INVALID_OR_EXPIRED_CODE` | Upon first successful verification, `consumed_at` is set, blocking replay attacks. |
| Missing `Authorization` header | `401` | `UNAUTHENTICATED` | `Authorization: Bearer <token>` was not passed. |
| Malformed or expired JWT | `401` | `UNAUTHENTICATED` | Token signature failed validation or token timestamp expired. |
| Vehicle does not belong to caller | `404` | `VEHICLE_NOT_FOUND` | `vehicle-service` restricts queries to caller's `user_id`. |
| Missing or wrong internal token | `401` | `INTERNAL_CALLER_UNAUTHORIZED` | Endpoint `/internal/v1/*` called without matching `X-Internal-Service-Token`. |

---

## 5. Configuration & Environment Variables

All microservices share standardized configuration keys for authentication across their `.env` / `settings` objects:

```ini
# User & Auth Service
COMPANY_EMAIL_DOMAIN=company.com
OTP_EXPIRE_MINUTES=5
ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_SECRET_KEY=super-secret-jwt-key-for-corporate-parking
JWT_ALGORITHM=HS256

# Vehicle Service, Parking Service, Payment Service
JWT_SECRET_KEY=super-secret-jwt-key-for-corporate-parking
JWT_ALGORITHM=HS256
INTERNAL_SERVICE_TOKEN=dev-internal-service-token
```

---

## 6. Testing & Verifying the Pipeline

To execute the automated authentication test suite:
```powershell
.\.venv\Scripts\pytest.exe services\user-auth-service\tests\test_auth.py -v
```

### What `test_auth.py` Verifies:
1. **`test_health`**: Verifies `/health` returns `200 OK` with `"service": "user-auth-service"`.
2. **`test_reject_non_corporate_email`**: Asserts that `outsider@gmail.com` is rejected with `403 CORPORATE_EMAIL_REQUIRED`.
3. **`test_company_otp_login_and_me_flow`**: Asserts OTP generation and email normalization (`Alice@Company.com` -> `alice@company.com`), wrong OTP rejection (`401 INVALID_OR_EXPIRED_CODE`), valid OTP verification, HS256 JWT token generation, replay protection (`401` on second use of the same OTP), and `/api/v1/users/me` resolution with `Authorization: Bearer <token>`.

To run end-to-end multi-service authentication and authorization:
```powershell
.\.venv\Scripts\pytest.exe tests\test_e2e_journey.py -v
```
This verifies OTP generation, token minting, token usage in vehicle registration, slot holding with token propagation, and inter-service payment confirmation.
