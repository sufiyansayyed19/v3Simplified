# Topic 2: Service Core, Infrastructure, Security & Logging

This file explains every built-in class, method, and function used in `config.py`, `security.py`, `clients.py`, and route parameters across all 4 microservices.

**Contents:**
1. [`BaseSettings`](#1-basesettings)
2. [`SettingsConfigDict`](#2-settingsconfigdict)
3. [`APIRouter(...)`](#3-apirouter)
4. [`Depends(...)`](#4-depends)
5. [`Query(...)`](#5-query)
6. [`Header(...)`](#6-header)
7. [`Response`](#7-response)
8. [`status`](#8-status)
9. [`HTTPBearer(...)`](#9-httpbearer)
10. [`HTTPAuthorizationCredentials`](#10-httpauthorizationcredentials)
11. [`jwt.encode(...)`](#11-jwtencode)
12. [`jwt.decode(...)`](#12-jwtdecode)
13. [`jwt.PyJWTError`](#13-jwtpyjwterror)
14. [`httpx.Client(...)`](#14-httpxclient)
15. [`httpx.HTTPError`](#15-httpxhttperror)
16. [`logging.basicConfig(...)` & `logging.getLogger(...)`](#16-loggingbasicconfig--logginggetlogger)

---

## 1. `BaseSettings`

* **Import:** `from pydantic_settings import BaseSettings`
* **In Simple Words:** A Pydantic base class that automatically loads configuration values from **OS environment variables** and **`.env` files**, converts them to the declared Python types (`int`, `str`, `bool`), and validates them at startup.

### How It Works
* You subclass `BaseSettings` and declare class attributes with type annotations and default values.
* Priority order (highest wins): **OS Environment Variable** > **`.env` file** > **Default value in class**.
* **Project Example (`services/parking-service/app/core/config.py`):**
  ```python
  class Settings(BaseSettings):
      SERVICE_NAME: str = "parking-service"
      PORT: int = 8003
      DATABASE_URL: str = "postgresql+psycopg://..."
      model_config = SettingsConfigDict(env_file=".env", extra="ignore")
  ```

---

## 2. `SettingsConfigDict`

* **Import:** `from pydantic_settings import SettingsConfigDict`
* **In Simple Words:** Configuration dictionary attached to `model_config` inside a `BaseSettings` class to tell Pydantic *where* `.env` is and *how* to handle extra variables.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `env_file` | `str \| Path` | `None` | Path to the `.env` file to read (e.g. `".env"`). |
| `env_file_encoding` | `str` | `None` | Character encoding of `.env` (usually `"utf-8"`). |
| `extra` | `Literal["ignore", "forbid", "allow"]` | `"forbid"` | What to do when `.env` contains variables not listed on this class. `"ignore"` prevents crashes when 4 services share one `.env`. |
| `case_sensitive` | `bool` | `False` | Whether `PORT` and `port` are treated as different variables. |

* **Project Example (`services/parking-service/app/core/config.py`):**
  ```python
  model_config = SettingsConfigDict(
      env_file=".env",
      env_file_encoding="utf-8",
      extra="ignore",
  )
  ```

---

## 3. `APIRouter(...)`

* **Import:** `from fastapi import APIRouter`
* **In Simple Words:** Groups related API endpoints into a modular unit (like `vehicles.py` or `parking.py`) before plugging them into `app`.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `prefix` | `str` | `""` | URL prefix added to every route on this router (e.g. `"/api/v1/vehicles"`). |
| `tags` | `list[str]` | `None` | Section heading used in Swagger UI (`/docs`). |
| `dependencies` | `Sequence[Depends]` | `None` | Dependencies executed before *every* route in this router (e.g. internal token check). |
| `responses` | `dict` | `None` | Shared OpenAPI error responses documented for all routes in this router. |

* **Project Example (`services/vehicle-service/app/api/v1/vehicles.py`):**
  ```python
  router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])

  @router.get("")
  def list_vehicles(...):
      ...
  ```

---

## 4. `Depends(...)`

* **Import:** `from fastapi import Depends`
* **In Simple Words:** FastAPI's **Dependency Injection** marker. It tells FastAPI: *"Before running this route, call this helper function first and pass its return value (or yielded value) as this parameter."*

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `dependency` | `Callable \| None` | `None` | The function or class to run before the route (e.g., `get_db`, `get_current_user`). If omitted, FastAPI uses the parameter's type hint. |
| `use_cache` | `bool` | `True` | If the same dependency is requested twice in one HTTP request (e.g. two sub-dependencies both ask for `get_db`), `True` reuses the same result within that single request. |

* **Project Example:**
  ```python
  def create_booking(
      auth: AuthContext = Depends(get_auth_context),
      db: Session = Depends(get_db),
  ): ...
  ```

---

## 5. `Query(...)`

* **Import:** `from fastapi import Query`
* **In Simple Words:** Extracts, converts, and validates parameters from the **URL query string** (after `?`, e.g., `?date=2026-11-26&page=1`).

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `default` | `Any` | `...` (Ellipsis) | Default value if omitted by client. Pass `...` to mark the query parameter as **required**. |
| `alias` | `str \| None` | `None` | The exact name expected in the URL (e.g., `alias="date"` lets URL use `?date=...` while Python variable is named `booking_date`). |
| `ge` / `le` | `int \| float` | `None` | Greater-than-or-equal / Less-than-or-equal numeric bounds (e.g. `ge=1, le=100` for `page_size`). |
| `description` | `str \| None` | `None` | Documentation text shown in Swagger UI. |

* **Project Example (`services/parking-service/app/api/v1/parking.py`):**
  ```python
  booking_date: date = Query(alias="date")
  page: int = Query(default=1, ge=1)
  page_size: int = Query(default=20, ge=1, le=100)
  ```

---

## 6. `Header(...)`

* **Import:** `from fastapi import Header`
* **In Simple Words:** Extracts and validates an **HTTP request header** (such as `X-Internal-Service-Token`).

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `default` | `Any` | `...` | Default value if header is missing (use `None` when handling missing headers manually). |
| `alias` | `str \| None` | `None` | Exact HTTP header name (e.g., `alias="X-Internal-Service-Token"`). |
| `convert_underscores` | `bool` | `True` | Automatically maps Python `my_header` to HTTP `my-header` when `alias` is not set. |

* **Project Example (`services/parking-service/app/api/internal.py`):**
  ```python
  token: str | None = Header(default=None, alias="X-Internal-Service-Token")
  ```

---

## 7. `Response`

* **Import:** `from fastapi import Response`
* **In Simple Words:** Represents the outgoing HTTP response object. Injecting `response: Response` into a route lets you **dynamically override** the HTTP status code or set response headers while still returning a normal Pydantic model.

### Common Attributes & Methods

| Attribute / Method | Type | What it does |
| :--- | :--- | :--- |
| `response.status_code` | `int` | Overrides the route's default status code (e.g., switching `201` to `200` on an idempotent replay). |
| `response.headers` | `MutableHeaders` | Dictionary-like object to set custom HTTP response headers. |

* **Project Example (`services/payment-service/app/api/v1/payments.py`):**
  ```python
  if existing is not None:
      response.status_code = status.HTTP_200_OK
      return InternalPaymentCreateResponse(...)
  ```

---

## 8. `status`

* **Import:** `from fastapi import status`
* **In Simple Words:** A module containing readable constant names for all standard HTTP status codes, preventing magic numbers.

### Common Constants Used in Project

| Constant | Value | Meaning |
| :--- | :--- | :--- |
| `status.HTTP_200_OK` | `200` | Request succeeded. |
| `status.HTTP_201_CREATED` | `201` | New resource (vehicle, booking, payment) created. |
| `status.HTTP_401_UNAUTHORIZED` | `401` | Missing, expired, or invalid JWT / internal token. |
| `status.HTTP_404_NOT_FOUND` | `404` | Record does not exist. |
| `status.HTTP_409_CONFLICT` | `409` | Duplicate vehicle, slot overlap, or invalid state transition. |

* **Project Example (`services/vehicle-service/app/api/v1/vehicles.py`):**
  ```python
  @router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
  def create_vehicle(...):
      ...
  ```

---

## 9. `HTTPBearer(...)`

* **Import:** `from fastapi.security import HTTPBearer`
* **In Simple Words:** FastAPI security scheme that reads the `Authorization: Bearer <token>` header and activates the **Authorize padlock button** in Swagger UI (`/docs`).

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `bearerFormat` | `str \| None` | `None` | Hint for OpenAPI docs (e.g., `"JWT"`). |
| `scheme_name` | `str \| None` | `None` | Display name in OpenAPI security schemes. |
| `auto_error` | `bool` | `True` | If `True`, FastAPI immediately returns its own `403` error if header is missing. Setting `False` returns `None` so our custom `AppError(401, ...)` runs instead. |

* **Project Example (`services/parking-service/app/core/security.py`):**
  ```python
  from fastapi.security import HTTPBearer

  bearer_scheme = HTTPBearer(auto_error=False)
  ```

---

## 10. `HTTPAuthorizationCredentials`

* **Import:** `from fastapi.security import HTTPAuthorizationCredentials`
* **In Simple Words:** The object returned by `HTTPBearer(...)` containing the split parts of the `Authorization` header.

### Attributes

| Attribute | Type | Example Value | What it contains |
| :--- | :--- | :--- | :--- |
| `scheme` | `str` | `"Bearer"` | The authentication scheme prefix. |
| `credentials` | `str` | `"eyJhbGciOi..."` | The raw JWT string extracted after `"Bearer "`. |

* **Project Example (`services/parking-service/app/core/security.py`):**
  ```python
  def get_auth_context(
      credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
  ) -> AuthContext:
      if credentials is None or credentials.scheme.lower() != "bearer":
          raise AppError(401, "UNAUTHORIZED", "Authentication required.")
      raw_token = credentials.credentials
  ```

---

## 11. `jwt.encode(...)`

* **Import:** `import jwt` (from `PyJWT`)
* **In Simple Words:** Creates and cryptographically signs a JWT string from a claims dictionary.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `payload` | `dict[str, Any]` | **Required** | Claims dictionary (`sub` = user UUID, `iat` = issued at, `exp` = expiration timestamp). |
| `key` | `str \| bytes` | **Required** | Secret signing key (`settings.JWT_SECRET_KEY`). |
| `algorithm` | `str` | `"HS256"` | Cryptographic signing algorithm (`"HS256"` = HMAC with SHA-256). |
| `headers` | `dict \| None` | `None` | Optional extra JWT header fields. |

* **Returns:** Signed JWT string (`str`).
* **Project Example (`services/user-auth-service/app/core/security.py`):**
  ```python
  payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
  token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
  ```

---

## 12. `jwt.decode(...)`

* **Import:** `import jwt` (from `PyJWT`)
* **In Simple Words:** Verifies a JWT's cryptographic signature and expiration (`exp`), then unpacks its claims dictionary.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `jwt` | `str` | **Required** | The incoming raw JWT string from `credentials.credentials`. |
| `key` | `str \| bytes` | **Required** | Same secret key used to sign the token. |
| `algorithms` | `list[str]` | **Required** | **Explicit list** of allowed algorithms (e.g. `["HS256"]`) to prevent algorithm-confusion attacks. |
| `options` | `dict \| None` | `None` | Optional verification toggles (e.g. `verify_exp`). |

* **Returns:** Decoded claims `dict` (`{"sub": "...", "iat": ..., "exp": ...}`).
* **Project Example (`services/parking-service/app/core/security.py`):**
  ```python
  payload = jwt.decode(
      credentials.credentials,
      settings.JWT_SECRET_KEY,
      algorithms=[settings.JWT_ALGORITHM],
  )
  user_id = uuid.UUID(payload["sub"])
  ```

---

## 13. `jwt.PyJWTError`

* **Import:** `from jwt import PyJWTError` (or `jwt.PyJWTError`)
* **In Simple Words:** Base exception class in PyJWT. Catching `PyJWTError` catches **every** token failure: expired (`ExpiredSignatureError`), invalid signature (`InvalidSignatureError`), malformed string (`DecodeError`), etc.
* **Project Example (`services/parking-service/app/core/security.py`):**
  ```python
  try:
      payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
  except jwt.PyJWTError as exc:
      raise AppError(401, "INVALID_TOKEN", "Authentication token is invalid or expired.") from exc
  ```

---

## 14. `httpx.Client(...)`

* **Import:** `import httpx`
* **In Simple Words:** Synchronous HTTP client used by one microservice (e.g., Parking) to call another microservice (Vehicle or Payment) over REST.

### Parameters (`httpx.Client(...)`)

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `timeout` | `float \| Timeout` | `5.0` | Max seconds to wait before aborting so a slow service doesn't hang callers (`3.0` in our project). |
| `base_url` | `str` | `""` | Optional root URL prepended to relative paths. |
| `headers` | `dict` | `None` | Default headers sent on every request made by this client. |

### Request Method Parameters (`client.get(...)` / `client.post(...)`)

| Parameter | Type | What it does |
| :--- | :--- | :--- |
| `url` | `str` | Target endpoint URL (e.g. `f"{base_url}/api/v1/vehicles/{vehicle_id}"`). |
| `headers` | `dict` | Request headers (e.g. forwarding `Authorization` or `X-Internal-Service-Token`). |
| `json` | `dict` | Python dictionary automatically serialized to JSON request body (`POST`/`PUT`). |

* **Returns:** An `httpx.Response` object (`.status_code`, `.json()`, `.text`).
* **Project Example (`services/parking-service/app/services/clients.py`):**
  ```python
  with httpx.Client(timeout=3.0) as client:
      resp = client.get(
          f"{self.base_url}/api/v1/vehicles/{vehicle_id}",
          headers={"Authorization": f"Bearer {bearer_token}"},
      )
  ```

---

## 15. `httpx.HTTPError`

* **Import:** `import httpx`
* **In Simple Words:** Base exception class for all `httpx` network failures (connection refused, DNS error, read timeout). Caught so we can convert downstream outages into a clean `503 SERVICE_UNAVAILABLE` response.
* **Project Example (`services/parking-service/app/services/clients.py`):**
  ```python
  try:
      with httpx.Client(timeout=3.0) as client:
          resp = client.get(url, headers=headers)
  except httpx.HTTPError as exc:
      raise AppError(503, "VEHICLE_SERVICE_UNAVAILABLE", "Vehicle service is currently unreachable.") from exc
  ```

---

## 16. `logging.basicConfig(...)` & `logging.getLogger(...)`

* **Import:** `import logging`
* **In Simple Words:** Python's standard library logger setup (`basicConfig` configures format/level once in `main.py`; `getLogger` grabs a named logger per file).

### Parameters (`logging.basicConfig(...)`)

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `level` | `int` | `logging.WARNING` | Minimum severity to print (`INFO` shows info + warnings + errors; `DEBUG` shows everything). |
| `format` | `str` | `"%(levelname)s:%(name)s:%(message)s"` | Template for each log line (`%(asctime)s`, `%(levelname)s`, `%(name)s`, `%(message)s`). |
| `datefmt` | `str` | ISO-like | Timestamp format (e.g. `"%Y-%m-%d %H:%M:%S"`). |
| `handlers` | `list` | `[StreamHandler()]` | Optional list of outputs (e.g. console + `FileHandler("app.log")`). |

### Parameters (`logging.getLogger(...)`)

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `name` | `str \| None` | `None` | Logger name shown in logs. Passing `__name__` automatically uses the Python file's module path (e.g., `app.api.v1.auth`). |

* **Project Example (`services/user-auth-service/app/main.py` & `auth.py`):**
  ```python
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
      datefmt="%Y-%m-%d %H:%M:%S",
  )
  logger = logging.getLogger(__name__)
  logger.info("OTP request received for email: %s", email)
  ```
