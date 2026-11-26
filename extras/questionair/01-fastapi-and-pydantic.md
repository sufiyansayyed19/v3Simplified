# Questionnaire 01: FastAPI & Pydantic

> **Scope:** Covers FastAPI architecture, ASGI/Uvicorn, `lifespan`, `APIRouter`, request/response handling, Pydantic v2 schemas, `Depends` + `yield`, `HTTPBearer`, custom `AppError` JSON envelopes, `BaseSettings`, `TestClient`, and production add-ons (`BackgroundTasks`, Middleware, CORS).  
> **How to use:** Try answering all questions in a level before scrolling down to that level's **Answer Key**.

---

## Level 1: Core Fundamentals (Warm-Up)

**Q1.** What is the difference between **WSGI** and **ASGI**, and why does FastAPI need **Uvicorn** to run?  
**Q2.** Every route in `ParkingSimplified` uses Python type hints like `vehicle_id: uuid.UUID` or `payload: BookingCreateRequest`. Name the **4 things** FastAPI does automatically from those type hints.  
**Q3.** What is the difference between a **SQLAlchemy Model** (`app/models/*.py`) and a **Pydantic Schema / DTO** (`app/schemas/*.py`)? Why don't we return the SQLAlchemy `User` or `VerificationCode` object raw without a schema?  
**Q4.** Why do our routes use `APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])` instead of putting every `@app.get` and `@app.post` directly inside `app/main.py`?  
**Q5.** What does `--reload` do when running `uvicorn app.main:app --port 8001 --reload`, and should it ever be enabled in production?  

### Level 1 — Answer Key

* **A1.** **WSGI** (used by Flask/classic Django) is synchronous-only—each worker handles one blocking call at a time. **ASGI** supports both asynchronous (`async def`) and synchronous (`def`) handlers plus startup/shutdown **lifespan** events. FastAPI only defines Python routes and rules; **Uvicorn** is the ASGI web server that opens the TCP socket (e.g., `127.0.0.1:8001`), reads raw HTTP bytes, and passes requests into FastAPI.
* **A2.** FastAPI uses the type hint to: (1) extract/parse the input from URL/query/header/JSON body, (2) validate constraints, (3) convert JSON strings into native Python objects (`uuid.UUID`, `date`, `time`, `Decimal`), and (4) generate live OpenAPI/Swagger UI schemas (`/docs`).
* **A3.** **Models** define PostgreSQL tables and columns (`users`, `verification_codes`). **Schemas (DTOs)** define the public API input/output contract. Keeping them separate ensures internal DB fields (like `VerificationCode.code_hash`, `consumed_at`, or internal timestamps) are never accidentally exposed in JSON responses.
* **A4.** `APIRouter` modularizes routes by domain (`auth.py`, `vehicles.py`, `parking.py`, `internal.py`, `payments.py`), cleanly applies shared URL prefixes (`/api/v1/...`), groups Swagger UI endpoints via `tags`, and supports side-by-side API versioning (`v1` vs future `v2`).
* **A5.** `--reload` watches `.py` files and automatically restarts the Uvicorn worker whenever code changes are saved. It must **never** be used in production because file-watching wastes CPU/memory and causes dropped requests during restarts.

---

## Level 2: Project Implementation (`ParkingSimplified` Codebase)

**Q6.** In `services/vehicle-service/app/schemas/vehicle.py`, `VehicleResponse` has `model_config = ConfigDict(from_attributes=True)`. Why is that single line necessary?  
**Q7.** Look at `services/parking-service/app/api/v1/parking.py`:
```python
booking_date: date = Query(alias="date"),
start_time: time = Query(...),
page: int = Query(default=1, ge=1),
page_size: int = Query(default=20, ge=1, le=100),
```
Explain what `alias="date"`, the `...` (Ellipsis), and `ge=1, le=100` each do.  
**Q8.** Why do `POST /api/v1/vehicles` and `POST /api/v1/parking/bookings` use `@router.post("", ...)` (empty string `""`) instead of `@router.post("/", ...)` when `prefix` is already set?  
**Q9.** How does `get_db()` in `app/core/database.py` use `yield` to guarantee there are no leaked PostgreSQL connections, even when an endpoint raises an exception?  
**Q10.** Look at `services/user-auth-service/app/core/config.py` and `parking-service/app/core/config.py`: why is `extra="ignore"` included in `SettingsConfigDict(env_file=".env", ..., extra="ignore")`?  
**Q11.** In `services/vehicle-service/app/schemas/vehicle.py`, if a user sends `"vehicle_number": " ka-01 ab 1234 "`, what exact value reaches `create_vehicle()` in `vehicles.py`, and how did that happen before the route body ran?  

### Level 2 — Answer Key

* **A6.** By default, Pydantic expects a Python `dict` (`obj["id"]`). SQLAlchemy queries return ORM model instances whose fields are attributes (`vehicle.id`, `vehicle.vehicle_number`). Setting `from_attributes=True` tells Pydantic to read attributes using dot notation when running `VehicleResponse.model_validate(vehicle)`.
* **A7.**
  - `alias="date"` lets the HTTP URL use `?date=2026-11-26` while keeping the Python variable named `booking_date` (avoiding collision with `from datetime import date`).
  - `...` (`Ellipsis`) marks `start_time` as **required** with no default.
  - `ge=1, le=100` validates pagination bounds ($1 \le \text{page\_size} \le 100$), blocking huge queries like `?page_size=999999` with `422`.
* **A8.** With `prefix="/api/v1/vehicles"`, `@router.post("")` registers the exact path `/api/v1/vehicles`. Using `"/"` would register `/api/v1/vehicles/`, causing FastAPI to emit `307 Temporary Redirect` responses if clients call `/api/v1/vehicles` without a trailing slash.
* **A9.** `get_db()` runs `db = SessionLocal()`, then `yield db` hands the session to the route inside a `try` block. Once the route finishes—**or even if it raises `AppError`**—FastAPI resumes `get_db()` and always executes `finally: db.close()`, returning the connection safely to the pool.
* **A10.** By default, Pydantic rejects unknown keys (`extra="forbid"`). With `extra="ignore"`, if the host OS shell or a shared test environment sets variables meant for *other* services (such as `COMPANY_EMAIL_DOMAIN` when running `parking-service`), `Settings()` ignores them instead of crashing at startup.
* **A11.** `create_vehicle()` receives `"KA01AB1234"`. Before entering the route body, Pydantic validates `VehicleCreate`, triggering `@field_validator("vehicle_number")` $\rightarrow$ `normalize_vehicle_number()`, which strips spaces/hyphens, uppercases the string, and checks `^[A-Z0-9]{4,20}$`.

---

## Level 3: Deep "Why" & Architect-Level Questions

**Q12.** Every route handler in `ParkingSimplified` is declared with plain **`def`** instead of **`async def`**. An architect asks: *"Isn't FastAPI famous for `async`? Why didn't you write `async def` on your endpoints?"* How do you answer?  
**Q13.** Look at `lifespan` in `services/parking-service/app/main.py`:
```python
if get_db not in app_instance.dependency_overrides:
    Base.metadata.create_all(bind=engine)
```
Why does `lifespan` check `dependency_overrides`, and why do `user-auth-service`, `vehicle-service`, and `payment-service` have `import app.models  # noqa: F401` right at the top of `main.py`?  
**Q14.** Why did we configure `bearer_scheme = HTTPBearer(auto_error=False)` instead of leaving `auto_error=True` (the default)?  
**Q15.** In `services/payment-service/app/api/v1/payments.py`, `create_internal_payment` declares `status_code=status.HTTP_201_CREATED` in its decorator, yet returns `200 OK` on an idempotent retry. How does FastAPI allow returning two different 2xx status codes from one function?  
**Q16.** Why did we register custom exception handlers (`RequestValidationError`, `AppError`, `HTTPException`, `Exception`) in `app/core/errors.py` instead of using FastAPI's built-in `HTTPException` everywhere?  
**Q17.** In `services/parking-service/app/api/internal.py`, `_require_internal_token` is attached via `dependencies=[Depends(_require_internal_token)]` in the `@router.post(...)` decorator rather than as a function parameter. When should you put `Depends(...)` in the decorator vs. the function signature?  
**Q18.** Why did we inject `now: datetime = Depends(get_now)` in `parking.py` instead of calling `datetime.now()` inside the function body?  

### Level 3 — Answer Key

* **A12.** Because our database driver (`psycopg` sync `Session`) and HTTP client (`httpx.Client`) are **synchronous/blocking**. If you put blocking I/O inside `async def`, it freezes Python's single-threaded `asyncio` event loop for *all* concurrent users! With plain `def`, FastAPI automatically dispatches each request to an AnyIO worker threadpool safely. You should switch routes to `async def` only when migrating the whole stack to async drivers (`asyncpg` / `AsyncSession` + `httpx.AsyncClient`).
* **A13.**
  - **Guard check:** When unit tests run `TestClient(app)` with `app.dependency_overrides[get_db] = sqlite_override`, skipping `create_all(bind=engine)` stops `lifespan` from trying to connect to a live PostgreSQL server during offline unit tests.
  - **`import app.models`:** SQLAlchemy only registers tables on `Base.metadata` once their Python class files are imported. Without importing `app.models`, `create_all()` would see an empty `Base.metadata` and create zero tables.
* **A14.** With `auto_error=True`, FastAPI/Starlette automatically intercepts missing `Authorization` headers and returns `403 {"detail": "Not authenticated"}`. With `auto_error=False`, FastAPI passes `credentials = None` into `get_current_user_id()`, allowing us to return `401 UNAUTHENTICATED` inside our consistent JSON error envelope.
* **A15.** By injecting FastAPI's `response: Response` parameter into the route function and setting `response.status_code = status.HTTP_200_OK` dynamically before returning the Pydantic model when an existing matching `Payment` row is found.
* **A16.** Raw FastAPI mixes three incompatible error JSON shapes (`{"detail": "..."}`, Pydantic's `{"detail": [...]}`, and plain-text `500`s). Registering global `@app.exception_handler` handlers enforces one contract (`{"error": {"code", "message", "request_id"}}`) across all 4 services, lets business rules in `rules.py`/`clients.py` raise `AppError` cleanly, overrides `422` validation formatting, and prevents stack-trace leaks on unhandled `500` errors.
* **A17.** Put `Depends(...)` in the function signature when the route needs the returned object (`db`, `auth`, `now`). Put it in `dependencies=[Depends(...)]` in the route decorator when it is purely a validation/security gate that returns `None` (`_require_internal_token`), keeping the handler's parameter list clean.
* **A18.** Injecting time via `Depends(get_now)` lets tests override `app.dependency_overrides[get_now]` to test operating hours (`07:00–22:00`), Sunday closures, and 5-minute hold expiry (`clock["now"] += timedelta(minutes=10)`) instantaneously and deterministically without `time.sleep()`.

---

## Level 4: Scenarios, Debugging & Beyond `ParkingSimplified`

**Q19. Debugging Scenario:** In `vehicle-service`, a test calls `PUT /api/v1/vehicles/{id}` with `"vehicle_type": "TRUCK"`. Where is this rejected, what HTTP status code is returned, and what `error.code` appears in the JSON body?  
**Q20. Architecture Scenario:** In `parking-service/app/core/errors.py`, `_request_id(request)` checks `getattr(request.state, "request_id", str(uuid.uuid4()))`. Right now, nothing populates `request.state.request_id`. How would you populate it globally for *every* incoming request (both successes and errors) across a service?  
**Q21. Trade-Off Scenario:** Right now `send_company_code()` calls `email_sender.send_otp(...)` synchronously before returning `200 OK`, and `process_payment()` calls `callback_client.deliver_payment_result(...)` synchronously before returning `200 OK`. If you upgraded email sending to a slow 2-second SMTP server, which FastAPI feature could offload it? And why should you be careful using that same feature for payment callbacks?  
**Q22. Frontend Scenario:** You build a React UI running on `http://localhost:3000` and try calling `http://127.0.0.1:8001/api/v1/auth/company/send-code` from Chrome, and Chrome blocks it—even though Swagger UI and `pytest` worked fine. Why did that happen, and how do you fix it in FastAPI?  

### Level 4 — Answer Key

* **A19.** Because `VehicleType = Literal["CAR", "BIKE"]` in `schemas/vehicle.py`, Pydantic fails validation before `update_vehicle()` runs and raises `RequestValidationError`. The handler in `services/vehicle-service/app/core/errors.py` catches it and returns **HTTP `422`** with `"code": "INVALID_VEHICLE_DATA"`.
* **A20.** Add an HTTP middleware using `@app.middleware("http")` in `app/main.py` that reads an incoming `X-Request-ID` header (or generates `str(uuid.uuid4())`), sets `request.state.request_id = request_id`, awaits `call_next(request)`, and attaches `X-Request-ID` on the outgoing response headers.
* **A21.** FastAPI's **`BackgroundTasks`** (`background_tasks.add_task(...)`) lets `send_company_code()` return `200 OK` immediately and send the SMTP email right after the response flushes. However, `BackgroundTasks` runs in-memory inside the same worker process—if the server crashes or restarts mid-task, the task is lost! For critical financial state transitions like payment callbacks, you either keep them synchronous (so confirmation happens before returning) or use a durable message queue / Outbox table.
* **A22.** Browsers enforce the **Same-Origin Policy** (`localhost:3000` $\neq$ `127.0.0.1:8001`), blocking cross-origin JavaScript requests unless the backend returns CORS headers (`Swagger UI` worked because it was served from `:8001` itself, same origin!). Fix it by adding **`CORSMiddleware`** (`app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`) in each service's `app/main.py`.
