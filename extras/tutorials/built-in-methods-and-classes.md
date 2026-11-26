# Built-In & Library Methods Reference Tutorial — Used Directly in `ParkingSimplified`

> **Who is this for?** This tutorial is designed for freshers and learners preparing for project evaluations. It covers **only the built-in Python and third-party library classes, functions, decorators, and methods** that we import and call directly in `ParkingSimplified` (not our own custom helper functions).
> 
> **How each method is explained:**
> 1. 🌟 **What is it in simple words?** (Everyday analogy & plain English).
> 2. 🎯 **What problem does it solve in our project?** (Why we need it).
> 3. 💻 **Real Code Snippet** (Directly from the `ParkingSimplified` codebase).

---

## Course Outline (All Root Topics & Subtopics)

1. **Topic 1: Root / App-Bootstrap Level (`app/main.py` & `app/core/errors.py`)**
   - 1.1 `FastAPI(...)` & `@app.get(...)`
   - 1.2 `@asynccontextmanager` (`contextlib`)
   - 1.3 `app.include_router(...)` & `app.dependency_overrides`
   - 1.4 `@app.exception_handler(...)`, `RequestValidationError`, `HTTPException` & `JSONResponse`
2. **Topic 2: Common Service & Core Infrastructure (`config.py`, `security.py`, `clients.py`)**
   - 2.1 `BaseSettings` & `SettingsConfigDict` (`pydantic_settings`)
   - 2.2 `APIRouter(...)`
   - 2.3 `Depends(...)`, `Query(...)`, `Header(...)`, `Response`, `status`
   - 2.4 `HTTPBearer(...)` & `HTTPAuthorizationCredentials`
   - 2.5 `jwt.encode(...)`, `jwt.decode(...)` & `jwt.PyJWTError`
   - 2.6 `httpx.Client(...)` & `httpx.HTTPError`
3. **Topic 3: Schema Validation & Serialization (`app/schemas/*.py`)**
   - 3.1 `BaseModel` & `ConfigDict(from_attributes=True)`
   - 3.2 `Field(...)`, `EmailStr` & `Literal[...]`
   - 3.3 `@field_validator(...)` & `model_validate(...)`
4. **Topic 4: Database, SQLAlchemy 2.0 & Alembic (`database.py`, `models/*.py`, `api/*.py`, `alembic/`)**
   - 4.1 `create_engine(...)`, `sessionmaker(...)`, `DeclarativeBase` (`Base`) & `Session`
   - 4.2 `Mapped[...]`, `mapped_column(...)`, `UUID(as_uuid=True)`, `ForeignKey(...)`, `relationship(...)`
   - 4.3 `select(...)`, `delete(...)`, `func.count(...)`, `desc(...)`, `and_(...)`, `or_(...)`
   - 4.4 `joinedload(...)`, `with_for_update()` & `Base.metadata.create_all(...)`
   - 4.5 Session Execution Methods (`db.execute`, `db.get`, `db.add`, `db.add_all`, `db.commit`, `db.refresh`, `db.close`)
   - 4.6 Result Extractors (`scalar_one`, `scalar_one_or_none`, `scalars().all()`)
   - 4.7 Alembic Built-ins (`engine_from_config`, `pool.NullPool`, `context.*`, `op.*`, `sa.text`)
5. **Topic 5: Python Standard Library Built-ins Used Directly**
   - 5.1 Security & Identifiers (`uuid.uuid4`, `uuid.UUID`, `.hex`, `secrets.randbelow`)
   - 5.2 Dates, Timezones & Exact Money (`datetime.now`, `datetime.combine`, `timedelta`, `timezone.utc`, `ZoneInfo`, `Decimal`)
   - 5.3 OOP, Regex & Typing Helpers (`ABC`, `@abstractmethod`, `@dataclass`, `re.compile`, `re.sub`, `Generator`)
6. **Topic 6: Testing & Concurrency Built-ins (`tests/` & `services/*/tests/`)**
   - 6.1 `TestClient(...)` & `@pytest.fixture()`
   - 6.2 `StaticPool` (`sqlalchemy.pool`)
   - 6.3 `threading.Barrier`, `ThreadPoolExecutor` & `subprocess.Popen`

---

## Topic 1: Root / App-Bootstrap Level (`app/main.py` & `app/core/errors.py`)

**Subtopics in this section:**
- 1.1 `FastAPI(...)` & `@app.get(...)`
- 1.2 `@asynccontextmanager` (`contextlib`)
- 1.3 `app.include_router(...)` & `app.dependency_overrides`
- 1.4 `@app.exception_handler(...)`, `RequestValidationError`, `HTTPException` & `JSONResponse`

---

### 1.1 `FastAPI(...)` & `@app.get(...)`

#### `FastAPI(...)` (`from fastapi import FastAPI`)
* 🌟 **What is it in simple words?**
  Think of `FastAPI` as the **front desk manager of your microservice**. Whenever an HTTP request arrives from the outside world (like a browser, Postman, or mobile app), `FastAPI` greets it, looks at where it wants to go, validates the inputs, and directs it to the right function. It also automatically generates a beautiful, interactive instruction manual at `/docs` (Swagger UI)!
* 🎯 **What problem does it solve in our project?**
  Instead of writing hundreds of lines of low-level networking code to parse HTTP sockets and URL paths, `FastAPI` sets up a complete, production-ready REST API in 1 line of code. Each of our 4 microservices creates its own `FastAPI` instance.
* 💻 **Real Code Snippet (`services/parking/app/main.py`):**
  ```python
  from fastapi import FastAPI

  app = FastAPI(
      title="Corporate Parking — Parking Service",
      version="1.0.0",
      lifespan=lifespan,
  )
  ```

#### `@app.get(...)`
* 🌟 **What is it in simple words?**
  Think of `@app.get` like putting a sign on an office door: *"When someone knocks with an HTTP GET request at `/health`, open this door and run this function"*.
* 🎯 **What problem does it solve in our project?**
  It maps a specific URL path and HTTP verb (`GET`) directly to a Python function. We use it on the root `app` for the `/health` endpoint so monitoring tools or Docker can check if our service is healthy.
* 💻 **Real Code Snippet (`services/parking/app/main.py`):**
  ```python
  @app.get("/health", tags=["health"])
  def health_check():
      # When someone visits GET /health, return this JSON status
      return {"status": "ok", "service": settings.SERVICE_NAME}
  ```

---

### 1.2 `@asynccontextmanager` (`contextlib`)

#### `@asynccontextmanager` (`from contextlib import asynccontextmanager`)
* 🌟 **What is it in simple words?**
  Think of this like **opening and closing a shop**:
  - In the morning before customers arrive, you unlock the doors and turn on the lights (Startup).
  - During the day, customers shop (`yield`).
  - At night when the shop closes, you turn off the lights and lock the doors (Shutdown).
* 🎯 **What problem does it solve in our project?**
  FastAPI uses this decorator for the `lifespan` parameter. It guarantees that our database tables are created *before* the server starts accepting any HTTP requests. The code before `yield` runs at server boot; the code after `yield` runs when the server stops.
* 💻 **Real Code Snippet (`services/parking/app/main.py`):**
  ```python
  from contextlib import asynccontextmanager
  from fastapi import FastAPI

  @asynccontextmanager
  async def lifespan(app_instance: FastAPI):
      # --- STARTUP PHASE ---
      # Create database tables automatically before handling user traffic
      if get_db not in app_instance.dependency_overrides:
          Base.metadata.create_all(bind=engine)
      
      yield  # --- RUNNING PHASE (server is now live and accepting requests) ---
      
      # --- SHUTDOWN PHASE ---
      # (Any cleanup code like closing connections would run here)
  ```

---

### 1.3 `app.include_router(...)` & `app.dependency_overrides`

#### `app.include_router(...)`
* 🌟 **What is it in simple words?**
  Think of an **extension power strip** or adding new wings to a building. Instead of stuffing 50 different API endpoints into one giant messy `main.py` file, we group related endpoints into separate files (called "routers"). `app.include_router` plugs those modular router files into the main app.
* 🎯 **What problem does it solve in our project?**
  Keeps our project clean and modular. For example, in the Parking service, public customer routes (`/api/v1/slots`, `/api/v1/bookings`) live in one file, while internal service-to-service routes (`/internal/v1/holds`) live in another file. `main.py` just plugs them in!
* 💻 **Real Code Snippet (`services/parking/app/main.py`):**
  ```python
  from app.api.parking import router as parking_router
  from app.api.internal import router as internal_router

  # Plug modular route groups into the root application
  app.include_router(parking_router)
  app.include_router(internal_router)
  ```

#### `app.dependency_overrides`
* 🌟 **What is it in simple words?**
  Think of a **movie stunt double**! In a movie, a famous actor does the speaking, but for a dangerous stunt, a stunt double steps in. In testing, we don't want tests touching our real PostgreSQL database or calling real external services. `app.dependency_overrides` tells FastAPI: *"Whenever any route asks for the real database `get_db`, give it my fake in-memory SQLite database instead!"*
* 🎯 **What problem does it solve in our project?**
  It allows our automated tests (`pytest`) to run in milliseconds without needing a running PostgreSQL instance or external network access, and without changing a single line of production code!
* 💻 **Real Code Snippet (`services/parking/tests/conftest.py`):**
  ```python
  # Swap the real PostgreSQL connection with an in-memory SQLite connection for testing:
  app.dependency_overrides[get_db] = override_get_db

  # Swap the real external vehicle HTTP client with a fake in-memory client:
  app.dependency_overrides[get_vehicle_client] = lambda: FakeVehicleClient()
  ```

---

### 1.4 `@app.exception_handler(...)`, `RequestValidationError`, `HTTPException` & `JSONResponse`

#### `@app.exception_handler(...)`
* 🌟 **What is it in simple words?**
  Think of a **safety net or a specialized hospital emergency team**. Whenever an error happens anywhere in your app, instead of letting Python crash and show an ugly internal error traceback to the user, this decorator catches the error and turns it into a polite, predictable JSON response.
* 🎯 **What problem does it solve in our project?**
  It enforces a unified JSON error format across all 4 microservices. The frontend mobile app or web client always receives `{ "error": { "code": "...", "message": "..." } }`.
* 💻 **Real Code Snippet (`services/common/app/core/errors.py`):**
  ```python
  @app.exception_handler(AppError)
  async def app_error_handler(request: Request, exc: AppError):
      return JSONResponse(
          status_code=exc.status_code,
          content={"error": {"code": exc.code, "message": exc.message}},
      )
  ```

#### `RequestValidationError` (`from fastapi.exceptions import RequestValidationError`)
* 🌟 **What is it in simple words?**
  Think of a **security guard checking tickets at the entrance**. If a user sends bad data (e.g., forgets their email, sends `"abc"` instead of an integer price, or sends an invalid date), FastAPI automatically blows the whistle and raises `RequestValidationError`.
* 🎯 **What problem does it solve in our project?**
  We catch this error globally and convert FastAPI's verbose internal validation messages into our project's standardized `422 Unprocessable Entity` error format.
* 💻 **Real Code Snippet (`services/common/app/core/errors.py`):**
  ```python
  @app.exception_handler(RequestValidationError)
  async def validation_error_handler(request: Request, exc: RequestValidationError):
      return JSONResponse(
          status_code=422,
          content={
              "error": {
                  "code": "VALIDATION_ERROR",
                  "message": "Invalid request parameters",
                  "details": exc.errors(),  # Lists exactly which fields were wrong
              }
          },
      )
  ```

#### `HTTPException` (`from fastapi import HTTPException`)
* 🌟 **What is it in simple words?**
  The standard way in FastAPI to **immediately stop executing and return an HTTP error** (like 404 Not Found, 401 Unauthorized, or 403 Forbidden).
* 🎯 **What problem does it solve in our project?**
  All our custom application errors (`AppError`, `NotFoundError`, `ConflictError`, `UnauthorizedError`) inherit from `HTTPException` so FastAPI understands their HTTP status code natively.
* 💻 **Real Code Snippet (`services/common/app/core/errors.py`):**
  ```python
  class NotFoundError(AppError):
      def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
          # Calls HTTPException's constructor with status_code=404
          super().__init__(status_code=404, message=message, code=code)
  ```

#### `JSONResponse` (`from fastapi.responses import JSONResponse`)
* 🌟 **What is it in simple words?**
  A helper class that takes a plain Python dictionary, formats it as valid JSON text, sets the `Content-Type: application/json` header, and attaches the specific HTTP status code you specify.
* 🎯 **What problem does it solve in our project?**
  Inside custom exception handlers, FastAPI expects you to return an explicit response object. `JSONResponse(status_code=..., content=...)` lets us build the exact response sent back to the client.
* 💻 **Real Code Snippet (`services/common/app/core/errors.py`):**
  ```python
  return JSONResponse(
      status_code=400,
      content={"error": {"code": "BAD_REQUEST", "message": "Invalid input"}},
  )
  ```

---

## Topic 2: Common Service & Core Infrastructure (`config.py`, `security.py`, `clients.py`)

**Subtopics in this section:**
- 2.1 `BaseSettings` & `SettingsConfigDict` (`pydantic_settings`)
- 2.2 `APIRouter(...)`
- 2.3 `Depends(...)`, `Query(...)`, `Header(...)`, `Response`, `status`
- 2.4 `HTTPBearer(...)` & `HTTPAuthorizationCredentials`
- 2.5 `jwt.encode(...)`, `jwt.decode(...)` & `jwt.PyJWTError`
- 2.6 `httpx.Client(...)` & `httpx.HTTPError`

---

### 2.1 `BaseSettings` & `SettingsConfigDict` (`pydantic_settings`)

#### `BaseSettings`
* 🌟 **What is it in simple words?**
  Think of an **intelligent assistant that reads your configuration files**. Instead of manually writing `os.getenv("PORT")` and converting strings to numbers with `int(os.getenv("PORT"))`, `BaseSettings` reads your `.env` file or environment variables automatically, checks the data types, and gives you clean, autocompleted Python attributes!
* 🎯 **What problem does it solve in our project?**
  Centralizes database URLs, secret keys, and microservice ports. If someone configures `PORT="abc"`, `BaseSettings` crashes immediately on startup with a helpful error instead of failing mysteriously during runtime.
* 💻 **Real Code Snippet (`services/parking/app/config.py`):**
  ```python
  from pydantic_settings import BaseSettings, SettingsConfigDict

  class Settings(BaseSettings):
      SERVICE_NAME: str = "parking-service"
      PORT: int = 8003
      DATABASE_URL: str = "postgresql://parking_user:parking_pass@localhost:5432/parking_db"
      JWT_SECRET_KEY: str = "dev-secret-key-change-in-prod"
      JWT_ALGORITHM: str = "HS256"

      model_config = SettingsConfigDict(env_file=".env", extra="ignore")

  settings = Settings()
  ```

#### `SettingsConfigDict`
* 🌟 **What is it in simple words?**
  The configuration settings for `BaseSettings` itself. It tells Pydantic: *"Where should you look for the `.env` file, and what should you do if there are extra variables you don't recognize?"*.
* 🎯 **What problem does it solve in our project?**
  All 4 microservices share one common `.env` file in the project root. If the Parking service didn't have `extra="ignore"`, it would crash complaining that `PAYMENT_GATEWAY_URL` exists in `.env` (which belongs to the Payment service, not Parking)!
* 💻 **Real Code Snippet (`services/parking/app/config.py`):**
  ```python
  model_config = SettingsConfigDict(
      env_file=".env",
      env_file_encoding="utf-8",
      extra="ignore",  # Don't crash if other services have variables in .env!
  )
  ```

---

### 2.2 `APIRouter(...)`

#### `APIRouter` (`from fastapi import APIRouter`)
* 🌟 **What is it in simple words?**
  Think of a **department manager**. If `FastAPI` is the entire company building, `APIRouter` is a specific department (like the "Vehicle Department" or "Billing Department"). It groups related endpoints together under a shared URL prefix (e.g., `/api/v1/vehicles`).
* 🎯 **What problem does it solve in our project?**
  Prevents monolithic code. Each business domain (`parking.py`, `vehicle.py`, `auth.py`, `payment.py`) writes its routes on its own `router`, and `main.py` simply connects them.
* 💻 **Real Code Snippet (`services/vehicle/app/api/vehicle.py`):**
  ```python
  from fastapi import APIRouter

  # All routes in this file will automatically start with /api/v1/vehicles
  router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])

  @router.post("", response_model=VehicleResponse)
  def register_vehicle(...):
      ...
  ```

---

### 2.3 `Depends(...)`, `Query(...)`, `Header(...)`, `Response`, `status`

#### `Depends(...)` (`from fastapi import Depends`)
* 🌟 **What is it in simple words?**
  Think of a **surgical assistant who prepares tools before an operation**. Before your route function starts, FastAPI sees `Depends(get_db)` and says: *"Wait! Let me open a fresh database connection, hand it to your function as `db`, and once your function finishes, I'll close the connection automatically!"*.
* 🎯 **What problem does it solve in our project?**
  Eliminates repetitive boilerplate for opening/closing database connections (`db: Session = Depends(get_db)`) and authenticating users (`current_user = Depends(get_current_user)`).
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  @router.get("/slots")
  def list_slots(
      db: Session = Depends(get_db),                       # Database session injected!
      current_user: AuthContext = Depends(get_current_user) # Authenticated user injected!
  ):
      ...
  ```

#### `Query(...)` (`from fastapi import Query`)
* 🌟 **What is it in simple words?**
  Reads and validates parameters passed in the URL query string (the part after the `?` in `https://api.com/slots?date=2026-11-26&type=CAR`).
* 🎯 **What problem does it solve in our project?**
  Validates search filters and pagination parameters. In our project, `date` is a Python keyword, so we use `alias="date"` to accept `?date=...` while naming our Python variable `booking_date`.
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  @router.get("/slots")
  def get_available_slots(
      # Reads ?date=2026-11-26 from the URL and parses it as a python date object:
      booking_date: date = Query(alias="date", description="Target booking date"),
      vehicle_type: str | None = Query(default=None, alias="type"),
  ):
      ...
  ```

#### `Header(...)` (`from fastapi import Header`)
* 🌟 **What is it in simple words?**
  Reads hidden metadata sent in HTTP request headers (like `X-Internal-Service-Token: my-secret-token`).
* 🎯 **What problem does it solve in our project?**
  Used for **internal microservice-to-microservice authentication**. When the Parking service calls the Payment service internally, it sends a secret token in this header to prove it is an authorized internal service, not an outside attacker.
* 💻 **Real Code Snippet (`services/parking/app/api/internal.py`):**
  ```python
  def verify_internal_token(
      token: str | None = Header(default=None, alias="X-Internal-Service-Token")
  ):
      if token != settings.INTERNAL_SERVICE_TOKEN:
          raise HTTPException(status_code=403, detail="Forbidden internal access")
  ```

#### `Response` (`from fastapi import Response`)
* 🌟 **What is it in simple words?**
  The outgoing HTTP envelope. If you need to manually change the HTTP status code or set custom response headers inside your function, you inject `Response`.
* 🎯 **What problem does it solve in our project?**
  Allows dynamic status codes (e.g. returning `200 OK` if a resource already existed or `201 Created` if newly created).
* 💻 **Real Code Snippet:**
  ```python
  @router.post("/sync")
  def sync_data(response: Response):
      response.headers["X-Server-Time"] = "2026-11-26T12:00:00Z"
      return {"synced": True}
  ```

#### `status` (`from fastapi import status`)
* 🌟 **What is it in simple words?**
  A dictionary of **human-readable names for HTTP status numbers**. Instead of remembering mystery numbers like `201`, `401`, or `404`, you write `status.HTTP_201_CREATED`, `status.HTTP_401_UNAUTHORIZED`, or `status.HTTP_404_NOT_FOUND`.
* 🎯 **What problem does it solve in our project?**
  Prevents accidental typos with numbers and makes your code self-documenting.
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  @router.post("/bookings", status_code=status.HTTP_201_CREATED)
  def create_booking(...):
      ...
  ```

---

### 2.4 `HTTPBearer(...)` & `HTTPAuthorizationCredentials`

#### `HTTPBearer(...)` (`from fastapi.security import HTTPBearer`)
* 🌟 **What is it in simple words?**
  Think of a **VIP security guard inspecting wristbands at a club entrance**. It looks specifically for the `Authorization: Bearer <token>` header in incoming HTTP requests and extracts the token string.
* 🎯 **What problem does it solve in our project?**
  It integrates with OpenAPI / Swagger UI so a green **"Authorize"** button appears at the top of `/docs`. We pass `auto_error=False` so that if a user forgets to send a token, our custom exception handler catches it and returns our standard JSON format instead of FastAPI's default HTML/text error.
* 💻 **Real Code Snippet (`services/common/app/core/security.py`):**
  ```python
  from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

  # auto_error=False lets us handle missing tokens with our custom UnauthorizedError
  security = HTTPBearer(auto_error=False)
  ```

#### `HTTPAuthorizationCredentials`
* 🌟 **What is it in simple words?**
  The object given to you by `HTTPBearer`. It holds two pieces of information:
  1. `credentials.scheme`: The word `"Bearer"`.
  2. `credentials.credentials`: The actual long encoded JWT string (`"eyJhbGciOiJIUzI1Ni..."`).
* 🎯 **What problem does it solve in our project?**
  Provides type hints and quick access to the raw JWT token.
* 💻 **Real Code Snippet (`services/common/app/core/security.py`):**
  ```python
  def get_current_user(
      credentials: HTTPAuthorizationCredentials | None = Depends(security),
  ) -> AuthContext:
      if not credentials:
          raise UnauthorizedError("Missing authentication token")
      raw_jwt = credentials.credentials  # Extract the token string
      ...
  ```

---

### 2.5 `jwt.encode(...)`, `jwt.decode(...)` & `jwt.PyJWTError`

#### `jwt.encode(...)` (`import jwt`)
* 🌟 **What is it in simple words?**
  Think of **creating a tamper-proof digital ID card with an official wax stamp**. You take the user's data (User ID, email, expiration time) and your secret key, and `jwt.encode` outputs a signed string. If anyone tries to change the User ID inside the token, the stamp breaks and becomes invalid!
* 🎯 **What problem does it solve in our project?**
  When a user logs in with an OTP in the User Auth service, we issue this token. The user presents it in future requests to prove who they are.
* 💻 **Real Code Snippet (`services/user-auth/app/core/security.py`):**
  ```python
  import jwt
  from datetime import datetime, timedelta, timezone

  def create_access_token(user_id: str, email: str) -> str:
      payload = {
          "sub": user_id,
          "email": email,
          "exp": datetime.now(timezone.utc) + timedelta(hours=24),
          "iat": datetime.now(timezone.utc),
      }
      return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
  ```

#### `jwt.decode(...)`
* 🌟 **What is it in simple words?**
  Think of **inspecting the wax stamp on the digital ID card**. It checks the secret key, verifies that nobody modified the token, checks that the token hasn't expired, and returns the original user information!
* 🎯 **What problem does it solve in our project?**
  Enables **Zero-DB Authentication**. The Parking, Vehicle, and Payment services can verify who the user is locally in memory in 0.1 milliseconds without making a database query or calling the User service!
* 💻 **Real Code Snippet (`services/common/app/core/security.py`):**
  ```python
  payload = jwt.decode(
      raw_jwt,
      settings.JWT_SECRET_KEY,
      algorithms=[settings.JWT_ALGORITHM]
  )
  user_id = payload["sub"]
  email = payload["email"]
  ```

#### `jwt.PyJWTError`
* 🌟 **What is it in simple words?**
  The umbrella error that catches **any problem with a JWT**—whether the token has expired, has been tampered with, or is complete gibberish.
* 🎯 **What problem does it solve in our project?**
  Allows us to safely catch all token failures in one `try...except` block and raise our clean `UnauthorizedError("Invalid or expired token")`.
* 💻 **Real Code Snippet (`services/common/app/core/security.py`):**
  ```python
  try:
      payload = jwt.decode(raw_jwt, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
  except jwt.PyJWTError:
      raise UnauthorizedError("Token is invalid or has expired")
  ```

---

### 2.6 `httpx.Client(...)` & `httpx.HTTPError`

#### `httpx.Client(...)` (`import httpx`)
* 🌟 **What is it in simple words?**
  Think of a **web browser inside Python code**. When Service A (like Parking) needs to talk to Service B (like Vehicle or Payment), it uses `httpx.Client` to send an HTTP GET or POST request to Service B.
* 🎯 **What problem does it solve in our project?**
  Because microservices have isolated databases, the Parking service cannot directly read the Vehicle database. Instead, Parking calls `GET /api/v1/vehicles/{id}` over HTTP. We pass `timeout=3.0` so our service never hangs waiting if the other service is slow.
* 💻 **Real Code Snippet (`services/parking/app/clients.py`):**
  ```python
  import httpx

  class VehicleClient:
      def get_vehicle(self, vehicle_id: str, token: str) -> dict:
          headers = {"Authorization": f"Bearer {token}"}
          with httpx.Client(timeout=3.0) as client:
              resp = client.get(f"{self.base_url}/api/v1/vehicles/{vehicle_id}", headers=headers)
              if resp.status_code == 200:
                  return resp.json()
              return None
  ```

#### `httpx.HTTPError`
* 🌟 **What is it in simple words?**
  An alarm that fires when **an HTTP request to another microservice fails** (e.g., connection refused, DNS lookup failed, or the request timed out).
* 🎯 **What problem does it solve in our project?**
  If the Payment service goes down, the Parking service shouldn't crash with a raw Python traceback. We catch `httpx.HTTPError` and return a user-friendly `503 Service Unavailable` error: *"Payment service is temporarily unreachable"*.
* 💻 **Real Code Snippet (`services/parking/app/clients.py`):**
  ```python
  try:
      with httpx.Client(timeout=3.0) as client:
          resp = client.post(f"{self.base_url}/internal/v1/payments", json=payload)
  except httpx.HTTPError:
      raise ServiceUnavailableError("Payment service is temporarily unavailable")
  ```

---

## Topic 3: Schema Validation & Serialization (`app/schemas/*.py`)

**Subtopics in this section:**
- 3.1 `BaseModel` & `ConfigDict(from_attributes=True)`
- 3.2 `Field(...)`, `EmailStr` & `Literal[...]`
- 3.3 `@field_validator(...)` & `model_validate(...)`

---

### 3.1 `BaseModel` & `ConfigDict(from_attributes=True)`

#### `BaseModel` (`from pydantic import BaseModel`)
* 🌟 **What is it in simple words?**
  Think of an **official application form**. You define what boxes must be filled in (like `slot_id`, `vehicle_number`, `booking_date`) and what type of data belongs in each box. If someone submits a form with missing or wrong data, Pydantic rejects it automatically before it ever reaches your database.
* 🎯 **What problem does it solve in our project?**
  Every request payload sent to our API and every response returned to the user is strictly defined and validated using `BaseModel`.
* 💻 **Real Code Snippet (`services/parking/app/schemas/parking.py`):**
  ```python
  from pydantic import BaseModel
  from uuid import UUID
  from datetime import date, time

  class BookingCreate(BaseModel):
      slot_id: UUID
      vehicle_number: str
      booking_date: date
      start_time: time
      end_time: time
  ```

#### `ConfigDict(from_attributes=True)`
* 🌟 **What is it in simple words?**
  A **translator between SQLAlchemy and Pydantic**. By default, Pydantic expects dictionaries (`row["email"]`). But SQLAlchemy database queries return Python class objects (`row.email`). `from_attributes=True` tells Pydantic: *"It is totally fine to read data using dot notation (`row.email`), not just dictionary keys!"*.
* 🎯 **What problem does it solve in our project?**
  Allows your route functions to return raw database objects directly: `return db_booking`. Pydantic automatically reads its attributes and serializes it into clean JSON!
* 💻 **Real Code Snippet (`services/parking/app/schemas/parking.py`):**
  ```python
  from pydantic import BaseModel, ConfigDict

  class SlotResponse(BaseModel):
      id: UUID
      slot_number: str
      vehicle_type: str
      is_active: bool

      # Allows reading directly from SQLAlchemy ParkingSlot ORM instances
      model_config = ConfigDict(from_attributes=True)
  ```

---

### 3.2 `Field(...)`, `EmailStr` & `Literal[...]`

#### `Field(...)` (`from pydantic import Field`)
* 🌟 **What is it in simple words?**
  A **magnifying glass that adds extra validation rules** to a specific field. For example: *"This OTP must be exactly 6 characters long and only numbers"*, or *"This price must be greater than 0"*.
* 🎯 **What problem does it solve in our project?**
  Catches bad user input immediately at the API boundary without writing manual `if len(otp) != 6:` checks in every function.
* 💻 **Real Code Snippet (`services/user-auth/app/schemas/auth.py`):**
  ```python
  from pydantic import BaseModel, Field

  class OTPVerify(BaseModel):
      otp: str = Field(
          min_length=6,
          max_length=6,
          pattern=r"^\d{6}$",  # Must be exactly 6 digits!
          description="6-digit one-time password"
      )
  ```

#### `EmailStr` (`from pydantic import EmailStr`)
* 🌟 **What is it in simple words?**
  A specialized string type that automatically verifies that the text is a **validly formatted email address** (contains `@`, a proper domain name, and no illegal characters).
* 🎯 **What problem does it solve in our project?**
  Stops users from registering with invalid emails like `"not-an-email"`.
* 💻 **Real Code Snippet (`services/user-auth/app/schemas/auth.py`):**
  ```python
  from pydantic import BaseModel, EmailStr

  class OTPRequest(BaseModel):
      email: EmailStr  # Rejects anything that isn't a valid email format!
  ```

#### `Literal[...]` (`from typing import Literal`)
* 🌟 **What is it in simple words?**
  Think of a **strict dropdown menu**. Instead of allowing any random string, `Literal` restricts the value strictly to a list of predefined choices.
* 🎯 **What problem does it solve in our project?**
  Stops typos. For vehicle types, only `"CAR"` and `"BIKE"` are allowed. For booking status, only `"CONFIRMED"`, `"CANCELLED"`, or `"COMPLETED"` are allowed.
* 💻 **Real Code Snippet (`services/vehicle/app/schemas/vehicle.py`):**
  ```python
  from typing import Literal
  from pydantic import BaseModel

  class VehicleCreate(BaseModel):
      vehicle_number: str
      vehicle_type: Literal["CAR", "BIKE"]  # Rejects "TRUCK", "BUS", or lowercase "car"
  ```

---

### 3.3 `@field_validator(...)` & `model_validate(...)`

#### `@field_validator(...)` (`from pydantic import field_validator`)
* 🌟 **What is it in simple words?**
  A **custom sanitizer/inspector** for a specific field. Before data is accepted, this function runs to clean up or transform the value.
* 🎯 **What problem does it solve in our project?**
  Users often type vehicle license plates with messy spaces or lowercase letters (e.g., `"ka-01 ab 1234"`). Our validator strips all spaces and hyphens and converts it to clean uppercase `"KA01AB1234"` so our database remains 100% consistent!
* 💻 **Real Code Snippet (`services/vehicle/app/schemas/vehicle.py`):**
  ```python
  import re
  from pydantic import BaseModel, field_validator

  class VehicleCreate(BaseModel):
      vehicle_number: str

      @field_validator("vehicle_number")
      @classmethod
      def normalize_vehicle_number(cls, v: str) -> str:
          # Strip spaces/hyphens and convert to uppercase
          cleaned = re.sub(r"[\s-]+", "", v).upper()
          if not re.match(r"^[A-Z0-9]{5,15}$", cleaned):
              raise ValueError("Invalid vehicle registration format")
          return cleaned
  ```

#### `model_validate(...)`
* 🌟 **What is it in simple words?**
  An **instant converter button**. You hand it an object (like a SQLAlchemy database row) and say: *"Convert this object into this Pydantic schema right now!"*.
* 🎯 **What problem does it solve in our project?**
  Used when you need to manually turn a database model into a validated response schema before returning it or caching it.
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  slot = db.get(ParkingSlot, slot_id)
  if not slot:
      raise NotFoundError("Slot not found")

  # Converts the SQLAlchemy slot row into a validated SlotResponse Pydantic model:
  return SlotResponse.model_validate(slot)
  ```

---

## Topic 4: Database, SQLAlchemy 2.0 & Alembic (`database.py`, `models/*.py`, `api/*.py`, `alembic/`)

**Subtopics in this section:**
- 4.1 `create_engine(...)`, `sessionmaker(...)`, `DeclarativeBase` (`Base`) & `Session`
- 4.2 `Mapped[...]`, `mapped_column(...)`, `UUID(as_uuid=True)`, `ForeignKey(...)`, `relationship(...)`
- 4.3 `select(...)`, `delete(...)`, `func.count(...)`, `desc(...)`, `and_(...)`, `or_(...)`
- 4.4 `joinedload(...)`, `with_for_update()` & `Base.metadata.create_all(...)`
- 4.5 Session Execution Methods (`db.execute`, `db.get`, `db.add`, `db.add_all`, `db.commit`, `db.refresh`, `db.close`)
- 4.6 Result Extractors (`scalar_one`, `scalar_one_or_none`, `scalars().all()`)
- 4.7 Alembic Built-ins (`engine_from_config`, `pool.NullPool`, `context.*`, `op.*`, `sa.text`)

---

### 4.1 `create_engine(...)`, `sessionmaker(...)`, `DeclarativeBase` (`Base`) & `Session`

#### `create_engine(...)` (`from sqlalchemy import create_engine`)
* 🌟 **What is it in simple words?**
  The **main water pipeline to PostgreSQL**. Instead of opening and closing a brand new network connection for every single query (which is slow), `create_engine` manages a "pool" of open connections ready to be shared.
* 🎯 **What problem does it solve in our project?**
  Provides high-performance database connectivity. We pass `pool_pre_ping=True` so if PostgreSQL closes an idle connection, SQLAlchemy quietly reconnects instead of crashing with a "Connection closed" error.
* 💻 **Real Code Snippet (`services/parking/app/database.py`):**
  ```python
  from sqlalchemy import create_engine

  engine = create_engine(
      settings.DATABASE_URL,
      pool_pre_ping=True,  # Health-checks connections before reusing them
  )
  ```

#### `sessionmaker(...)` (`from sqlalchemy.orm import sessionmaker`)
* 🌟 **What is it in simple words?**
  A **factory that hands out shopping baskets (Sessions)**. Every time an HTTP request comes in, this factory hands you a fresh database Session. You put your queries inside it, commit your changes, and throw the session away when the request ends.
* 🎯 **What problem does it solve in our project?**
  Ensures every request has its own isolated database transaction so two users booking at the same time don't interfere with each other's database states.
* 💻 **Real Code Snippet (`services/parking/app/database.py`):**
  ```python
  from sqlalchemy.orm import sessionmaker

  SessionLocal = sessionmaker(
      autocommit=False,
      autoflush=False,
      expire_on_commit=False,
      bind=engine,
  )
  ```

#### `DeclarativeBase` (`Base`) (`from sqlalchemy.orm import DeclarativeBase`)
* 🌟 **What is it in simple words?**
  The **grandparent blueprint class for all database tables**. You write `class Base(DeclarativeBase): pass`, and then every table model you create inherits from `Base`.
* 🎯 **What problem does it solve in our project?**
  `Base.metadata` collects the schema definitions of all tables in the service. Alembic and `Base.metadata.create_all()` look at `Base.metadata` to know what tables to create in PostgreSQL!
* 💻 **Real Code Snippet (`services/parking/app/database.py`):**
  ```python
  from sqlalchemy.orm import DeclarativeBase

  class Base(DeclarativeBase):
      pass
  ```

#### `Session` (`from sqlalchemy.orm import Session`)
* 🌟 **What is it in simple words?**
  The **active notepad of your current conversation with the database**. When you fetch a row, modify it, or add a new row, the `Session` keeps track of all your changes until you call `commit()`.
* 🎯 **What problem does it solve in our project?**
  Used as the type hint for the `db` parameter across all API routes (`db: Session = Depends(get_db)`).

---

### 4.2 `Mapped[...]`, `mapped_column(...)`, `UUID(as_uuid=True)`, `ForeignKey(...)`, `relationship(...)`

#### `Mapped[...]` & `mapped_column(...)` (`from sqlalchemy.orm import Mapped, mapped_column`)
* 🌟 **What is it in simple words?**
  The **modern SQLAlchemy 2.0 way to define a database column**.
  - `Mapped[str]` tells Python and your code editor: *"This attribute is a string!"* (gives you autocomplete and error checking).
  - `mapped_column(...)` tells PostgreSQL: *"Make this a `VARCHAR(50)`, make it `UNIQUE`, and do not allow `NULL`!"*.
* 🎯 **What problem does it solve in our project?**
  Replaces legacy, untyped SQLAlchemy 1.4 syntax (`Column(String)`), giving us 100% type safety across all database models.
* 💻 **Real Code Snippet (`services/parking/app/models/parking.py`):**
  ```python
  class ParkingSlot(Base):
      __tablename__ = "parking_slots"

      slot_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
      floor: Mapped[int] = mapped_column(Integer, nullable=False)
      is_active: Mapped[bool] = mapped_column(Boolean, default=True)
  ```

#### `UUID(as_uuid=True)` (`from sqlalchemy.dialects.postgresql import UUID`)
* 🌟 **What is it in simple words?**
  Tells PostgreSQL: *"Store this in your native 16-byte UUID binary format"*, and tells Python: *"Convert it automatically into a Python `uuid.UUID` object"*.
* 🎯 **What problem does it solve in our project?**
  Prevents IDOR (Insecure Direct Object Reference) attacks. Instead of predictable numbers (`1, 2, 3`), every record uses a random 128-bit UUID (`d3b07384-d113-4672-887e-41d3e8e19c36`).
* 💻 **Real Code Snippet (`services/parking/app/models/parking.py`):**
  ```python
  import uuid
  from sqlalchemy.dialects.postgresql import UUID

  class ParkingSlot(Base):
      id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
      )
  ```

#### `ForeignKey(...)` (`from sqlalchemy import ForeignKey`)
* 🌟 **What is it in simple words?**
  An **unbreakable chain between two tables**. It tells PostgreSQL: *"A booking MUST point to a valid slot that already exists in `parking_slots`. If someone tries to book slot ID 999 which does not exist, reject it with an error!"*.
* 🎯 **What problem does it solve in our project?**
  Guarantees database integrity. You cannot have "orphan" bookings that point to nonexistent parking slots.
* 💻 **Real Code Snippet (`services/parking/app/models/parking.py`):**
  ```python
  class Booking(Base):
      slot_id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True), ForeignKey("parking_slots.id"), nullable=False
      )
  ```

#### `relationship(...)` (`from sqlalchemy.orm import relationship`)
* 🌟 **What is it in simple words?**
  A **magical Python shortcut**. Instead of writing a manual SQL `JOIN` query every time you want to find which slot belongs to a booking, `relationship` lets you simply type `booking.slot.slot_number` in Python!
* 🎯 **What problem does it solve in our project?**
  Makes your Python code clean, readable, and object-oriented.
* 💻 **Real Code Snippet (`services/parking/app/models/parking.py`):**
  ```python
  class Booking(Base):
      # Lets you do: current_booking.slot.slot_number directly!
      slot: Mapped["ParkingSlot"] = relationship("ParkingSlot", back_populates="bookings")
  ```

---

### 4.3 `select(...)`, `delete(...)`, `func.count(...)`, `desc(...)`, `and_(...)`, `or_(...)`

#### `select(...)` (`from sqlalchemy import select`)
* 🌟 **What is it in simple words?**
  The Python version of SQL `SELECT * FROM ...`.
* 🎯 **What problem does it solve in our project?**
  The standard SQLAlchemy 2.0 way to query data.
* 💻 **Real Code Snippet:**
  ```python
  # Translates to: SELECT * FROM parking_slots WHERE is_active = true;
  stmt = select(ParkingSlot).where(ParkingSlot.is_active == True)
  slots = db.execute(stmt).scalars().all()
  ```

#### `delete(...)` (`from sqlalchemy import delete`)
* 🌟 **What is it in simple words?**
  The Python version of SQL `DELETE FROM ... WHERE ...`.
* 🎯 **What problem does it solve in our project?**
  Used to clean up expired temporary holds in bulk in a single database round-trip.
* 💻 **Real Code Snippet (`services/parking/app/api/internal.py`):**
  ```python
  # Deletes all temporary holds whose expiration time has passed
  stmt = delete(SlotHold).where(SlotHold.expires_at < datetime.now(timezone.utc))
  db.execute(stmt)
  db.commit()
  ```

#### `func.count(...)` (`from sqlalchemy import func`)
* 🌟 **What is it in simple words?**
  Executes SQL `COUNT(...)` on the database server to count rows **without downloading them into Python memory**.
* 🎯 **What problem does it solve in our project?**
  Checks whether a user already has an active booking on a given date without wasting RAM loading all the booking rows.
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  stmt = select(func.count(Booking.id)).where(
      Booking.user_id == user_id,
      Booking.booking_date == target_date,
      Booking.status == "CONFIRMED",
  )
  count = db.execute(stmt).scalar_one()
  ```

#### `desc(...)` (`from sqlalchemy import desc`)
* 🌟 **What is it in simple words?**
  Sorts records in **descending order (newest first)**.
* 🎯 **What problem does it solve in our project?**
  Ensures that when a user looks at their booking history, the most recent bookings appear at the very top.
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  # Translates to: ORDER BY created_at DESC
  stmt = select(Booking).where(Booking.user_id == user_id).order_by(desc(Booking.created_at))
  ```

#### `and_(...)` & `or_(...)` (`from sqlalchemy import and_, or_`)
* 🌟 **What is it in simple words?**
  Combines multiple filtering conditions with clean parentheses, matching SQL `AND` and `OR`.
* 🎯 **What problem does it solve in our project?**
  Used when checking whether two time slots overlap when reserving a parking spot.
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  stmt = select(Booking).where(
      and_(
          Booking.slot_id == slot_id,
          Booking.booking_date == target_date,
          or_(Booking.status == "CONFIRMED", Booking.status == "HOLD"),
      )
  )
  ```

---

### 4.4 `joinedload(...)`, `with_for_update()` & `Base.metadata.create_all(...)`

#### `joinedload(...)` (`from sqlalchemy.orm import joinedload`)
* 🌟 **What is it in simple words?**
  Think of **ordering a toy that comes with the batteries already in the box**. Normally, if you load 50 bookings and then access `b.slot.slot_number`, SQLAlchemy will fire **50 extra separate SQL queries** to fetch the slot for each booking (the infamous "N+1 query problem")! `joinedload` fetches both the booking AND the slot together in **1 single SQL query** using a `LEFT JOIN`.
* 🎯 **What problem does it solve in our project?**
  Drastically reduces database latency and prevents the database from getting overwhelmed by hundreds of unnecessary queries.
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  # Fetches Bookings AND their related ParkingSlot objects in ONE query!
  stmt = (
      select(Booking)
      .options(joinedload(Booking.slot))
      .where(Booking.user_id == user_id)
  )
  bookings = db.execute(stmt).scalars().all()
  ```

#### `with_for_update()` (`stmt.with_for_update()`)
* 🌟 **What is it in simple words?**
  Think of a **bouncer who physically locks the door while you examine an item**. It tells PostgreSQL: *"I am reading this slot row, and I am locking it. If any other transaction tries to touch this slot at the exact same millisecond, make them wait in line until I finish and commit!"*.
* 🎯 **What problem does it solve in our project?**
  Prevents **race conditions and double-bookings**. If 10 employees try to book the last remaining parking slot at 9:00:00 AM, `with_for_update()` forces PostgreSQL to process them one-by-one. The first gets the slot, and the other 9 are rejected!
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  # Locks the slot row in PostgreSQL so no concurrent request can book it at the same time:
  stmt = (
      select(ParkingSlot)
      .where(ParkingSlot.id == slot_id)
      .with_for_update()
  )
  slot = db.execute(stmt).scalar_one_or_none()
  ```

#### `Base.metadata.create_all(...)`
* 🌟 **What is it in simple words?**
  The master command: *"Look at all our Python table classes and create any tables in PostgreSQL that don't already exist!"* (Emits `CREATE TABLE IF NOT EXISTS`).
* 🎯 **What problem does it solve in our project?**
  Used at service startup (`lifespan`) and inside test fixtures to set up database tables automatically without manual SQL scripts.
* 💻 **Real Code Snippet (`services/parking/app/main.py`):**
  ```python
  Base.metadata.create_all(bind=engine)
  ```

---

### 4.5 Session Execution Methods

Here is the simple, complete cheatsheet for how you talk to the database using `db`:

| Method | What is it in simple words? | Example from `ParkingSimplified` |
| :--- | :--- | :--- |
| **`db.execute(stmt)`** | Sends your `select(...)` or `delete(...)` query to the database server. | `result = db.execute(stmt)` |
| **`db.get(Model, id)`** | Shortcut to fetch one row directly by its primary key ID (returns `None` if missing). | `slot = db.get(ParkingSlot, slot_id)` |
| **`db.add(obj)`** | Puts a new record into your "shopping cart" (stages an `INSERT` or `UPDATE`). | `db.add(new_booking)` |
| **`db.add_all([a, b])`** | Puts multiple new records into the shopping cart at once. | `db.add_all([slot1, slot2, slot3])` |
| **`db.commit()`** | **The Checkout button!** Permanently saves all staged changes to the database disk. | `db.commit()` |
| **`db.refresh(obj)`** | Asks PostgreSQL: *"Please update my Python object with any database-generated values (like auto-generated IDs or timestamps)"*. | `db.refresh(new_booking)` |
| **`db.close()`** | Returns the database connection back to the connection pool for others to use. | `db.close()` (handled automatically by `get_db`) |

---

### 4.6 Result Extractors (`scalar_one`, `scalar_one_or_none`, `scalars().all()`)

When you run `result = db.execute(stmt)`, how do you get the actual Python objects out of `result`?

#### 1. `scalar_one()`
* 🌟 **What is it?** *"I expect **exactly one single value**. If there are 0 rows, or if there are 2 or more rows, crash with an error!"*.
* 🎯 **When to use:** Perfect for SQL counts (`func.count`).
* 💻 **Example:** `total_count = db.execute(count_stmt).scalar_one()`

#### 2. `scalar_one_or_none()`
* 🌟 **What is it?** *"I expect **at most one row**. If found, give it to me. If no match exists, return `None`. If there are 2 or more rows, crash!"*.
* 🎯 **When to use:** Perfect for searching by unique attributes (like searching a user by email, or a slot by slot number).
* 💻 **Example:**
  ```python
  stmt = select(User).where(User.email == email)
  user = db.execute(stmt).scalar_one_or_none()
  if not user:
      raise NotFoundError("User does not exist")
  ```

#### 3. `scalars().all()`
* 🌟 **What is it?** *"Give me **a plain Python list** of all the matching rows"*.
* 🎯 **When to use:** Perfect for listing records (all available slots, all registered vehicles, all past bookings).
* 💻 **Example:**
  ```python
  stmt = select(ParkingSlot).where(ParkingSlot.is_active == True)
  slots: list[ParkingSlot] = db.execute(stmt).scalars().all()
  ```

---

### 4.7 Alembic Built-ins (`alembic/env.py` & migrations)

#### `engine_from_config(...)` & `pool.NullPool`
* 🌟 **What is it in simple words?**
  Reads the database connection URL from `alembic.ini` and builds an engine specifically to run migration scripts. `NullPool` tells Alembic: *"Do not keep connections open in an idle pool. Connect, run the migration, and disconnect immediately"*.
* 💻 **Real Code Snippet (`services/parking/alembic/env.py`):**
  ```python
  connectable = engine_from_config(
      config.get_section(config.config_ini_section),
      prefix="sqlalchemy.",
      poolclass=pool.NullPool,
  )
  ```

#### `context.configure(...)`, `context.begin_transaction()`, `context.run_migrations()`
* 🌟 **What is it in simple words?**
  The **migration runner engine**. It connects Alembic to `Base.metadata`, opens a safe database transaction, and executes the migration steps. If anything fails halfway through, the transaction rolls back cleanly so your database is never corrupted.
* 💻 **Real Code Snippet (`services/parking/alembic/env.py`):**
  ```python
  with connectable.connect() as connection:
      context.configure(connection=connection, target_metadata=target_metadata)
      with context.begin_transaction():
          context.run_migrations()
  ```

#### `op.create_table(...)` & `op.drop_table(...)`
* 🌟 **What is it in simple words?**
  The built-in commands written inside migration files:
  - `op.create_table`: Runs during `upgrade()` to create a new table.
  - `op.drop_table`: Runs during `downgrade()` to undo the creation.
* 💻 **Real Code Snippet (`services/parking/alembic/versions/0001_create_parking_tables.py`):**
  ```python
  def upgrade() -> None:
      op.create_table(
          "parking_slots",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
          sa.Column("slot_number", sa.String(length=20), nullable=False),
          sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
      )

  def downgrade() -> None:
      op.drop_table("parking_slots")
  ```

#### `sa.text(...)` (`import sqlalchemy as sa`)
* 🌟 **What is it in simple words?**
  Lets you pass **raw SQL expressions** directly to the database. For example, `server_default=sa.text("true")` tells PostgreSQL to set the database-level default value to SQL `true`.

---

## Topic 5: Python Standard Library Built-ins Used Directly

**Subtopics in this section:**
- 5.1 Security & Identifiers (`uuid.uuid4`, `uuid.UUID`, `.hex`, `secrets.randbelow`)
- 5.2 Dates, Timezones & Exact Money (`datetime.now`, `datetime.combine`, `timedelta`, `timezone.utc`, `ZoneInfo`, `Decimal`)
- 5.3 OOP, Regex & Typing Helpers (`ABC`, `@abstractmethod`, `@dataclass`, `re.compile`, `re.sub`, `Generator`)

---

### 5.1 Security & Identifiers (`uuid.uuid4`, `uuid.UUID`, `.hex`, `secrets.randbelow`)

#### `uuid.uuid4()`, `uuid.UUID(...)` & `.hex`
* 🌟 **What is it in simple words?**
  - `uuid.uuid4()`: Generates a completely unpredictable, globally unique 128-bit ID (e.g. `9f8b2c4e-1234-4567-89ab-cdef01234567`).
  - `uuid.UUID(s)`: Parses a string into a real Python UUID object.
  - `.hex`: Returns the UUID as a plain 32-character string **without hyphens**.
* 🎯 **What problem does it solve in our project?**
  Used for all primary keys in our databases. We also use `.hex` to generate clean, compact payment transaction references like `"TXN9F8B2C4E12"`!
* 💻 **Real Code Snippet (`services/payment/app/api/payment.py`):**
  ```python
  import uuid

  # Generate a clean transaction reference without hyphens:
  txn_ref = f"TXN{uuid.uuid4().hex[:10].upper()}"  # e.g., "TXN4B8C1E0A2F"
  ```

#### `secrets.randbelow(...)` (`import secrets`)
* 🌟 **What is it in simple words?**
  A **cryptographically secure random number generator**.
* 🎯 **What problem does it solve in our project?**
  Used to generate 6-digit login OTPs.
  > ⚠️ **Critical Interview Tip:** Why do we use `secrets.randbelow` instead of `random.randint`?
  > Standard `random` uses the Mersenne Twister algorithm, which is **predictable**. If an attacker observes a few outputs, they can calculate the next OTP! `secrets` uses the operating system's cryptographic entropy source, making the OTP mathematically impossible to predict.
* 💻 **Real Code Snippet (`services/user-auth/app/api/auth.py`):**
  ```python
  import secrets

  # Generates a truly random 6-digit integer from 100000 to 999999:
  otp_code = str(secrets.randbelow(900_000) + 100_000)
  ```

---

### 5.2 Dates, Timezones & Exact Money (`datetime.now`, `datetime.combine`, `timedelta`, `timezone.utc`, `ZoneInfo`, `Decimal`)

#### `datetime.now(timezone.utc)` & `timedelta(...)`
* 🌟 **What is it in simple words?**
  - `datetime.now(timezone.utc)`: Gets the current exact time in **UTC timezone**.
  - `timedelta(minutes=5)`: Represents a duration of time (e.g., adding 5 minutes).
* 🎯 **What problem does it solve in our project?**
  When a user reserves a slot, we give them a 5-minute temporary hold to finish payment. If payment isn't completed before `expires_at`, the hold expires.
* 💻 **Real Code Snippet (`services/parking/app/api/internal.py`):**
  ```python
  from datetime import datetime, timedelta, timezone

  now = datetime.now(timezone.utc)
  expires_at = now + timedelta(minutes=5)  # Exactly 5 minutes in the future!
  ```

#### `datetime.combine(...)`
* 🌟 **What is it in simple words?**
  **Glues a separate date and time together** into one complete datetime object.
* 🎯 **What problem does it solve in our project?**
  In our database, bookings store `booking_date` (`2026-11-26`) and `start_time` (`09:00:00`) in separate columns. To check if a booking is in the past, `datetime.combine` merges them into `2026-11-26 09:00:00`.
* 💻 **Real Code Snippet (`services/parking/app/api/parking.py`):**
  ```python
  from datetime import datetime

  # Merges separate date and time columns:
  start_dt = datetime.combine(booking.booking_date, booking.start_time)
  if start_dt < datetime.now():
      raise BadRequestError("Cannot book a slot in the past!")
  ```

#### `ZoneInfo("Asia/Kolkata")` (`from zoneinfo import ZoneInfo`)
* 🌟 **What is it in simple words?**
  Python's built-in timezone database.
* 🎯 **What problem does it solve in our project?**
  Parking facility rules operate on local facility time (e.g. gates open from 06:00 AM to 11:00 PM Indian Standard Time), even though server clocks run on UTC.
* 💻 **Real Code Snippet:**
  ```python
  from zoneinfo import ZoneInfo

  facility_tz = ZoneInfo("Asia/Kolkata")
  local_now = datetime.now(facility_tz)
  ```

#### `Decimal("10.00")` (`from decimal import Decimal`)
* 🌟 **What is it in simple words?**
  **Exact decimal math for money calculations**.
  > ⚠️ **Interview Classic:** In standard Python floating-point math:
  > `0.1 + 0.2` returns `0.30000000000000004` (due to binary float limitations).
  > With `Decimal('0.1') + Decimal('0.2')`, it returns **exactly** `Decimal('0.3')`!
* 🎯 **What problem does it solve in our project?**
  In financial calculations (hourly parking rates $\times$ hours parked), `Decimal` ensures you never lose a single penny to rounding errors.
* 💻 **Real Code Snippet (`services/payment/app/models/payment.py`):**
  ```python
  from decimal import Decimal

  hourly_rate = Decimal("20.00")
  hours_parked = Decimal("3.5")
  total_price = hourly_rate * hours_parked  # Exactly Decimal("70.000")
  ```

---

### 5.3 OOP, Regex & Typing Helpers (`ABC`, `@abstractmethod`, `@dataclass`, `re.compile`, `re.sub`, `Generator`)

#### `ABC` & `@abstractmethod` (`from abc import ABC, abstractmethod`)
* 🌟 **What is it in simple words?**
  Think of a **job contract**. It defines an interface and says: *"Any class that wants this job MUST implement these exact methods, or Python will refuse to let the program run!"*.
* 🎯 **What problem does it solve in our project?**
  We define an `EmailSender(ABC)` interface with an abstract `send_otp()` method. In local development, `ConsoleEmailSender` prints the OTP to the console. In production, a `SendGridEmailSender` can replace it without changing any business logic!
* 💻 **Real Code Snippet (`services/user-auth/app/core/email.py`):**
  ```python
  from abc import ABC, abstractmethod

  class EmailSender(ABC):
      @abstractmethod
      def send_otp(self, to_email: str, otp: str) -> None:
          """Every email provider MUST implement this method!"""
          pass

  class ConsoleEmailSender(EmailSender):
      def send_otp(self, to_email: str, otp: str) -> None:
          print(f"[LOCAL DEV] Sending OTP {otp} to {to_email}")
  ```

#### `@dataclass` (`from dataclasses import dataclass`)
* 🌟 **What is it in simple words?**
  A decorator that eliminates boilerplate. Instead of writing `def __init__(self, user_id, email): self.user_id = user_id; self.email = email`, `@dataclass` creates `__init__`, `__repr__`, and equality checks automatically!
* 🎯 **What problem does it solve in our project?**
  Used for lightweight internal data carriers like `AuthContext`.
* 💻 **Real Code Snippet (`services/common/app/core/security.py`):**
  ```python
  from dataclasses import dataclass
  from uuid import UUID

  @dataclass
  class AuthContext:
      user_id: UUID
      email: str
      role: str = "EMPLOYEE"
  ```

#### `re.compile(...)` & `re.sub(...)` (`import re`)
* 🌟 **What is it in simple words?**
  - `re.compile`: Pre-compiles a regular expression pattern so it searches text at maximum speed.
  - `re.sub`: Replaces matching patterns (like removing all spaces and hyphens).
* 🎯 **What problem does it solve in our project?**
  Cleans and validates vehicle license plates.
* 💻 **Real Code Snippet (`services/vehicle/app/schemas/vehicle.py`):**
  ```python
  import re

  # Pre-compiled license plate pattern:
  _PLATE_REGEX = re.compile(r"^[A-Z0-9]{5,15}$")

  # Strips all whitespace and hyphens:
  cleaned_plate = re.sub(r"[\s-]+", "", raw_input).upper()
  ```

#### `Generator[Session, None, None]` (`from collections.abc import Generator`)
* 🌟 **What is it in simple words?**
  The Python type annotation for any function that uses `yield` instead of `return`.
* 🎯 **What problem does it solve in our project?**
  Documents the exact return type of the `get_db()` dependency injection function.
* 💻 **Real Code Snippet (`services/parking/app/database.py`):**
  ```python
  from collections.abc import Generator

  def get_db() -> Generator[Session, None, None]:
      db = SessionLocal()
      try:
          yield db  # Hands the active session to the route
      finally:
          db.close()  # Closes connection after the route completes
  ```

---

## Topic 6: Testing & Concurrency Built-ins (`tests/` & `services/*/tests/`)

**Subtopics in this section:**
- 6.1 `TestClient(...)` & `@pytest.fixture()`
- 6.2 `StaticPool` (`sqlalchemy.pool`)
- 6.3 `threading.Barrier`, `ThreadPoolExecutor` & `subprocess.Popen`

---

### 6.1 `TestClient(...)` & `@pytest.fixture()`

#### `TestClient(...)` (`from fastapi.testclient import TestClient`)
* 🌟 **What is it in simple words?**
  A **fake in-memory HTTP client**. It lets you call `client.get("/api/v1/slots")` or `client.post(...)` directly against your FastAPI app in memory **without starting a real server, without opening a network port, and without firewall prompts**!
* 🎯 **What problem does it solve in our project?**
  Powers our unit and integration test suite, executing hundreds of API tests in seconds.
* 💻 **Real Code Snippet (`services/parking/tests/test_parking_api.py`):**
  ```python
  from fastapi.testclient import TestClient
  from app.main import app

  client = TestClient(app)

  def test_health_check():
      response = client.get("/health")
      assert response.status_code == 200
      assert response.json()["status"] == "ok"
  ```

#### `@pytest.fixture()` (`import pytest`)
* 🌟 **What is it in simple words?**
  Think of a **stage crew that sets up the props before a play begins, and cleans up the stage when the play ends**. Any test function that needs a fresh database or an auth token simply names the fixture in its parameters, and `pytest` injects it automatically!
* 🎯 **What problem does it solve in our project?**
  Guarantees each test starts with a completely clean database so tests never pollute or break each other.
* 💻 **Real Code Snippet (`services/parking/tests/conftest.py`):**
  ```python
  import pytest

  @pytest.fixture
  def db_session():
      # Setup: Create tables before the test runs
      Base.metadata.create_all(bind=engine)
      session = TestingSessionLocal()
      
      yield session  # Pass the clean session to the test
      
      # Teardown: Clean up and drop tables after the test finishes
      session.close()
      Base.metadata.drop_all(bind=engine)
  ```

---

### 6.2 `StaticPool` (`sqlalchemy.pool`)

#### `StaticPool`
* 🌟 **What is it in simple words?**
  A special connection pool that **keeps a single in-memory SQLite database alive forever**. Normally, in-memory SQLite (`sqlite:///:memory:`) wipes its entire database the millisecond a connection closes. `StaticPool` holds that single connection open across all requests during a test.
* 🎯 **What problem does it solve in our project?**
  Allows multiple `get_db()` calls in a test to see the exact same test database without wiping tables between calls.
* 💻 **Real Code Snippet (`services/parking/tests/conftest.py`):**
  ```python
  from sqlalchemy import create_engine
  from sqlalchemy.pool import StaticPool

  # Keeps in-memory SQLite alive across all requests in a test:
  test_engine = create_engine(
      "sqlite:///:memory:",
      connect_args={"check_same_thread": False},
      poolclass=StaticPool,
  )
  ```

---

### 6.3 `threading.Barrier`, `ThreadPoolExecutor` & `subprocess.Popen`

#### `threading.Barrier(n)` (`import threading`)
* 🌟 **What is it in simple words?**
  Think of the **starting gate at an Olympic sprint**. Runners walk up to the gate at different times and call `barrier.wait()`. The gate holds them all back until the 10th runner arrives. The moment all 10 are lined up, the gate drops and all 10 sprint at the exact same millisecond!
* 🎯 **What problem does it solve in our project?**
  Used in `tests/test_pg_concurrency.py` to trigger **real race conditions**. It fires 10 simultaneous booking requests at the exact same microsecond to prove that our PostgreSQL `with_for_update()` lock allows only 1 booking and rejects the other 9!
* 💻 **Real Code Snippet (`tests/test_pg_concurrency.py`):**
  ```python
  import threading

  barrier = threading.Barrier(10)  # Wait for 10 threads

  def attempt_booking(user_id):
      barrier.wait()  # All 10 threads pause here until everyone arrives, then fire together!
      return book_slot(user_id, slot_id)
  ```

#### `ThreadPoolExecutor(max_workers=n)` (`from concurrent.futures import ThreadPoolExecutor`)
* 🌟 **What is it in simple words?**
  A **worker manager that runs tasks on multiple CPU threads concurrently**.
* 🎯 **What problem does it solve in our project?**
  Spawns and manages the 10 worker threads in our concurrency test.
* 💻 **Real Code Snippet (`tests/test_pg_concurrency.py`):**
  ```python
  from concurrent.futures import ThreadPoolExecutor

  with ThreadPoolExecutor(max_workers=10) as executor:
      results = list(executor.map(attempt_booking, user_ids))
  ```

#### `subprocess.Popen(...)` (`import subprocess`)
* 🌟 **What is it in simple words?**
  Launches a real operating system program or command in the background (like typing `python -m uvicorn ...` in a separate terminal window).
* 🎯 **What problem does it solve in our project?**
  During our End-to-End (E2E) integration test (`tests/test_e2e_journey.py`), `subprocess.Popen` starts all 4 real microservices on ports 8001, 8002, 8003, and 8004 as background processes, lets the full user journey test run against them, and then cleanly shuts them all down (`terminate()` and `wait()`) when testing finishes!
* 💻 **Real Code Snippet (`tests/test_e2e_journey.py`):**
  ```python
  import subprocess

  # Starts the real Parking microservice on port 8003 in the background:
  proc = subprocess.Popen(
      ["python", "-m", "uvicorn", "app.main:app", "--port", "8003"],
      cwd="services/parking",
  )

  # Cleanup when tests are done:
  proc.terminate()
  proc.wait()
  ```

---

## Summary Reference Table: Which Method Belongs Where?

| Built-in / Library Method | Topic / Layer | Primary Role in `ParkingSimplified` |
| :--- | :--- | :--- |
| **`FastAPI(...)`** | App-Bootstrap | Root microservice application instance & Swagger UI generator |
| **`@app.get(...)`** | App-Bootstrap | Binds route paths directly to the root application (e.g. `/health`) |
| **`@asynccontextmanager`** | App-Bootstrap | Modern `lifespan` manager for startup table creation & shutdown cleanup |
| **`app.include_router(...)`** | App-Bootstrap | Plugs modular sub-routers (`/api/v1/...`, `/internal/v1/...`) into main app |
| **`app.dependency_overrides`** | Testing / Bootstrap | Replaces production dependencies (DB, HTTP clients) with test doubles |
| **`@app.exception_handler`** | App-Bootstrap | Catches domain errors globally and formats them as standard JSON |
| **`RequestValidationError`** | App-Bootstrap | FastAPI error raised when incoming request data fails Pydantic schema validation |
| **`HTTPException`** | App-Bootstrap | Base HTTP exception with status code, inherited by all our custom `AppError`s |
| **`JSONResponse`** | App-Bootstrap | Formats raw Python dictionaries into HTTP JSON responses with explicit status |
| **`BaseSettings`** | Core / Config | Reads `.env` files and environment variables into typed configuration objects |
| **`SettingsConfigDict`** | Core / Config | Configures `.env` parsing rules (e.g. `extra="ignore"` for multi-service setup) |
| **`APIRouter(...)`** | Core / Routes | Groups related API routes under a shared URL prefix and OpenAPI tag |
| **`Depends(...)`** | Core / DI | FastAPI Dependency Injection marker for database sessions and auth contexts |
| **`Query(...)`** | Core / Routes | Extracts and validates URL query string parameters (`?date=...&type=...`) |
| **`Header(...)`** | Core / Routes | Extracts HTTP request headers (used for `X-Internal-Service-Token`) |
| **`Response`** | Core / Routes | Allows dynamic override of response status codes or headers inside a route |
| **`status`** | Core / HTTP | Named HTTP status constants (`status.HTTP_201_CREATED`, `404_NOT_FOUND`) |
| **`HTTPBearer(...)`** | Core / Security | Extracts `Authorization: Bearer <token>` and activates Swagger UI auth |
| **`HTTPAuthorizationCredentials`** | Core / Security | Holds the extracted Bearer token string (`credentials.credentials`) |
| **`jwt.encode(...)`** | Core / Security | Signs user identity (`sub`, `email`, `exp`) into an HS256 JWT string |
| **`jwt.decode(...)`** | Core / Security | Verifies token signature & expiration, enabling zero-DB local auth |
| **`jwt.PyJWTError`** | Core / Security | Base exception catching expired, malformed, or tampered tokens |
| **`httpx.Client(...)`** | Core / Clients | Synchronous HTTP client for cross-service calls with bounded timeouts |
| **`httpx.HTTPError`** | Core / Clients | Catches cross-service timeouts and network disconnects to return 503 |
| **`BaseModel`** | Schemas | Base class for all API request and response data transfer objects |
| **`ConfigDict(from_attributes=True)`** | Schemas | Allows Pydantic schemas to read directly from SQLAlchemy ORM attributes |
| **`Field(...)`** | Schemas | Adds fine-grained validation (min/max length, regex patterns, numeric bounds) |
| **`EmailStr`** | Schemas | Validates that a string is a properly formatted email address |
| **`Literal[...]`** | Schemas | Restricts string values to an exact set of allowed constants (`CAR`, `BIKE`) |
| **`@field_validator(...)`** | Schemas | Runs custom sanitization (e.g. stripping spaces from vehicle plates) |
| **`model_validate(...)`** | Schemas | Converts a database ORM instance into a validated Pydantic model |
| **`create_engine(...)`** | Database / ORM | Creates database connection pipeline and connection pool (`pool_pre_ping`) |
| **`sessionmaker(...)`** | Database / ORM | Factory creating isolated, request-scoped `Session` instances |
| **`DeclarativeBase` (`Base`)** | Database / ORM | Parent blueprint collecting table metadata for Alembic and `create_all` |
| **`Session`** | Database / ORM | Active database conversation/notepad tracking changes for `commit()` |
| **`Mapped[...]` / `mapped_column(...)`** | Database / ORM | SQLAlchemy 2.0 type-safe column definitions |
| **`UUID(as_uuid=True)`** | Database / ORM | Native PostgreSQL 16-byte UUID column mapped to Python `uuid.UUID` |
| **`ForeignKey(...)`** | Database / ORM | Enforces relational integrity constraint across tables in the same DB |
| **`relationship(...)`** | Database / ORM | Python navigation shortcut across Foreign Keys (`booking.slot.slot_number`) |
| **`select(...)`** | Database / ORM | Builds SQL `SELECT` statements in SQLAlchemy 2.0 style |
| **`delete(...)`** | Database / ORM | Builds bulk SQL `DELETE` statements (used for cleaning expired holds) |
| **`func.count(...)`** | Database / ORM | Emits SQL `COUNT(...)` without loading table rows into memory |
| **`desc(...)`** | Database / ORM | Emits `ORDER BY col DESC` to sort newest records first |
| **`and_(...)` / `or_(...)`** | Database / ORM | Combines SQL boolean conditions with explicit parentheses |
| **`joinedload(...)`** | Database / ORM | Emits `LEFT OUTER JOIN` to prevent the N+1 query problem |
| **`with_for_update()`** | Database / ORM | PostgreSQL row-level lock (`FOR UPDATE`) preventing race conditions |
| **`Base.metadata.create_all`** | Database / ORM | Creates all tables in database if they do not exist |
| **`db.execute(...)`** | Database / ORM | Executes statements (`select`, `delete`) on the database |
| **`db.get(Model, pk)`** | Database / ORM | Fast lookup by primary key ID (returns `None` if not found) |
| **`db.add(...)` / `db.add_all(...)`** | Database / ORM | Stages new or modified ORM instances in the session |
| **`db.commit(...)`** | Database / ORM | Persists staged changes to disk in a single database transaction |
| **`db.refresh(...)`** | Database / ORM | Reloads database-generated values (`id`, `created_at`) onto Python object |
| **`db.close(...)`** | Database / ORM | Releases the database connection back to the connection pool |
| **`scalar_one()`** | Database / ORM | Extracts exactly one scalar value (fails if 0 or >1 rows) |
| **`scalar_one_or_none()`** | Database / ORM | Extracts one model/value, or returns `None` if no match exists |
| **`scalars().all()`** | Database / ORM | Extracts all matching rows as a plain Python list |
| **`engine_from_config`** | Alembic | Builds migration engine from `alembic.ini` settings |
| **`pool.NullPool`** | Alembic | Closes database connections immediately without keeping idle pool |
| **`context.configure / run_migrations`** | Alembic | Runs schema migration runner inside a database transaction |
| **`op.create_table / drop_table`** | Alembic | Emits DDL operations inside `upgrade()` and `downgrade()` scripts |
| **`sa.text(...)`** | Alembic / ORM | Passes raw SQL snippets to column definitions (`server_default=sa.text("true")`) |
| **`uuid.uuid4()` / `.hex`** | Stdlib / Crypto | Generates 128-bit random IDs and hyphen-free transaction strings |
| **`secrets.randbelow(...)`** | Stdlib / Crypto | Cryptographically secure random number generator for login OTPs |
| **`datetime.now(timezone.utc)`** | Stdlib / Time | Aware UTC current timestamp |
| **`timedelta(...)`** | Stdlib / Time | Represents time duration (e.g. 5-minute hold window) |
| **`datetime.combine(...)`** | Stdlib / Time | Glues date and time into a complete datetime object |
| **`ZoneInfo(...)`** | Stdlib / Time | Local facility timezone for operating hours |
| **`Decimal(...)`** | Stdlib / Math | Exact base-10 arithmetic for financial calculations without float drift |
| **`ABC` / `@abstractmethod`** | Stdlib / OOP | Defines strict interface contracts (e.g. `EmailSender`) |
| **`@dataclass`** | Stdlib / OOP | Boilerplate-free data carrier class (e.g. `AuthContext`) |
| **`re.compile(...)` / `re.sub(...)`** | Stdlib / Regex | Fast pre-compiled pattern matching & string sanitization |
| **`Generator[...]`** | Stdlib / Typing | Return type annotation for `yield`-based dependencies (`get_db`) |
| **`TestClient(...)`** | Testing | In-memory HTTP client testing API routes without starting a port |
| **`@pytest.fixture()`** | Testing | Reusable setup/teardown injection for test databases and auth |
| **`StaticPool`** | Testing | Keeps single SQLite in-memory database alive across test sessions |
| **`threading.Barrier(n)`** | Testing / Concurrency | Synchronizes `n` threads to release simultaneously for race condition testing |
| **`ThreadPoolExecutor`** | Testing / Concurrency | Manages pool of threads executing concurrent test requests |
| **`subprocess.Popen(...)`** | Testing / OS | Launches live microservices as OS child processes for E2E testing |
