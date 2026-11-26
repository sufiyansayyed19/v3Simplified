# Topic 1: App Bootstrap & Error Handling (`app/main.py` & `app/core/errors.py`)

This file explains every built-in class, method, and decorator used at the **root level** of each microservice.

**Contents:**
1. [`FastAPI(...)`](#1-fastapi)
2. [`@app.get(...)`](#2-appget)
3. [`@asynccontextmanager`](#3-asynccontextmanager)
4. [`app.include_router(...)`](#4-appinclude_router)
5. [`app.dependency_overrides`](#5-appdependency_overrides)
6. [`@app.exception_handler(...)`](#6-appexception_handler)
7. [`RequestValidationError`](#7-requestvalidationerror)
8. [`HTTPException`](#8-httpexception)
9. [`JSONResponse`](#9-jsonresponse)

---

## 1. `FastAPI(...)`

* **Import:** `from fastapi import FastAPI`
* **In Simple Words:** The **main application object** representing one microservice. Think of it as the front desk manager of a building: it receives every HTTP request, checks the URL and parameters, calls the right Python function, and automatically generates interactive Swagger UI documentation at `/docs`.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `title` | `str` | `"FastAPI"` | Sets the project title displayed at the top of `/docs` (Swagger UI). |
| `version` | `str` | `"0.1.0"` | API version shown in `/docs` and OpenAPI JSON schema. |
| `description` | `str` | `""` | Optional Markdown description shown under the title in `/docs`. |
| `lifespan` | `Callable` | `None` | Async context manager function that runs startup logic (like creating DB tables) before the server accepts requests, and shutdown logic when the server stops. |
| `docs_url` | `str \| None` | `"/docs"` | URL path for Swagger UI. Set to `None` to disable `/docs` in production. |

* **Returns:** A `FastAPI` ASGI application instance (`app`).
* **Project Example (`services/parking-service/app/main.py`):**
  ```python
  app = FastAPI(
      title="Corporate Parking — Parking Service",
      lifespan=lifespan,
  )
  ```

---

## 2. `@app.get(...)`

* **Import:** Decorator method on your `app = FastAPI(...)` instance.
* **In Simple Words:** Binds an HTTP `GET` URL path directly to a Python function. When someone visits that URL (e.g., `/health`), FastAPI runs the decorated function and returns its result as JSON.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `path` | `str` | **Required** | The URL route path (e.g. `"/health"`). |
| `tags` | `list[str]` | `None` | Groups this endpoint under a named section in `/docs` Swagger UI. |
| `status_code` | `int` | `200` | Default HTTP status code returned on success. |
| `response_model` | `type` | `None` | Pydantic schema used to filter, validate, and document the output JSON. |

* **Returns:** The original function (registered internally in FastAPI's routing table).
* **Project Example (`services/user-auth-service/app/main.py`):**
  ```python
  @app.get("/health", tags=["health"])
  def health_check():
      return {"status": "ok", "service": settings.SERVICE_NAME}
  ```

---

## 3. `@asynccontextmanager`

* **Import:** `from contextlib import asynccontextmanager`
* **In Simple Words:** Turns an `async def` function containing a single `yield` into a **startup + shutdown lifecycle hook** for FastAPI. Everything *before* `yield` runs once when the server boots up; everything *after* `yield` runs once when the server shuts down.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `func` | `AsyncGenerator` | **Required** | Passed automatically via `@asynccontextmanager` above an `async def` function that yields once. |

* **Returns:** An asynchronous context manager compatible with `FastAPI(..., lifespan=lifespan)`.
* **Project Example (`services/parking-service/app/main.py`):**
  ```python
  @asynccontextmanager
  async def lifespan(app_instance: FastAPI):
      # Runs ONCE before accepting HTTP traffic:
      if get_db not in app_instance.dependency_overrides:
          Base.metadata.create_all(bind=engine)
          with SessionLocal() as db:
              seed_default_slots(db)
      yield  # Server handles requests while paused here
      # Cleanup code would run here on shutdown
  ```

---

## 4. `app.include_router(...)`

* **Import:** Method on `app` (`FastAPI` instance).
* **In Simple Words:** Plugs a modular `APIRouter` (e.g., `auth_router`, `parking_router`) into the root `FastAPI` application so all routes defined in other files become active.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `router` | `APIRouter` | **Required** | The router object containing grouped API endpoints. |
| `prefix` | `str` | `""` | Optional extra URL prefix prepended on top of the router's own prefix. |
| `tags` | `list[str]` | `None` | Optional extra Swagger UI tags applied to all routes in that router. |
| `dependencies` | `Sequence[Depends]` | `None` | Dependencies (like auth checks) applied to every single route in the router. |

* **Returns:** `None`.
* **Project Example (`services/parking-service/app/main.py`):**
  ```python
  app.include_router(parking_router)
  app.include_router(internal_router)
  ```

---

## 5. `app.dependency_overrides`

* **Import:** Built-in dictionary attribute on `FastAPI` (`app.dependency_overrides: dict`).
* **In Simple Words:** A **stunt-double dictionary** used in automated tests. Whenever a route asks for `Depends(original_fn)`, FastAPI checks this dictionary first; if a replacement exists, it calls the test replacement instead of the real production function.

### Usage (Dictionary Key -> Value)

| Component | Type | What it does |
| :--- | :--- | :--- |
| **Key** | `Callable` | The original dependency function (e.g., `get_db`, `get_vehicle_client`, `get_now`). |
| **Value** | `Callable` | The fake/test function to run instead during tests (e.g., `override_get_db`). |

* **Returns:** Mutates FastAPI's internal override mapping.
* **Project Example (`services/parking-service/tests/conftest.py`):**
  ```python
  app.dependency_overrides[get_db] = override_get_db
  app.dependency_overrides[get_vehicle_client] = lambda: fake_vehicle_client
  ```

---

## 6. `@app.exception_handler(...)`

* **Import:** Decorator method on `app` (`FastAPI` instance).
* **In Simple Words:** Registers a **global safety net** for a specific Python exception class. Whenever that exception is raised anywhere in any route or dependency, FastAPI catches it and runs your handler function instead of crashing.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `exc_class_or_status_code` | `type[Exception] \| int` | **Required** | The exception class (e.g. `AppError`, `RequestValidationError`) or HTTP status code (e.g. `404`, `500`) to intercept. |

* **Handler Function Signature:** `async def handler(request: Request, exc: ExcClass) -> Response`
* **Project Example (`services/user-auth-service/app/core/errors.py`):**
  ```python
  @app.exception_handler(AppError)
  async def app_error_handler(request: Request, exc: AppError):
      return JSONResponse(
          status_code=exc.status_code,
          content={"error": {"code": exc.code, "message": exc.message}},
      )
  ```

---

## 7. `RequestValidationError`

* **Import:** `from fastapi.exceptions import RequestValidationError`
* **In Simple Words:** The exception FastAPI **automatically raises** when incoming JSON body, query parameters, path parameters, or headers fail Pydantic validation (e.g. missing required field, invalid email format, wrong data type).

### Key Attributes / Methods on `exc`

| Attribute / Method | Return Type | What it gives you |
| :--- | :--- | :--- |
| `exc.errors()` | `list[dict]` | List of validation error dictionaries detailing which field failed, its location (`body`, `query`), and why. |
| `exc.body` | `Any` | The raw invalid request body that was sent by the client. |

* **Project Example (`services/user-auth-service/app/core/errors.py`):**
  ```python
  @app.exception_handler(RequestValidationError)
  async def validation_error_handler(request: Request, exc: RequestValidationError):
      return JSONResponse(
          status_code=422,
          content={
              "error": {
                  "code": "INVALID_REQUEST",
                  "message": "Request validation failed.",
                  "request_id": _request_id(request),
              }
          },
      )
  ```

---

## 8. `HTTPException`

* **Import:** `from fastapi import HTTPException`
* **In Simple Words:** FastAPI's built-in exception for returning HTTP errors (like `401 Unauthorized`, `403 Forbidden`, `404 Not Found`).

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `status_code` | `int` | **Required** | HTTP error code (e.g., `404`, `401`, `409`). |
| `detail` | `Any` | `None` | Error message or dictionary explaining why the request failed. |
| `headers` | `dict[str, str] \| None` | `None` | Optional extra HTTP headers to include on the error response (e.g. `{"WWW-Authenticate": "Bearer"}`). |

* **Project Example (`services/user-auth-service/app/core/errors.py`):**
  ```python
  from fastapi import HTTPException

  @app.exception_handler(HTTPException)
  async def http_exception_handler(request: Request, exc: HTTPException):
      return JSONResponse(
          status_code=exc.status_code,
          content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "request_id": _request_id(request)}},
      )
  ```

---

## 9. `JSONResponse`

* **Import:** `from fastapi.responses import JSONResponse`
* **In Simple Words:** Manually builds an HTTP response with JSON content, `Content-Type: application/json`, and an exact HTTP status code.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `content` | `Any` | `None` | Python dict or list that gets serialized into JSON. |
| `status_code` | `int` | `200` | HTTP status code sent back to the client. |
| `headers` | `Mapping[str, str] \| None` | `None` | Optional custom HTTP response headers. |
| `media_type` | `str \| None` | `"application/json"` | Response MIME type. |

* **Returns:** A Starlette/FastAPI `JSONResponse` object ready to send over HTTP.
* **Project Example (`services/user-auth-service/app/core/errors.py`):**
  ```python
  return JSONResponse(
      status_code=exc.status_code,
      content={"error": {"code": exc.code, "message": exc.message, "request_id": _request_id(request)}},
  )
  ```
