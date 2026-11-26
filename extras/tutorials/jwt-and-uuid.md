# JWT & UUID Deep-Dive Tutorial — Built From `ParkingSimplified`

> **How to use this tutorial:** Every UUID format, JWT claim, error catch, and helper function here comes directly from `ParkingSimplified`. New security and cryptographic terms are explained briefly in plain English the first time they appear.

---

## Course Outline (All Root Topics & Subtopics)

1. **Topic 1: UUID Fundamentals (`uuid` Module)**
   - 1.1 What is a UUID (v4) & Why Not Auto-Increment Integers (`1, 2, 3`)?
   - 1.2 Anatomy of a UUID (`uuid.uuid4()`, `.hex`, `str(...)`)
   - 1.3 Converting Strings $\leftrightarrow$ `uuid.UUID` (And Why JSON/JWT Needs `str(...)`)
2. **Topic 2: How `ParkingSimplified` Uses UUIDs Everywhere**
   - 2.1 Database Primary Keys & Alembic (`UUID(as_uuid=True)`, `default=uuid.uuid4`)
   - 2.2 FastAPI Path/Query Validation & Pydantic Serialization
   - 2.3 Short Unique Transaction IDs (`uuid.uuid4().hex[:10].upper()`)
   - 2.4 Correlation Request IDs (`errors.py`) & Isolated Test Fixtures
3. **Topic 3: JWT Fundamentals (`PyJWT` & Stateless Authentication)**
   - 3.1 What is a JWT (`Header.Payload.Signature`)?
   - 3.2 Signed vs. Encrypted (Critical Security Rule!)
   - 3.3 Registered Claims We Use (`sub`, `iat`, `exp`)
   - 3.4 Stateless HS256 JWT (What We Used) vs. Session Cookies & RS256 (Alternatives)
4. **Topic 4: Minting & Decoding JWTs in Python (`security.py`)**
   - 4.1 Minting an Access Token (`create_access_token` in `user-auth-service`)
   - 4.2 Verifying & Decoding Locally (`decode_access_token` Across All 4 Services)
   - 4.3 Why Catch `(jwt.PyJWTError, ValueError, KeyError)` & Specify `algorithms=["HS256"]`?
5. **Topic 5: Integrating JWTs with FastAPI & Inter-Service Calls**
   - 5.1 Extracting `Authorization: Bearer <token>` (`HTTPBearer(auto_error=False)`)
   - 5.2 `user-auth-service` (`get_current_user` DB Check) vs. Downstream Services (`get_current_user_id` Zero-DB Check)
   - 5.3 Propagating User Identity Between Services (`AuthContext.raw_token`)
   - 5.4 User JWT vs. `X-Internal-Service-Token` (M2M Calls)
   - 5.5 Minting Instant Test Tokens (`_make_jwt`) in Unit & Concurrency Tests

---

## Topic 1: UUID Fundamentals (`uuid` Module)

**Subtopics in this section:**
- 1.1 What is a UUID (v4) & Why Not Auto-Increment Integers (`1, 2, 3`)?
- 1.2 Anatomy of a UUID (`uuid.uuid4()`, `.hex`, `str(...)`)
- 1.3 Converting Strings $\leftrightarrow$ `uuid.UUID` (And Why JSON/JWT Needs `str(...)`)

### 1.1 What is a UUID (v4) & Why Not Auto-Increment Integers (`1, 2, 3`)?
* **UUID (Universally Unique Identifier)**: A standardized 128-bit identifier formatted as 32 hexadecimal characters grouped by hyphens (36 characters total):
  `550e8400-e29b-41d4-a716-446655440000`
* **UUID v4 (`uuid.uuid4()`)**: Generated using cryptographically strong random bits. The probability of two `uuid4()` calls colliding is astronomically near zero ($1 \text{ in } 2^{122}$).

**Why `ParkingSimplified` uses UUIDs instead of integer IDs (`1, 2, 3...`):**
1. **Prevents IDOR Enumeration Attacks**: With integers, if your booking is `/bookings/105`, an attacker knows `/bookings/104` exists and tries scraping `1..1000`. With UUIDs, IDs are unguessable.
2. **Safe Across 4 Separate Databases**: Each microservice generates its own `User.id`, `Vehicle.id`, `Booking.id`, and `Payment.id` independently in Python without needing a shared central database sequence.
3. **Offline/Client ID Knowledge**: SQLAlchemy knows `booking.id` immediately or on creation without coordinate locks across services.

### 1.2 Anatomy of a UUID (`uuid.uuid4()`, `.hex`, `str(...)`)
```python
import uuid

uid = uuid.uuid4()
print(uid)          # UUID('9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d')  -> Python UUID object
print(str(uid))     # "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"         -> 36-char hyphenated string
print(uid.hex)      # "9b1deb4d3b7d4bad9bdd2b0d7b3dcb6d"             -> 32-char string (no hyphens)
```

### 1.3 Converting Strings $\leftrightarrow$ `uuid.UUID` (And Why JSON/JWT Needs `str(...)`)
* **Common Python bug (`TypeError: Object of type UUID is not JSON serializable`)**:
  Python's built-in `json.dumps()` (and `jwt.encode()`, which calls `json.dumps()` internally) does **not** automatically convert `uuid.UUID` objects!
  * Look at `services/user-auth-service/app/core/security.py`:
    ```python
    payload = {
        "sub": str(user_id),   # MUST convert uuid.UUID -> str before jwt.encode()!
        ...
    }
    ```
  * Look at `services/parking-service/app/services/clients.py`:
    ```python
    payload = {
        "booking_id": str(booking_id),
        "user_id": str(user_id),
        ...
    }
    ```
* **Converting back from JSON/JWT string $\rightarrow$ Python `uuid.UUID`**:
  ```python
  user_id = uuid.UUID(payload["sub"])
  payment_id = uuid.UUID(resp.json()["payment_id"])
  ```
  If the string is not a valid 32-hex UUID, `uuid.UUID(...)` raises `ValueError`.

---

## Topic 2: How `ParkingSimplified` Uses UUIDs Everywhere

**Subtopics in this section:**
- 2.1 Database Primary Keys & Alembic (`UUID(as_uuid=True)`, `default=uuid.uuid4`)
- 2.2 FastAPI Path/Query Validation & Pydantic Serialization
- 2.3 Short Unique Transaction IDs (`uuid.uuid4().hex[:10].upper()`)
- 2.4 Correlation Request IDs (`errors.py`) & Isolated Test Fixtures

### 2.1 Database Primary Keys & Alembic (`UUID(as_uuid=True)`, `default=uuid.uuid4`)
Across all 6 models (`User`, `VerificationCode`, `Vehicle`, `ParkingSlot`, `Booking`, `Payment`), primary keys and foreign/logical IDs look like this:

```python
# From services/parking-service/app/models/parking.py
from sqlalchemy.dialects.postgresql import UUID

id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, unique=True)
```
* **`UUID(as_uuid=True)`**: Tells PostgreSQL to store a compact 16-byte binary `UUID` column (much faster/smaller than storing a 36-byte `VARCHAR`), while automatically returning real Python `uuid.UUID` objects instead of plain strings!
* **`default=uuid.uuid4` (NO `()`!)**: Passes the function reference so SQLAlchemy generates a fresh UUID on every `INSERT`. *(Writing `uuid.uuid4()` with parentheses would give every row the same UUID!)*
* **In Alembic (`0001_create_parking_tables.py`)**: Uses `postgresql.UUID(as_uuid=True)` identically.

### 2.2 FastAPI Path/Query Validation & Pydantic Serialization
Unlike `json.dumps()`, **FastAPI and Pydantic v2 natively understand `uuid.UUID`**:
* **Path parameter (`vehicles.py`)**: `def get_vehicle(vehicle_id: uuid.UUID, ...)` automatically parses `/vehicles/9b1deb4d-...` into `uuid.UUID`, and automatically rejects `/vehicles/abc` with HTTP `422`!
* **Query parameter (`parking.py`)**: `vehicle_id: uuid.UUID = Query(...)` validates `?vehicle_id=...` cleanly.
* **Response serialization (`schemas/*.py`)**: Declaring `id: uuid.UUID` in `VehicleResponse` or `BookingResponse` tells Pydantic to serialize the Python `uuid.UUID` cleanly into a JSON string in the HTTP response.

### 2.3 Short Unique Transaction IDs (`uuid.uuid4().hex[:10].upper()`)
Look at `services/payment-service/app/api/v1/payments.py`:
```python
txn_id = f"TXN{uuid.uuid4().hex[:10].upper()}" if outcome == "SUCCESS" else None
```
* `.hex` strips all hyphens (`"9b1deb4d3b7d..."`), `[:10]` takes the first 10 characters, and `.upper()` turns it into a realistic human-readable payment receipt reference like **`TXN9B1DEB4D3B`** (stored in `payments.transaction_id` with `unique=True`).

### 2.4 Correlation Request IDs (`errors.py`) & Isolated Test Fixtures
* **Error tracing (`app/core/errors.py`)**: Every error response attaches `"request_id": getattr(request.state, "request_id", str(uuid.uuid4()))` so support/logs can pinpoint the exact failed request.
* **Test isolation (`tests/test_pg_concurrency.py`)**: Every test run generates fresh `user_ids = [uuid.uuid4() for _ in range(10)]` so concurrent test runs never collide with existing rows in PostgreSQL, and can be deleted cleanly by `user_id` afterward.

---

## Topic 3: JWT Fundamentals (`PyJWT` & Stateless Authentication)

**Subtopics in this section:**
- 3.1 What is a JWT (`Header.Payload.Signature`)?
- 3.2 Signed vs. Encrypted (Critical Security Rule!)
- 3.3 Registered Claims We Use (`sub`, `iat`, `exp`)
- 3.4 Stateless HS256 JWT (What We Used) vs. Session Cookies & RS256 (Alternatives)

### 3.1 What is a JWT (`Header.Payload.Signature`)?
* **JWT (JSON Web Token)**: A compact, URL-safe string with **three Base64Url-encoded parts separated by dots (`.`)**:

```text
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 . eyJzdWIiOiI1NTBlODQwMC0uLi4iLCJpYXQiOjE3OTAwMDAwMDAsImV4cCI6MTc5MDAwMzYwMH0 . SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
└────────────── HEADER ──────────────┘   └─────────────────────────────── PAYLOAD ─────────────────────────────┘   └──────────────── SIGNATURE ───────────────┘
```

1. **Header**: Declares the token type and signing algorithm:
   `{"alg": "HS256", "typ": "JWT"}`
2. **Payload (Claims)**: Key-value JSON data about who the user is and when the token expires:
   `{"sub": "550e8400-e29b-41d4-a716-446655440000", "iat": 1790000000, "exp": 1790003600}`
3. **Signature**: Computed using **HMAC-SHA256 (`HS256`)** over `base64(header) + "." + base64(payload)` using our secret key `JWT_SECRET_KEY`:
   $$\text{Signature} = \text{HMAC-SHA256}(\text{Header.Payload},\ \text{JWT\_SECRET\_KEY})$$
   * If an attacker edits **even 1 character** in the Payload (e.g., changing `sub` to another employee's UUID or extending `exp`), the computed signature won't match and `jwt.decode()` rejects it immediately!

### 3.2 Signed vs. Encrypted (Critical Security Rule!)
* **Base64Url encoding is NOT encryption!** Anyone holding a JWT can paste it into `jwt.io` or decode the middle segment in Python to read `sub`, `iat`, and `exp`.
* **What JWT gives you is integrity/authenticity (tamper-proofing)**: Nobody can *modify* claims or *forge* a valid signature without knowing `JWT_SECRET_KEY`.
* **Rule**: Never put passwords, secrets, or sensitive PII inside a JWT payload. In `ParkingSimplified`, our JWT carries **only** `sub` (the user's UUID), `iat`, and `exp`!

### 3.3 Registered Claims We Use (`sub`, `iat`, `exp`)
* **Claim**: A key inside the JWT payload JSON. The JWT RFC 7519 standard defines 3-letter **registered claim names** that libraries like `PyJWT` recognize automatically:
  * **`sub` (Subject)**: Who this token belongs to (`str(user_id)`).
  * **`iat` (Issued At)**: UTC Unix epoch timestamp (integer seconds since 1970-01-01) when the token was created.
  * **`exp` (Expiration Time)**: UTC Unix epoch timestamp after which `PyJWT` **automatically rejects** the token with `jwt.ExpiredSignatureError`!

### 3.4 Stateless HS256 JWT (What We Used) vs. Session Cookies & RS256 (Alternatives)
Why did `ParkingSimplified` choose **HS256 Stateless Bearer JWT**?

| Approach | How Verification Works | Pros & Cons | When to Use |
| :--- | :--- | :--- | :--- |
| **HS256 Symmetric JWT (What We Used)** | Every service shares `JWT_SECRET_KEY` and verifies tokens locally with `PyJWT`. | Zero DB/HTTP calls to `user-auth-service`; fast; no `.pem` key management for freshers. | Trusted internal microservices owned by one team (`ParkingSimplified`). |
| **RS256 Asymmetric JWT (Alternative)** | Auth service signs with a **private `.pem` key**; other services verify with a **public `.pem` key**. | Downstream services can verify tokens *without* being able to mint new tokens. | Large organizations where untrusted external/partner teams verify your tokens. |
| **Stateful Session Cookie + Redis/DB (Alternative)** | Browser sends an opaque session ID cookie; server looks up session in Redis/DB. | Easy instant logout/revocation, **but** every microservice must query the session store on every call. | Monoliths or strict instant-revocation banking portals. |

---

## Topic 4: Minting & Decoding JWTs in Python (`security.py`)

**Subtopics in this section:**
- 4.1 Minting an Access Token (`create_access_token` in `user-auth-service`)
- 4.2 Verifying & Decoding Locally (`decode_access_token` Across All 4 Services)
- 4.3 Why Catch `(jwt.PyJWTError, ValueError, KeyError)` & Specify `algorithms=["HS256"]`?

### 4.1 Minting an Access Token (`create_access_token` in `user-auth-service`)
Only **`user-auth-service`** mints JWTs (inside `POST /api/v1/auth/company/verify`, after OTP verification succeeds):

```python
# From services/user-auth-service/app/core/security.py
def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60   # 60 * 60 = 3600 seconds
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in
```
* Returning both `(token, expires_in)` lets `verify_company_code()` build `AuthTokenResponse(access_token=..., token_type="bearer", expires_in=3600, user=...)` directly.

### 4.2 Verifying & Decoding Locally (`decode_access_token` Across All 4 Services)
Every microservice (`user-auth-service`, `vehicle-service`, `parking-service`, `payment-service`) has `decode_access_token()` in `app/core/security.py`:

```python
# From services/vehicle-service/app/core/security.py
def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise AppError(401, "UNAUTHENTICATED", "Invalid or expired access token.")
```
When `jwt.decode(...)` runs, `PyJWT` automatically checks:
1. Format has 3 valid Base64Url segments.
2. HMAC-SHA256 signature matches `settings.JWT_SECRET_KEY`.
3. Current UTC time is strictly less than `payload["exp"]` (`ExpiredSignatureError` otherwise).

### 4.3 Why Catch `(jwt.PyJWTError, ValueError, KeyError)` & Specify `algorithms=["HS256"]`?
* **Why `algorithms=[settings.JWT_ALGORITHM]` (a list) is mandatory for security**:
  Classic JWT vulnerability: an attacker sends a forged token with header `{"alg": "none"}` and empty signature. Passing an explicit whitelist `algorithms=["HS256"]` forces `PyJWT` to reject `"none"` or any unexpected algorithm!
* **Why catch ALL THREE exceptions `(jwt.PyJWTError, ValueError, KeyError)`?**
  1. `jwt.PyJWTError`: Covers invalid signature, expired token (`ExpiredSignatureError`), malformed token string (`DecodeError`), or wrong algorithm (`InvalidAlgorithmError`).
  2. `KeyError`: Covers a structurally valid signed token whose payload omitted `"sub"`.
  3. `ValueError`: Covers a signed token where `"sub"` is `"not-a-valid-uuid"`, causing `uuid.UUID(...)` to fail!
  Catching all three cleanly maps every bad-token edge case to `401 UNAUTHENTICATED` without ever crashing with a `500`!

---

## Topic 5: Integrating JWTs with FastAPI & Inter-Service Calls

**Subtopics in this section:**
- 5.1 Extracting `Authorization: Bearer <token>` (`HTTPBearer(auto_error=False)`)
- 5.2 `user-auth-service` (`get_current_user` DB Check) vs. Downstream Services (`get_current_user_id` Zero-DB Check)
- 5.3 Propagating User Identity Between Services (`AuthContext.raw_token`)
- 5.4 User JWT vs. `X-Internal-Service-Token` (M2M Calls)
- 5.5 Minting Instant Test Tokens (`_make_jwt`) in Unit & Concurrency Tests

### 5.1 Extracting `Authorization: Bearer <token>` (`HTTPBearer(auto_error=False)`)
```python
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> uuid.UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "UNAUTHENTICATED", "Missing or invalid authorization header.")

    return decode_access_token(credentials.credentials)
```
* `HTTPBearer(auto_error=False)` reads the `Authorization` header, strips the `"Bearer "` prefix into `credentials.credentials`, and lets our code raise `401 UNAUTHENTICATED` cleanly if the header is absent.

### 5.2 `user-auth-service` (`get_current_user` DB Check) vs. Downstream Services (`get_current_user_id` Zero-DB Check)
* In **`user-auth-service`** (`GET /api/v1/users/me`): `get_current_user()` decodes `user_id` **and runs `db.get(User, user_id)`** because `/users/me` must return the user's `email` and `name` from `user_db`.
* In **`vehicle-service`, `parking-service`, and `payment-service`**: Routes only need the caller's `user_id` to scope queries (`WHERE user_id = :user_id`), so `get_current_user_id()` / `get_auth_context()` performs **zero database queries and zero network calls** to `user-auth-service`!

### 5.3 Propagating User Identity Between Services (`AuthContext.raw_token`)
When a user calls `parking-service` (`POST /api/v1/parking/bookings`), `parking-service` must verify vehicle ownership with `vehicle-service` (`GET /api/v1/vehicles/{vehicle_id}`).
* Instead of trusting an unauthenticated internal query, `get_auth_context()` in `services/parking-service/app/core/security.py` keeps **both** `user_id` and `raw_token`:
  ```python
  @dataclass
  class AuthContext:
      user_id: uuid.UUID
      raw_token: str
  ```
* `VehicleServiceClient` sends `headers={"Authorization": f"Bearer {bearer_token}"}` to `vehicle-service`—so `vehicle-service` independently validates the exact same HS256 JWT and checks `Vehicle.user_id == decoded_user_id`!

### 5.4 User JWT vs. `X-Internal-Service-Token` (M2M Calls)
Why don't `/internal/v1/payments` and `/internal/v1/bookings/{id}/payment-result` use JWT?
* Those calls happen **service-to-service (M2M)** rather than directly from an end user's browser (for instance, `payment-service` pushing a payment result back to `parking-service`).
* Using a separate `X-Internal-Service-Token` header guarantees an employee with a valid user JWT can **never** call internal endpoints to fake a `"SUCCESS"` payment callback!

### 5.5 Minting Instant Test Tokens (`_make_jwt`) in Unit & Concurrency Tests
Because all 4 services share the same HS256 contract, `test_vehicles.py`, `test_parking.py`, `test_payments.py`, and `test_pg_concurrency.py` each use a 6-line `_make_jwt(user_id)` helper to create real valid JWTs for arbitrary `uuid.uuid4()` users in-memory—no running `:8001` auth server needed during isolated service tests!

```python
# From services/vehicle-service/tests/test_vehicles.py
def _make_jwt(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=60)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
```
