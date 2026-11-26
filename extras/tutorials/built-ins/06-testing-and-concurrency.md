# Topic 6: Testing & Concurrency Built-ins (`tests/` & `services/*/tests/`)

This file explains every testing, in-memory pooling, threading, and process-launching built-in used across unit, concurrency, and end-to-end tests, with real code examples.

**Contents:**
1. [`TestClient(...)`](#1-testclient)
2. [`@pytest.fixture(...)`](#2-pytestfixture)
3. [`StaticPool`](#3-staticpool)
4. [`threading.Barrier(...)`](#4-threadingbarrier)
5. [`ThreadPoolExecutor(...)`](#5-threadpoolexecutor)
6. [`subprocess.Popen(...)`](#6-subprocesspopen)

---

## 1. `TestClient(...)`

* **Import:** `from fastapi.testclient import TestClient`
* **In Simple Words:** Executes real HTTP requests (`client.get`, `client.post`, `client.put`, `client.delete`) directly against your FastAPI `app` in memory without opening a TCP network port.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `app` | `FastAPI` | **Required** | Your FastAPI application instance. |
| `base_url` | `str` | `"http://testserver"` | Base URL for relative request paths. |
| `raise_server_exceptions` | `bool` | `True` | Re-raises unhandled Python exceptions directly in pytest tracebacks. |

* **Returns:** A `TestClient` instance.
* **Project Example (`services/user-auth-service/tests/test_auth.py`):**
  ```python
  with TestClient(app) as client:
      res = client.post("/api/v1/auth/company/send-code", json={"email": "emp@corp.com"})
      assert res.status_code == 200
  ```

---

## 2. `@pytest.fixture(...)`

* **Import:** `import pytest`
* **In Simple Words:** Defines reusable setup and teardown functions injected automatically into test functions by matching parameter names.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `scope` | `Literal["function", "class", "module", "session"]` | `"function"` | How often the fixture runs (`"function"` creates fresh state per test; `"session"` runs once for the whole test run). |
| `autouse` | `bool` | `False` | If `True`, runs automatically for every test without needing to list it in test parameters. |

* **Project Example (`services/parking-service/tests/conftest.py`):**
  ```python
  @pytest.fixture()
  def client():
      Base.metadata.create_all(bind=test_engine)
      with TestClient(app) as c:
          yield c
      Base.metadata.drop_all(bind=test_engine)
  ```

---

## 3. `StaticPool`

* **Import:** `from sqlalchemy.pool import StaticPool`
* **In Simple Words:** A SQLAlchemy connection pool that keeps **one single connection** open forever. Essential for `sqlite:///:memory:` unit tests because SQLite destroys an in-memory database the instant its last connection closes.
* **Project Example (`services/parking-service/tests/conftest.py`):**
  ```python
  test_engine = create_engine(
      "sqlite:///:memory:",
      connect_args={"check_same_thread": False},
      poolclass=StaticPool,
  )
  ```

---

## 4. `threading.Barrier(...)`

* **Import:** `import threading`
* **In Simple Words:** A synchronization starting gate for threads. All threads pause at `barrier.wait()` until the `parties`-th thread arrives, then all release at the exact same microsecond to trigger genuine concurrent race conditions.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `parties` | `int` | **Required** | Exact number of threads that must call `barrier.wait()` before all threads are released simultaneously. |
| `timeout` | `float \| None` | `None` | Optional max seconds to wait before raising `BrokenBarrierError`. |

* **Returns:** A `Barrier` instance.
* **Project Example (`tests/test_pg_concurrency.py`):**
  ```python
  barrier = threading.Barrier(num_workers)

  def book_for_user(user_id):
      barrier.wait()  # All threads fire simultaneously after reaching here
      return client.post("/api/v1/parking/bookings", ...)
  ```

---

## 5. `ThreadPoolExecutor(...)`

* **Import:** `from concurrent.futures import ThreadPoolExecutor`
* **In Simple Words:** Manages a pool of OS worker threads to execute functions concurrently.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `max_workers` | `int \| None` | Auto | Maximum number of threads running in parallel (e.g. `max_workers=10`). |

* **Project Example (`tests/test_pg_concurrency.py`):**
  ```python
  with ThreadPoolExecutor(max_workers=num_workers) as pool:
      results = list(pool.map(book_for_user, user_ids))
  ```

---

## 6. `subprocess.Popen(...)`

* **Import:** `import subprocess`
* **In Simple Words:** Launches an external OS child process (such as `uvicorn app.main:app --port 8003`) in the background without blocking Python.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `args` | `list[str]` | **Required** | Command and arguments (e.g. `[python_exe, "-m", "uvicorn", "app.main:app", "--port", "8003"]`). |
| `cwd` | `str \| Path` | `None` | Working directory for the child process. |
| `env` | `dict[str, str]` | `None` | Environment variables passed to the child process. |
| `stdout` / `stderr` | `int \| IO` | `None` | Redirects process output (`subprocess.PIPE` or `subprocess.DEVNULL`). |

* **Project Example (`tests/test_e2e_journey.py`):**
  ```python
  proc = subprocess.Popen(
      [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
      cwd=str(service_dir),
      env=env,
  )
  # Later during teardown:
  proc.terminate()
  proc.wait(timeout=5)
  ```
