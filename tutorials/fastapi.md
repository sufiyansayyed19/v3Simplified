# FastAPI Deep-Dive Tutorial — Built From `ParkingSimplified`

> **How to use this tutorial:** Every concept, pattern, and code snippet here is taken directly from our 4 microservices (`user-auth-service`, `vehicle-service`, `parking-service`, `payment-service`). New technical terms are explained briefly in plain English the first time they appear.

---

## Course Outline (All Root Topics & Subtopics)

1. **Topic 1: FastAPI Fundamentals, ASGI, Uvicorn & Request Lifecycle**
   - 1.1 What is FastAPI & Why Do We Use It?
   - 1.2 ASGI vs. WSGI & What Uvicorn Does
   - 1.3 Synchronous (`def`) vs. Asynchronous (`async def`) Routes (What We Used & Why)
   - 1.4 Creating the `FastAPI` Instance (`title`, `lifespan`)
   - 1.5 End-to-End Request Lifecycle (What Happens When a Client Calls Your API?)
   - 1.6 Health Checks (`GET /health`) & Interactive OpenAPI Docs (`/docs`)
   - 1.7 Running One Service vs. All Services with Uvicorn (`--port`, `--reload`)
2. **Topic 2: Application Lifespan (`@asynccontextmanager`)**
   - 2.1 What is a Context Manager & Lifespan Event?
   - 2.2 Startup Table Creation & Automatic Slot Seeding
   - 2.3 Startup vs. Shutdown Code Around `yield`
   - 2.4 Guarding Lifespan Startup During Automated Tests
3. **Topic 3: Routing & Modularization (`APIRouter`)**
   - 3.1 Why Not Put All Routes in `main.py`?
   - 3.2 Creating an `APIRouter` with `prefix` and `tags`
   - 3.3 HTTP Method Decorators (`@router.get`, `@router.post`, `@router.put`, `@router.delete`)
   - 3.4 Separating Public (`/api/v1`) vs. Internal (`/internal/v1`) Routers in `main.py`
4. **Topic 4: Request Inputs (Path, Query, Header, Body) & HTTP Responses**
   - 4.1 Path Parameters with Automatic Type Parsing (`uuid.UUID`)
   - 4.2 Query Parameters (`Query`, `...` Ellipsis, `alias`, `ge`/`le` Bounds)
   - 4.3 Custom HTTP Headers (`Header`, `alias`)
   - 4.4 JSON Request Bodies vs. Query Parameters
   - 4.5 `response_model`, Status Codes (`201 Created`) & Dynamic `Response` Status Overrides
   - 4.6 Synchronous Post-Actions vs. `BackgroundTasks` (Alternative Used in Auth & Payment)
5. **Topic 5: Pydantic v2 Schemas & Data Validation**
   - 5.1 What is Pydantic & What is a DTO (Schema vs. DB Model)?
   - 5.2 Serializing SQLAlchemy Objects with `ConfigDict(from_attributes=True)`
   - 5.3 Built-in Constraints (`EmailStr`, `Field`, `pattern`, `Literal`, `Decimal`)
   - 5.4 Custom Cleanup & Validation with `@field_validator`
   - 5.5 What Happens When Validation Fails (`RequestValidationError`)
6. **Topic 6: Dependency Injection (`Depends`) — FastAPI's Core Superpower**
   - 6.1 What is Dependency Injection (Plain-English Analogy)?
   - 6.2 Generator Dependencies with `yield` (Safe Database Session Lifecycle)
   - 6.3 Nested Dependencies (Dependencies Calling Other Dependencies)
   - 6.4 Injecting Clocks (`get_now`) & Inter-Service HTTP Clients
   - 6.5 Route-Level `dependencies=[Depends(...)]` (Security Gates Without Return Values)
7. **Topic 7: Security & Authentication Patterns in FastAPI**
   - 7.1 How `HTTPBearer` Extracts Bearer JWTs (`auto_error=False` Explained)
   - 7.2 Auth Dependency Flow in `user-auth-service` vs. Downstream Services
   - 7.3 `AuthContext` Dataclass for Forwarding Tokens Across Services
   - 7.4 Machine-to-Machine (M2M) Authentication with `X-Internal-Service-Token`
8. **Topic 8: Global Error Handling & Uniform JSON Envelopes**
   - 8.1 Why Raw Tracebacks & Inconsistent Errors Hurt Microservices
   - 8.2 Designing a Custom `AppError` Exception Class
   - 8.3 Registering Global Handlers with `@app.exception_handler`
   - 8.4 Overriding FastAPI's Default Validation Error (`422`) & Catching `500`s
   - 8.5 Returning Exact JSON via `JSONResponse` & Request-ID Middleware (`@app.middleware("http")`)
9. **Topic 9: Environment & Configuration Management (`pydantic-settings`)**
   - 9.1 Why We Never Hardcode Passwords or URLs in Route Files
   - 9.2 Loading `.env` Files & Environment Variables with `BaseSettings`
   - 9.3 `SettingsConfigDict` & Why `extra="ignore"` Matters
10. **Topic 10: Testing FastAPI Applications (`TestClient` & `dependency_overrides`)**
    - 10.1 How `TestClient` Calls Your App Without Opening a Real Network Port
    - 10.2 Understanding `app.dependency_overrides`
    - 10.3 Real Project Pattern 1: Swapping PostgreSQL for In-Memory SQLite (`get_db`)
    - 10.4 Real Project Pattern 2: Capturing OTP Emails & Faking Other Microservices
    - 10.5 Real Project Pattern 3: Time-Travel Testing Using `get_now` Override
11. **Topic 11: Browser Integration (`CORSMiddleware`)**
    - 11.1 What is CORS (Cross-Origin Resource Sharing)?
    - 11.2 Enabling `CORSMiddleware` When Connecting a Frontend UI

---

## Topic 1: FastAPI Fundamentals, ASGI, Uvicorn & Request Lifecycle

**Subtopics in this section:**
- 1.1 What is FastAPI & Why Do We Use It?
- 1.2 ASGI vs. WSGI & What Uvicorn Does
- 1.3 Synchronous (`def`) vs. Asynchronous (`async def`) Routes (What We Used & Why)
- 1.4 Creating the `FastAPI` Instance (`title`, `lifespan`)
- 1.5 End-to-End Request Lifecycle (What Happens When a Client Calls Your API?)
- 1.6 Health Checks (`GET /health`) & Interactive OpenAPI Docs (`/docs`)
- 1.7 Running One Service vs. All Services with Uvicorn (`--port`, `--reload`)

### 1.1 What is FastAPI & Why Do We Use It?
* **FastAPI** is a modern Python web framework for building HTTP/REST APIs.
* Its core idea is **single-source-of-truth Python type hints**. When you write `vehicle_id: uuid.UUID` or `payload: BookingCreateRequest`, FastAPI uses that single type hint to do **four jobs automatically**:
  1. Parse the incoming HTTP request (URL, query string, headers, JSON body).
  2. Validate that the data matches your rules (e.g., valid UUID, valid email, integer $\ge 1$).
  3. Convert JSON strings into real Python objects (`uuid.UUID`, `date`, `time`, `Decimal`).
  4. Generate live interactive documentation (`/docs`) so anyone can test your API in a browser.

### 1.2 ASGI vs. WSGI & What Uvicorn Does
* **WSGI (Web Server Gateway Interface)**: The older Python web standard (used by Flask and classic Django). WSGI handles one synchronous function call per worker thread and cannot natively pause while waiting for slow I/O.
* **ASGI (Asynchronous Server Gateway Interface)**: The modern successor to WSGI. ASGI supports both regular synchronous `def` endpoints (FastAPI runs them safely in an internal threadpool) and `async def` non-blocking endpoints, plus startup/shutdown **lifespan** events.
* **Uvicorn**: A high-speed **ASGI web server**. FastAPI by itself is just Python code defining routes; it cannot listen on TCP port `8001` alone. **Uvicorn** opens the network socket on `127.0.0.1:8001`, parses raw HTTP bytes from the client, and calls your FastAPI `app`.

### 1.3 Synchronous (`def`) vs. Asynchronous (`async def`) Routes (What We Used & Why)
In `ParkingSimplified`, **all route handlers use regular synchronous `def`** (e.g., `def create_booking(...)`, `def create_vehicle(...)`) rather than `async def`. Why?
* **Event Loop**: In Python `asyncio`, a single thread runs an event loop switching rapidly between tasks while they `await` network I/O. If you write `async def` and call a blocking synchronous library inside it (like standard SQLAlchemy `Session` or synchronous `httpx.Client`), you **freeze the entire server's event loop** for every other user!
* **How FastAPI handles our `def` routes**: FastAPI automatically runs normal `def` functions inside an **AnyIO worker threadpool**, so synchronous PostgreSQL queries (`psycopg`) and synchronous `httpx.Client` calls never block the main server loop.
* **When to use the `async def` alternative**: Only when your database driver and HTTP clients are **also asynchronous** (e.g., `sqlalchemy.ext.asyncio.AsyncSession` + `asyncpg` + `await httpx.AsyncClient().get(...)`), or for lightweight framework hooks like `lifespan` and `@app.exception_handler`.

### 1.4 Creating the `FastAPI` Instance
Every service has an `app/main.py` that instantiates one `FastAPI` object:

```python
# From services/user-auth-service/app/main.py
app = FastAPI(title="Corporate Parking — User/Auth Service", lifespan=lifespan)

register_exception_handlers(app)
app.include_router(auth_router)
```

* **`title`**: Appears at the top of Swagger UI (`/docs`) and in the generated OpenAPI JSON (`/openapi.json`).
* **`lifespan`**: Points to our startup/shutdown function (covered in Topic 2).

### 1.5 End-to-End Request Lifecycle (What Happens When a Client Calls Your API?)
Suppose an employee sends `POST http://127.0.0.1:8002/api/v1/vehicles` with a Bearer token and JSON body. Here is the exact 8-step journey inside FastAPI:

```text
1. Client sends HTTP request ──▶ Uvicorn receives bytes on port 8002
2. FastAPI Router matches method (POST) + path (/api/v1/vehicles) ──▶ vehicles.create_vehicle
3. Dependency Injection runs Depends(get_current_user_id) & Depends(get_db)
   └─ If JWT is invalid, AppError(401) is raised immediately; route body NEVER runs!
4. Pydantic parses & validates JSON body against VehicleCreate
   └─ Runs normalize_vehicle_number(); if invalid, raises RequestValidationError (422)
5. Your Python route function create_vehicle(...) executes with validated payload, user_id, db
6. Route returns VehicleResponse (or raises AppError e.g. 409 VEHICLE_ALREADY_REGISTERED)
7. FastAPI serializes response_model=VehicleResponse to JSON (or exception_handler builds error JSON)
8. Depends(get_db) resumes its finally block and closes the PostgreSQL session ──▶ Uvicorn sends HTTP 201
```

### 1.6 Health Checks (`GET /health`) & Interactive OpenAPI Docs (`/docs`)
Every microservice in our project exposes `/health`:

```python
# From services/parking-service/app/main.py
@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.SERVICE_NAME}
```

* **`@app.get("/health")`**: Registers an HTTP `GET` handler at `/health`. Returning a Python `dict` causes FastAPI to respond with `200 OK` and `Content-Type: application/json`.
* **OpenAPI**: An industry-standard JSON format (`/openapi.json`) describing every endpoint, header, request schema, and response code.
* **Swagger UI (`/docs`)** and **ReDoc (`/redoc`)**: FastAPI automatically serves two visual documentation pages generated from that OpenAPI spec:
  * `http://127.0.0.1:8001/docs` (User/Auth)
  * `http://127.0.0.1:8002/docs` (Vehicle)
  * `http://127.0.0.1:8003/docs` (Parking)
  * `http://127.0.0.1:8004/docs` (Payment)

### 1.7 Running One Service vs. All Services with Uvicorn
To start a single service (for example `parking-service` on port `8003`):
```powershell
cd services\parking-service
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8003 --reload
```
* **`app.main:app`**: Python module path (`app/main.py`) + colon + variable name (`app`).
* **`--port 8003`**: TCP port to bind. Because each microservice is an independent process, they run simultaneously on `8001`, `8002`, `8003`, and `8004`.
* **`--reload`**: Watches `.py` files using WatchFiles and restarts the worker process automatically whenever you save changes. *(Used in local dev only; never in production because watching files uses extra CPU/memory.)*

---

## Topic 2: Application Lifespan (`@asynccontextmanager`)

**Subtopics in this section:**
- 2.1 What is a Context Manager & Lifespan Event?
- 2.2 Startup Table Creation & Automatic Slot Seeding
- 2.3 Startup vs. Shutdown Code Around `yield`
- 2.4 Guarding Lifespan Startup During Automated Tests

### 2.1 What is a Context Manager & Lifespan Event?
* **Context Manager**: A Python object (usually used with `with ...:`) that runs **setup code** when entering a block and **cleanup code** when exiting.
* **`@asynccontextmanager`**: A decorator from Python's `contextlib` module that turns an `async def` generator function containing one `yield` into an asynchronous context manager.
* **Lifespan Event**: FastAPI enters this context manager **once when Uvicorn starts** (before handling the first HTTP request) and exits it **once when Uvicorn stops** (when you press `Ctrl+C`).

### 2.2 Startup Table Creation & Automatic Slot Seeding
Look at `services/parking-service/app/main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    if get_db not in app_instance.dependency_overrides:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_default_slots(db)
    yield
```

* **`Base.metadata.create_all(bind=engine)`**: Inspects every SQLAlchemy `Base` subclass (`ParkingSlot`, `Booking`) and runs `CREATE TABLE IF NOT EXISTS ...` against PostgreSQL.
* **`seed_default_slots(db)`**: Checks if `parking_slots` has `0` rows; if empty, inserts `C01`–`C60` and `B01`–`B40` (100 slots total) so the service works immediately out of the box.
* **Important subtle detail (`import app.models`)**: In `user-auth-service`, `vehicle-service`, and `payment-service`, `main.py` includes `import app.models  # noqa: F401`. Even though `models` isn't referenced directly in `main.py`, importing it registers the ORM classes onto `Base.metadata` before `create_all()` runs!

### 2.3 Startup vs. Shutdown Code Around `yield`
```python
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # --- STARTUP PHASE (runs once before server accepts requests) ---
    initialize_database()
    yield  # Server is now LIVE and serving requests
    # --- SHUTDOWN PHASE (runs once when server stops) ---
    # e.g., close connection pools or flush logs
```
* Think of `yield` as the pause button while the server is alive: code **above** `yield` runs at boot; code **below** `yield` runs on shutdown.

### 2.4 Guarding Lifespan Startup During Tests
Notice this line in every service's `lifespan`:
```python
if get_db not in app_instance.dependency_overrides:
```
* Why did we write that `if`?
  * When a developer runs `with TestClient(app) as client:`, FastAPI executes `lifespan()`.
  * In unit tests, `test_auth.py` or `test_parking.py` overrides `get_db` to point to an **in-memory SQLite** database instead of PostgreSQL.
  * Without that guard, `Base.metadata.create_all(bind=engine)` would still try to connect to `localhost:5432` PostgreSQL and fail if PostgreSQL isn't running!

---

## Topic 3: Routing & Modularization (`APIRouter`)

**Subtopics in this section:**
- 3.1 Why Not Put All Routes in `main.py`?
- 3.2 Creating an `APIRouter` with `prefix` and `tags`
- 3.3 HTTP Method Decorators (`@router.get`, `@router.post`, `@router.put`, `@router.delete`)
- 3.4 Separating Public (`/api/v1`) vs. Internal (`/internal/v1`) Routers in `main.py`

### 3.1 Why Not Put All Routes in `main.py`?
If a service grows to 10+ endpoints, putting all routes, schemas, and queries in `main.py` creates a giant, unreadable file.
* **`APIRouter`**: A modular route container provided by FastAPI. You define endpoints on `router` inside `app/api/v1/*.py`, and then plug `router` into `app` inside `app/main.py`.

### 3.2 Creating an `APIRouter` with `prefix` and `tags`
```python
# From services/parking-service/app/api/v1/parking.py
router = APIRouter(prefix="/api/v1/parking", tags=["parking"])
```
* **`prefix="/api/v1/parking"`**: Automatically prepends this path segment to every route in `parking.py`.
  * `@router.get("/availability")` becomes `/api/v1/parking/availability`.
  * `@router.post("/bookings")` becomes `/api/v1/parking/bookings`.
  * Why `v1`? URI versioning lets you later introduce `app/api/v2/parking.py` with `prefix="/api/v2/parking"` without breaking older mobile/web clients still calling `v1`.
* **`tags=["parking"]`**: Groups all routes from this file under one clean section header in Swagger UI (`/docs`).

### 3.3 HTTP Method Decorators (`@router.get`, `@router.post`, `@router.put`, `@router.delete`)
In `services/vehicle-service/app/api/v1/vehicles.py`, our CRUD endpoints map directly to standard REST HTTP verbs:

```python
router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])

@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(...): ...      # CREATE  -> POST   /api/v1/vehicles

@router.get("", response_model=VehicleListResponse)
def list_vehicles(...): ...       # LIST    -> GET    /api/v1/vehicles

@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(...): ...         # READ 1  -> GET    /api/v1/vehicles/{vehicle_id}

@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(...): ...      # UPDATE  -> PUT    /api/v1/vehicles/{vehicle_id}

@router.delete("/{vehicle_id}", response_model=VehicleDeactivateResponse)
def deactivate_vehicle(...): ...  # DELETE  -> DELETE /api/v1/vehicles/{vehicle_id}
```
* **Tip**: Notice `@router.post("")` (empty string) when `prefix="/api/v1/vehicles"`. In FastAPI, `""` creates `/api/v1/vehicles` (no trailing slash), whereas `"/"` creates `/api/v1/vehicles/`. Using `""` avoids unnecessary HTTP `307 Temporary Redirect` responses!

### 3.4 Separating Public (`/api/v1`) vs. Internal (`/internal/v1`) Routers in `main.py`
In `parking-service/app/main.py`, two routers are mounted on the same `app`:

```python
# Public employee-facing routes (/api/v1/parking/*)
app.include_router(parking_router)

# Internal service-to-service routes (/internal/v1/*)
app.include_router(internal_router)
```
* Keeping `internal.py` in its own router makes it immediately obvious (both in code and in Swagger UI under `internal` vs. `parking` tags) which endpoints are public vs. machine-only.

---

## Topic 4: Request Inputs (Path, Query, Header, Body) & HTTP Responses

**Subtopics in this section:**
- 4.1 Path Parameters with Automatic Type Parsing (`uuid.UUID`)
- 4.2 Query Parameters (`Query`, `...` Ellipsis, `alias`, `ge`/`le` Bounds)
- 4.3 Custom HTTP Headers (`Header`, `alias`)
- 4.4 JSON Request Bodies vs. Query Parameters
- 4.5 `response_model`, Status Codes (`201 Created`) & Dynamic `Response` Status Overrides
- 4.6 Synchronous Post-Actions vs. `BackgroundTasks` (Alternative Used in Auth & Payment)

### 4.1 Path Parameters with Automatic Type Parsing (`uuid.UUID`)
A **Path Parameter** is a dynamic placeholder inside the URL path itself:

```python
# From services/parking-service/app/api/v1/parking.py
@router.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: uuid.UUID,
    ...
):
```
* When a client calls `GET /api/v1/parking/bookings/3fa85f64-5717-4562-b3fc-2c963f66afa6`:
  * FastAPI matches `{booking_id}` to the parameter `booking_id: uuid.UUID`.
  * It automatically parses the string into a Python `uuid.UUID` object before entering `get_booking()`.
  * If a client sends `/bookings/abc123` (invalid UUID), FastAPI rejects it immediately with HTTP `422`.

### 4.2 Query Parameters (`Query`, `...` Ellipsis, `alias`, `ge`/`le` Bounds)
**Query Parameters** are key-value pairs after `?` in the URL (e.g., `?date=2026-11-26&start_time=09:00`).

Look at two real examples from `services/parking-service/app/api/v1/parking.py`:

**Example A — Required query parameters + `alias`:**
```python
@router.get("/availability", response_model=AvailabilityResponse)
def check_availability(
    booking_date: date = Query(alias="date"),
    start_time: time = Query(...),
    end_time: time = Query(...),
    vehicle_id: uuid.UUID = Query(...),
    requires_charging: bool = Query(...),
    ...
):
```
* **`...` (Ellipsis)**: Means **required** (no default value). Notice `booking_date` didn't have a default either, and `Query(alias="date")` makes `?date=...` required in the URL while naming the Python variable `booking_date` (so it doesn't collide with `from datetime import date`!).
* FastAPI also converts `?requires_charging=true` (or `1` / `yes`) into Python `True`, and `?start_time=09:00` into `datetime.time(9, 0)`.

**Example B — Optional query parameters with defaults and validation bounds:**
```python
@router.get("/bookings", response_model=BookingListResponse)
def list_bookings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    ...
):
```
* If the client calls `/api/v1/parking/bookings` with no query string, `page` defaults to `1` and `page_size` defaults to `20`.
* `ge=1` ("greater than or equal to 1") and `le=100` ("less than or equal to 100") prevent invalid `?page=0` or `?page_size=100000` queries.

### 4.3 Custom HTTP Headers (`Header`, `alias`)
In `payment-service`, we read a custom test header cleanly using `Header`:

```python
# From services/payment-service/app/api/v1/payments.py
test_outcome_header: str | None = Header(default=None, alias="X-Test-Payment-Outcome")
```
* HTTP headers use hyphens (`X-Test-Payment-Outcome`), which aren't legal in Python variable names. `alias="X-Test-Payment-Outcome"` maps the header cleanly to `test_outcome_header`.
* Setting `default=None` makes the header optional so real users don't have to send it.

### 4.4 JSON Request Bodies vs. Query Parameters
How does FastAPI know whether a function parameter comes from the URL query string or from the JSON request body?
* **Simple scalar types** (`int`, `str`, `bool`, `date`, `uuid.UUID`) $\rightarrow$ **Path** (if in URL `{...}`) or **Query** (if not in URL).
* **Pydantic `BaseModel` subclass** (like `payload: BookingCreateRequest`) $\rightarrow$ **JSON Request Body**.

```python
# POST /api/v1/parking/bookings expects JSON body matching BookingCreateRequest:
def create_booking(payload: BookingCreateRequest, ...):
```

### 4.5 `response_model`, Status Codes (`201 Created`) & Dynamic `Response` Status Overrides
* **`response_model=BookingResponse`**:
  1. Documents the exact response JSON schema in Swagger UI (`/docs`).
  2. Filters/validates the return value against `BookingResponse` before sending it over HTTP.
* **`status_code=status.HTTP_201_CREATED`**: By default FastAPI sends `200 OK`. For resource creation (`POST /vehicles`, `POST /bookings`, `POST /internal/v1/payments`), we explicitly set `201 Created`.
* **Dynamic Status Code (`Response`)**: In `payment-service`'s idempotent `create_internal_payment()`:
  * A brand-new payment returns `201 Created` (the decorator's default).
  * An idempotent retry for an already-existing `booking_id` injects `response: Response` and sets:
    ```python
    response.status_code = status.HTTP_200_OK
    ```
  * This lets one endpoint return `201` on creation and `200` on idempotent replay!

### 4.6 Synchronous Post-Actions vs. `BackgroundTasks` (Alternative Used in Auth & Payment)
Notice how two of our routes trigger secondary side effects right after committing to PostgreSQL:
* In `user-auth-service` (`send_company_code`): saves the OTP in DB, then **synchronously** calls `email_sender.send_otp(...)` before returning `200 OK`.
* In `payment-service` (`process_payment`): commits `SUCCESS`/`FAILED`, then **synchronously** calls `callback_client.deliver_payment_result(...)` before returning `200 OK`.

Why did we do it synchronously? Because in a fresher-friendly & deterministic architecture, immediate confirmation ensures `ConsoleEmailSender` logs immediately and `parking-service` is already `CONFIRMED` the millisecond `POST /payments/{id}/process` returns!

* **What is the alternative (`BackgroundTasks`)?**
  FastAPI includes `from fastapi import BackgroundTasks`. If sending a real SMTP email takes 2 seconds, you don't want the user's browser spinning for 2 seconds—you can schedule it to run **right after the HTTP response is sent**:
  ```python
  # Alternative approach if using slow SMTP email in production:
  def send_company_code(payload: SendCodeRequest, background_tasks: BackgroundTasks, ...):
      ... # save OTP to DB
      background_tasks.add_task(email_sender.send_otp, email=email, code=raw_code, expires_minutes=5)
      return MessageResponse(message="Verification code sent successfully")
  ```
  *Note: For critical payment callbacks, `BackgroundTasks` alone is risky if the process restarts mid-task—production systems use a persistent queue (like RabbitMQ/Celery/Outbox) or keep synchronous confirmation with retries.*

---

## Topic 5: Pydantic v2 Schemas & Data Validation

**Subtopics in this section:**
- 5.1 What is Pydantic & What is a DTO (Schema vs. DB Model)?
- 5.2 Serializing SQLAlchemy Objects with `ConfigDict(from_attributes=True)`
- 5.3 Built-in Constraints (`EmailStr`, `Field`, `pattern`, `Literal`, `Decimal`)
- 5.4 Custom Cleanup & Validation with `@field_validator`
- 5.5 What Happens When Validation Fails (`RequestValidationError`)

### 5.1 What is Pydantic & What is a DTO (Schema vs. DB Model)?
* **Pydantic**: Python's fastest data validation library (powered by a Rust core in Pydantic v2). FastAPI uses Pydantic for every request body and response model.
* **DTO (Data Transfer Object)**: A plain data class whose only job is shaping data entering or leaving an API (`app/schemas/*.py`), separate from your database tables (`app/models/*.py`).
* **Why keep `models/` and `schemas/` separate?**
  * In `user-auth-service`, the `VerificationCode` DB table has internal columns like `code_hash` and `consumed_at` that users must **never** see.
  * Similarly, `User` is returned as `UserProfile` (`id`, `email`, `name`), hiding internal timestamps (`created_at`, `updated_at`) from the public profile contract.

### 5.2 Serializing SQLAlchemy Objects with `ConfigDict(from_attributes=True)`
```python
# From services/vehicle-service/app/schemas/vehicle.py
class VehicleResponse(BaseModel):
    id: uuid.UUID
    vehicle_number: str
    vehicle_type: VehicleType
    is_ev: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
```
* **Why `from_attributes=True`?**
  * SQLAlchemy queries return an ORM object (`vehicle.id`, `vehicle.vehicle_number`), not a `dict` (`vehicle["id"]`).
  * With `ConfigDict(from_attributes=True)`, calling `VehicleResponse.model_validate(vehicle)` (or returning `vehicle` directly from a route with `response_model=VehicleResponse`) tells Pydantic to read attributes using dot notation (`obj.attr`).

### 5.3 Built-in Constraints (`EmailStr`, `Field`, `pattern`, `Literal`, `Decimal`)
Our schemas use Pydantic's built-in types to block bad data before a single line of business logic runs:

```python
# From services/user-auth-service/app/schemas/auth.py
class SendCodeRequest(BaseModel):
    email: EmailStr

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
```
* **`EmailStr`**: Requires `email-validator` and rejects malformed emails like `"not-an-email"`.
* **`Field(min_length=6, max_length=6, pattern=r"^\d{6}$")`**: Ensures OTP codes are **exactly 6 numeric digits** (`"123456"` passes; `"12345"` or `"12ab56"` fails with `422`).
* **`Literal["UPI", "CARD", "WALLET"]`** (`services/payment-service/app/schemas/payment.py`): Rejects any `payment_method` outside those 3 strings (e.g., `"CRYPTO"` fails automatically).
* **`Decimal = Field(gt=0)`**: Rejects zero or negative payment amounts (`0`, `-50.00`).

### 5.4 Custom Cleanup & Validation with `@field_validator`
Users type vehicle plates inconsistently (`"ka-01 ab 1234"`, `"KA01AB1234"`, `" ka 01-ab-1234 "`). Instead of repeating cleanup code in every route, `VehicleCreate` and `VehicleUpdate` normalize it automatically:

```python
# From services/vehicle-service/app/schemas/vehicle.py
_PLATE_PATTERN = re.compile(r"^[A-Z0-9]{4,20}$")

def normalize_vehicle_number(raw: str) -> str:
    cleaned = re.sub(r"[\s-]+", "", raw.strip()).upper()
    if not _PLATE_PATTERN.match(cleaned):
        raise ValueError("Vehicle number must be 4-20 alphanumeric characters.")
    return cleaned

class VehicleCreate(BaseModel):
    vehicle_number: str
    vehicle_type: VehicleType
    is_ev: bool

    @field_validator("vehicle_number")
    @classmethod
    def validate_plate(cls, v: str) -> str:
        return normalize_vehicle_number(v)
```
* **`@field_validator("vehicle_number")`**: Runs automatically whenever Pydantic parses `VehicleCreate` or `VehicleUpdate`.
* If `normalize_vehicle_number()` returns `"KA01AB1234"`, that cleaned value replaces the raw string inside `payload.vehicle_number`.
* If it raises `ValueError`, Pydantic turns it into a `422` validation error automatically.

### 5.5 What Happens When Validation Fails (`RequestValidationError`)
When any Path, Query, Header, or Pydantic body constraint fails, FastAPI raises `RequestValidationError` **before** calling your endpoint function. In Topic 8, we see how our custom handler catches `RequestValidationError` and formats it into our uniform error envelope (`INVALID_REQUEST`, `INVALID_VEHICLE_DATA`, `INVALID_BOOKING_REQUEST`, `INVALID_PAYMENT_REQUEST`).

---

## Topic 6: Dependency Injection (`Depends`) — FastAPI's Core Superpower

**Subtopics in this section:**
- 6.1 What is Dependency Injection (Plain-English Analogy)?
- 6.2 Generator Dependencies with `yield` (Safe Database Session Lifecycle)
- 6.3 Nested Dependencies (Dependencies Calling Other Dependencies)
- 6.4 Injecting Clocks (`get_now`) & Inter-Service HTTP Clients
- 6.5 Route-Level `dependencies=[Depends(...)]` (Security Gates Without Return Values)

### 6.1 What is Dependency Injection (Plain-English Analogy)?
Imagine cooking in a restaurant kitchen:
* **Without DI**: Every time a chef needs to cook a dish, the chef has to drive to the farm to milk a cow, grind wheat, and light a wood fire first.
* **With DI (`Depends`)**: The chef writes `"I need: db, current_user, clock"` in the function signature, and FastAPI's kitchen runner prepares and hands those exact items to the function right before it runs—and cleans them up afterward.

Why is this huge?
1. **Zero repetition**: You write DB connection and JWT auth logic **once**, then plug it into 10 routes with 1 parameter.
2. **Testability**: In tests, you swap PostgreSQL for SQLite or swap the real clock for a mock clock without editing a single line of route code!

### 6.2 Generator Dependencies with `yield` (Safe Database Session Lifecycle)
```python
# From services/parking-service/app/core/database.py
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
Step-by-step trace during a single HTTP request:
1. FastAPI calls `get_db()` and runs up to `yield db`.
2. FastAPI passes `db` into your route: `def list_bookings(..., db: Session = Depends(get_db))`.
3. `list_bookings()` runs SQL queries and returns `BookingListResponse`.
4. **After** your route returns (or even if it raises `AppError(404, ...)`!), FastAPI resumes `get_db()`, enters `finally:`, and calls `db.close()`, returning the connection cleanly to SQLAlchemy's connection pool.

### 6.3 Nested Dependencies (Dependencies Calling Other Dependencies)
A dependency function can itself use `Depends(...)`! Look at `get_current_user` in `user-auth-service`:

```python
# From services/user-auth-service/app/core/security.py
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "UNAUTHENTICATED", "Missing or invalid authorization header.")

    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if not user:
        raise AppError(401, "UNAUTHENTICATED", "Authenticated user not found.")
    return user
```
And then the route becomes just 2 lines:
```python
@router.get("/users/me", response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)):
    return UserProfile.model_validate(current_user)
```
FastAPI automatically resolves the entire graph: `bearer_scheme` + `get_db` $\rightarrow$ `get_current_user` $\rightarrow$ `get_me` $\rightarrow$ closes `db`!

### 6.4 Injecting Clocks (`get_now`) & Inter-Service HTTP Clients
In `services/parking-service/app/api/v1/parking.py`, notice that routes do **not** call `datetime.now()` or `VehicleServiceClient()` directly inside the function body:

```python
def create_booking(
    payload: BookingCreateRequest,
    auth: AuthContext = Depends(get_auth_context),
    now: datetime = Depends(get_now),
    db: Session = Depends(get_db),
    vehicle_client: VehicleServiceClient = Depends(get_vehicle_client),
    payment_client: PaymentServiceClient = Depends(get_payment_client),
):
```
* **Why inject `now: datetime = Depends(get_now)`?** Because booking rules depend heavily on current time (`07:00–22:00`, today vs. tomorrow, 5-minute hold expiry). Injecting time via `Depends` means unit tests can simulate `08:30`, then jump 6 minutes forward to `08:36` without sleeping!
* **Why inject `vehicle_client` and `payment_client`?** Unit tests for `parking-service` can run completely standalone (without starting `vehicle-service` on `:8002` or `payment-service` on `:8004`) by overriding these two dependencies.

### 6.5 Route-Level `dependencies=[Depends(...)]` (Security Gates Without Return Values)
```python
# From services/parking-service/app/api/internal.py
@router.post(
    "/bookings/{booking_id}/payment-result",
    response_model=PaymentResultResponse,
    dependencies=[Depends(_require_internal_token)],
)
def apply_payment_result(
    booking_id: uuid.UUID,
    payload: PaymentResultRequest,
    ...
):
```
* `_require_internal_token` returns `None`—the route body doesn't need any value from it; it only needs the check to pass before entering `apply_payment_result()`. Putting it inside `dependencies=[...]` in the decorator keeps the function signature clean.

---

## Topic 7: Security & Authentication Patterns in FastAPI

**Subtopics in this section:**
- 7.1 How `HTTPBearer` Extracts Bearer JWTs (`auto_error=False` Explained)
- 7.2 Auth Dependency Flow in `user-auth-service` vs. Downstream Services
- 7.3 `AuthContext` Dataclass for Forwarding Tokens Across Services
- 7.4 Machine-to-Machine (M2M) Authentication with `X-Internal-Service-Token`

### 7.1 How `HTTPBearer` Extracts Bearer JWTs (`auto_error=False` Explained)
* **Bearer Token**: An HTTP authentication scheme (`Authorization: Bearer eyJhbGci...`) meaning *"give access to whoever bears (carries) this signed token."*

```python
# From services/vehicle-service/app/core/security.py
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> uuid.UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "UNAUTHENTICATED", "Missing or invalid authorization header.")

    return decode_access_token(credentials.credentials)
```
* **What `HTTPBearer` gives you:**
  1. Parses the `Authorization` header and splits `"Bearer <token>"` into `credentials.scheme` (`"Bearer"`) and `credentials.credentials` (`"<token>"`).
  2. Automatically adds the **"Authorize 🔒"** button to Swagger UI (`/docs`) so you can paste your JWT once and test protected endpoints!
* **Why `auto_error=False`?** By default (`auto_error=True`), if the header is missing, Starlette returns `403 {"detail": "Not authenticated"}`. Setting `auto_error=False` gives us `credentials = None` so we can raise our own `AppError(401, "UNAUTHENTICATED", ...)` matching our uniform JSON error format.

### 7.2 Auth Dependency Flow in `user-auth-service` vs. Downstream Services
Notice the intentional difference between `user-auth-service` and the other 3 services:
* **`user-auth-service`** uses `get_current_user()` $\rightarrow$ decodes the JWT **and queries `user_db`** to return the full `User` row for `/api/v1/users/me`.
* **`vehicle-service`, `parking-service`, `payment-service`** use `get_current_user_id()` / `get_auth_context()` $\rightarrow$ decode the HS256 JWT **locally using the shared `JWT_SECRET_KEY`** and extract `uuid.UUID(payload["sub"])` **with zero database or HTTP calls to `user-auth-service`**.

### 7.3 `AuthContext` Dataclass for Forwarding Tokens Across Services
When a user calls `parking-service` to hold a slot (`POST /api/v1/parking/bookings`), `parking-service` must ask `vehicle-service` (`GET /api/v1/vehicles/{vehicle_id}`) if the vehicle belongs to that user.

To forward the caller's exact Bearer JWT to `vehicle-service`, `parking-service` defines a small Python `@dataclass`:

```python
# From services/parking-service/app/core/security.py
@dataclass
class AuthContext:
    user_id: uuid.UUID
    raw_token: str

def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "UNAUTHENTICATED", "Missing or invalid authorization header.")

    user_id = decode_access_token(credentials.credentials)
    return AuthContext(user_id=user_id, raw_token=credentials.credentials)
```
* **`auth.user_id`** is used by `parking-service` to save `Booking.user_id` and check `USER_BOOKING_OVERLAP`.
* **`auth.raw_token`** is passed into `vehicle_client.get_owned_vehicle(vehicle_id=..., bearer_token=auth.raw_token)` so `vehicle-service` independently authenticates the same user!

### 7.4 Machine-to-Machine (M2M) Authentication with `X-Internal-Service-Token`
* **M2M (Machine-to-Machine)**: Direct service-to-service calls that do not represent a human user clicking a button—for example, `parking-service` creating a pending payment in `payment-service`, or `payment-service` posting a callback to `parking-service`.

Both internal endpoints guard access using a `Header` dependency:
```python
# From services/parking-service/app/api/internal.py
def _require_internal_token(
    token: str | None = Header(default=None, alias="X-Internal-Service-Token"),
) -> None:
    if not token or token != settings.INTERNAL_SERVICE_TOKEN:
        raise AppError(401, "INTERNAL_CALLER_UNAUTHORIZED", "Invalid internal service token.")
```
* If an employee or external attacker tries to call `POST /internal/v1/bookings/{id}/payment-result` with their user JWT instead of `X-Internal-Service-Token`, FastAPI rejects it with `401 INTERNAL_CALLER_UNAUTHORIZED`.

---

## Topic 8: Global Error Handling & Uniform JSON Envelopes

**Subtopics in this section:**
- 8.1 Why Raw Tracebacks & Inconsistent Errors Hurt Microservices
- 8.2 Designing a Custom `AppError` Exception Class
- 8.3 Registering Global Handlers with `@app.exception_handler`
- 8.4 Overriding FastAPI's Default Validation Error (`422`) & Catching `500`s
- 8.5 Returning Exact JSON via `JSONResponse` & Request-ID Middleware (`@app.middleware("http")`)

### 8.1 Why Raw Tracebacks & Inconsistent Errors Hurt Microservices
Without centralized error handling:
* FastAPI's built-in `HTTPException` returns `{"detail": "..."}`.
* Pydantic validation failures return `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`.
* Unhandled bugs return plain text `"Internal Server Error"`.

Frontend apps and caller services would need 3 different parsers just to display an error message! Instead, all 4 of our services guarantee **one single JSON error envelope** for every failure:
```json
{
  "error": {
    "code": "NO_PARKING_CAPACITY",
    "message": "No compatible parking slot is available for the requested interval.",
    "request_id": "c7a6e920-4f1b-4d8e-9b2a-81f0e319c401"
  }
}
```

### 8.2 Designing a Custom `AppError` Exception Class
```python
# From services/parking-service/app/core/errors.py
class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)
```
* Any service layer (`rules.py`, `clients.py`, `security.py`, or route handlers) can simply `raise AppError(422, "CHARGING_NOT_SUPPORTED", "...")` without knowing anything about HTTP `JSONResponse` formatting.

### 8.3 Registering Global Handlers with `@app.exception_handler`
Inside `register_exception_handlers(app)` (`app/core/errors.py`), we attach four handlers directly to the `FastAPI` instance (`@app.exception_handler(...)`), called from `app/main.py`:

```python
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": _request_id(request),
            }
        },
    )
```

### 8.4 Overriding FastAPI's Default Validation Error (`422`) & Catching `500`s
We also register three framework handlers in `errors.py`:
1. **`@app.exception_handler(RequestValidationError)`**: Intercepts Pydantic `422` errors and returns our standard envelope (`code="INVALID_REQUEST"` / `"INVALID_VEHICLE_DATA"` / `"INVALID_BOOKING_REQUEST"` / `"INVALID_PAYMENT_REQUEST"`).
2. **`@app.exception_handler(HTTPException)`**: Formats any framework-level `HTTPException` (`code="HTTP_ERROR"`).
3. **`@app.exception_handler(Exception)`**: Catch-all fallback returning `500 INTERNAL_ERROR` so internal Python stack traces or SQL snippets are never leaked to callers.

### 8.5 Returning Exact JSON via `JSONResponse` & Request-ID Middleware (`@app.middleware("http")`)
* **`JSONResponse`**: A Starlette/FastAPI response class used when you need full control over `status_code` and raw JSON `content` outside normal route return values (such as inside exception handlers).

Notice line 16 of `app/core/errors.py`:
```python
def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))
```
Right now, `_request_id()` generates a fallback `str(uuid.uuid4())` whenever `request.state.request_id` isn't set.
* **What is Middleware (`@app.middleware("http")`)?**
  **Middleware** is a wrapper function that runs **before every single request reaches any route** and **after the response comes back**.
* In production, instead of generating a new UUID only on error, you attach a Request-ID middleware in `main.py` so **both success and error responses** share the exact same `X-Request-ID` correlation header across all 4 microservices:
  ```python
  @app.middleware("http")
  async def attach_request_id(request: Request, call_next):
      request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
      request.state.request_id = request_id          # errors.py reads this automatically!
      response = await call_next(request)            # Runs the matched route
      response.headers["X-Request-ID"] = request_id
      return response
  ```

---

## Topic 9: Environment & Configuration Management (`pydantic-settings`)

**Subtopics in this section:**
- 9.1 Why We Never Hardcode Passwords or URLs in Route Files
- 9.2 Loading `.env` Files & Environment Variables with `BaseSettings`
- 9.3 `SettingsConfigDict` & Why `extra="ignore"` Matters

### 9.1 Why We Never Hardcode Passwords or URLs in Route Files
A microservice runs in multiple environments:
* **Local Dev**: `DATABASE_URL` points to `localhost:5432`, `ENVIRONMENT=development`.
* **Staging / Production**: `DATABASE_URL` points to a managed RDS/Cloud SQL cluster, `ENVIRONMENT=production`, and `JWT_SECRET_KEY` is injected from a secrets manager.

### 9.2 Loading `.env` Files & Environment Variables with `BaseSettings`
Each service defines a single `Settings` class in `app/core/config.py`:

```python
# From services/parking-service/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SERVICE_NAME: str = "parking-service"
    HOST: str = "0.0.0.0"
    PORT: int = 8003
    DATABASE_URL: str = "postgresql+psycopg://parking_user:parking_pass@localhost:5432/parking_db"

    BUSINESS_TIMEZONE: str = "Asia/Kolkata"
    JWT_SECRET_KEY: str = "super-secret-jwt-key-for-corporate-parking"
    JWT_ALGORITHM: str = "HS256"

    VEHICLE_SERVICE_URL: str = "http://127.0.0.1:8002"
    PAYMENT_SERVICE_URL: str = "http://127.0.0.1:8004"
    INTERNAL_SERVICE_TOKEN: str = "dev-internal-service-token"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
```
* **Priority Order**: OS environment variables override `.env` file values, which override the Python class defaults above.
* Because `Settings` inherits from Pydantic `BaseSettings`, setting `PORT=abc` fails immediately at startup with a clear type error rather than crashing mysteriously later.

### 9.3 `SettingsConfigDict` & Why `extra="ignore"` Matters
* **`env_file=".env"`**: Reads variables automatically from a `.env` file in the service's working directory (`services/user-auth-service/.env`, etc.).
* **`extra="ignore"`**: By default Pydantic forbids unknown keys (`extra="forbid"`). If someone runs tests from a shell that has extra environment variables (like `COMPANY_EMAIL_DOMAIN` or IDE variables), `extra="ignore"` prevents unrelated keys from crashing `Settings()`.

---

## Topic 10: Testing FastAPI Applications (`TestClient` & `dependency_overrides`)

**Subtopics in this section:**
- 10.1 How `TestClient` Calls Your App Without Opening a Real Network Port
- 10.2 Understanding `app.dependency_overrides`
- 10.3 Real Project Pattern 1: Swapping PostgreSQL for In-Memory SQLite (`get_db`)
- 10.4 Real Project Pattern 2: Capturing OTP Emails & Faking Other Microservices
- 10.5 Real Project Pattern 3: Time-Travel Testing Using `get_now` Override

### 10.1 How `TestClient` Calls Your App Without Opening a Real Network Port
* **`TestClient`** (`from fastapi.testclient import TestClient`): Wraps your FastAPI `app` in an `httpx` client that routes HTTP calls directly through FastAPI's ASGI interface in memory.
* **Benefit**: You get real HTTP status codes, real header parsing, real Pydantic validation, real `Depends` resolution, and real exception handlers in milliseconds—without running Uvicorn on port `8001`–`8004`.

```python
client = TestClient(app)
resp = client.post("/api/v1/auth/company/send-code", json={"email": "outsider@gmail.com"})
assert resp.status_code == 403
assert resp.json()["error"]["code"] == "CORPORATE_EMAIL_REQUIRED"
```

### 10.2 Understanding `app.dependency_overrides`
`app.dependency_overrides` is a built-in dictionary on every `FastAPI` object:
```text
Key   = the original dependency function (e.g., get_db)
Value = your replacement test function (e.g., override_get_db)
```
Whenever FastAPI sees `Depends(get_db)` anywhere in your routes or nested dependencies, it checks `app.dependency_overrides` first and calls the replacement instead!

Always reset it when your test finishes:
```python
app.dependency_overrides.clear()
```

### 10.3 Real Project Pattern 1: Swapping PostgreSQL for In-Memory SQLite (`get_db`)
From `services/parking-service/tests/test_parking.py`:

```python
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=engine)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
```
* **`StaticPool` + `check_same_thread=False`**: Important SQLite trick! Normally an in-memory SQLite DB vanishes when a connection closes or errors when accessed from `TestClient`'s worker thread. `StaticPool` keeps one shared in-memory DB alive across every request inside the test.

### 10.4 Real Project Pattern 2: Capturing OTP Emails & Faking Other Microservices
* **Fake / Test Double**: A lightweight test replacement class that mimics the real dependency's methods without calling external networks.

In `services/user-auth-service/tests/test_auth.py`, `CapturingEmailSender` stores sent OTPs in a list (`self.sent`) so the test can read the generated 6-digit OTP and pass it to `/verify`:
```python
app.dependency_overrides[get_email_sender] = lambda: email_sender
```

In `services/parking-service/tests/test_parking.py`, `FakeVehicleClient` and `FakePaymentClient` replace real `httpx` calls so `parking-service` unit tests don't depend on `:8002` or `:8004` being online:
```python
app.dependency_overrides[get_vehicle_client] = lambda: vehicle_client
app.dependency_overrides[get_payment_client] = lambda: payment_client
```

### 10.5 Real Project Pattern 3: Time-Travel Testing Using `get_now` Override
In `services/parking-service/tests/test_internal.py`, testing a 5-minute hold expiration does **not** wait 5 real minutes! Instead, a mutable dictionary `clock` controls `get_now`:

```python
clock = {"now": datetime(2026, 11, 23, 9, 0, 0, tzinfo=IST_FALLBACK)}
app.dependency_overrides[get_now] = lambda: clock["now"]

# Later inside the test, fast-forward time by 10 minutes instantaneously:
ctx["clock"]["now"] += timedelta(minutes=10)
```
When the next request hits `apply_payment_result` or `list_bookings`, FastAPI injects `clock["now"]` (`09:10 IST`) via `Depends(get_now)`, letting us deterministically test `EXPIRED` and `EXPIRED_NO_RESURRECTION` in under 1 millisecond!

---

## Topic 11: Browser Integration (`CORSMiddleware`)

**Subtopics in this section:**
- 11.1 What is CORS (Cross-Origin Resource Sharing)?
- 11.2 Enabling `CORSMiddleware` When Connecting a Frontend UI

### 11.1 What is CORS (Cross-Origin Resource Sharing)?
* **Origin**: The combination of `protocol + domain + port` (e.g., `http://localhost:3000` is a different origin from `http://127.0.0.1:8001`).
* **CORS (Cross-Origin Resource Sharing)**: A browser security rule (**Same-Origin Policy**) blocks JavaScript running on `http://localhost:3000` (React/Angular/Vue) from calling an API on `http://127.0.0.1:8001` unless the API explicitly responds with `Access-Control-Allow-Origin` headers permitting it.
* **Why isn't `CORSMiddleware` in `ParkingSimplified` right now?** Because `ParkingSimplified` is currently a **pure backend API** tested via Swagger UI (same origin `:8001`/docs $\rightarrow$ `:8001`), `curl`, PowerShell, and `pytest`—browsers only enforce CORS on cross-origin frontend JavaScript!

### 11.2 Enabling `CORSMiddleware` When Connecting a Frontend UI
The moment you build a React/Angular/Next.js UI on e.g. `http://localhost:3000`, you add 6 lines to `app/main.py` in each service:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URLs allowed to call this API
    allow_credentials=True,
    allow_methods=["*"],                      # GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],                      # Authorization, Content-Type, etc.
)
```
* Never use `allow_origins=["*"]` with `allow_credentials=True` in production—always whitelist the exact frontend domain!
