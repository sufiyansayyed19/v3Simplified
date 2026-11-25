# Microservices, Cross-Service Communication & Concurrency Tutorial — Built From `ParkingSimplified`

> **How to use this tutorial:** We start from the ground up ("What problem do microservices solve?") and build gradually to the exact architecture, inter-service communication rules, idempotency guarantees, and PostgreSQL concurrency locks running inside `ParkingSimplified`. Every new technical term is explained briefly in plain English the first time it appears.

---

## Course Outline (All Root Topics & Subtopics)

1. **Topic 1: From Monolith to Microservices (Foundations)**
   - 1.1 Monolith vs. Microservices — What Changes?
   - 1.2 Bounded Contexts: How We Split `ParkingSimplified` into 4 Services
   - 1.3 Database-per-Service & Why Cross-Database `JOIN`s Are Forbidden
   - 1.4 The Price You Pay (Distributed Failures, No Cross-DB Transactions)
2. **Topic 2: Cross-Service Communication Basics (`httpx` & HTTP Contracts)**
   - 2.1 Synchronous REST Calls vs. Asynchronous Messaging (Queues / Callbacks)
   - 2.2 Why We Use `httpx.Client` With Strict 3-Second Timeouts
   - 2.3 Two Security Patterns: Token Propagation (`Bearer JWT`) vs. M2M (`X-Internal-Service-Token`)
   - 2.4 Mapping Remote Errors Cleanly (`401`, `404` $\rightarrow$ `503 SERVICE_UNAVAILABLE`)
3. **Topic 3: Distributed Data Patterns in `ParkingSimplified`**
   - 3.1 Data Ownership & Snapshot Pattern (`vehicle_*_snapshot` in `bookings`)
   - 3.2 Saga-Style Two-Step Orchestration (`PAYMENT_PENDING` Hold $\rightarrow$ Callback `CONFIRMED`)
   - 3.3 Idempotency: Safe Retries Across Unreliable Networks (`POST /internal/v1/payments` & Callback)
   - 3.4 Dealing With Network Partitions & Late Callbacks (`EXPIRED_NO_RESURRECTION`)
4. **Topic 4: Concurrency Fundamentals (Why Multi-User Systems Break)**
   - 4.1 Sequential vs. Concurrent Requests (What Happens When 10 Employees Click "Book" Together)
   - 4.2 Anatomy of a Race Condition (Time-of-Check to Time-of-Use / Double-Booking)
   - 4.3 Why Python Variables & `threading.Lock()` Fail Across Microservice Workers
5. **Topic 5: Database Concurrency Control in `ParkingSimplified`**
   - 5.1 Moving Synchronization to PostgreSQL (`SELECT ... FOR UPDATE`)
   - 5.2 Locking Parent Inventory (`parking_slots`) Instead of Non-Existent `bookings` Rows
   - 5.3 Transaction Boundary Discipline: Commit Before Calling Other Services over HTTP!
   - 5.4 Preventing Self-Contention (`USER_BOOKING_OVERLAP`) Under Concurrent Double-Clicks
   - 5.5 Pessimistic Locking (What We Used) vs. Optimistic Locking & Redis Distributed Locks
6. **Topic 6: Testing Real Multi-Service Communication & Race Conditions**
   - 6.1 Unit Mocking (`FakeVehicleClient`) vs. Live Multi-Process E2E (`test_e2e_journey.py`)
   - 6.2 Simulating True Concurrent Race Conditions With `threading.Barrier` (`test_pg_concurrency.py`)

---

## Topic 1: From Monolith to Microservices (Foundations)

**Subtopics in this section:**
- 1.1 Monolith vs. Microservices — What Changes?
- 1.2 Bounded Contexts: How We Split `ParkingSimplified` into 4 Services
- 1.3 Database-per-Service & Why Cross-Database `JOIN`s Are Forbidden
- 1.4 The Price You Pay (Distributed Failures, No Cross-DB Transactions)

### 1.1 Monolith vs. Microservices — What Changes?
* **Monolith**: One single FastAPI application and one single database containing `users`, `vehicles`, `parking_slots`, `bookings`, and `payments` together. Simple at first, **but** if payment code has a memory leak or needs a different scaling schedule, the whole platform restarts together.
* **Microservices Architecture**: Splitting one big backend into small, independent programs (**services**), each owning one business domain, running on its own port (`8001`–`8004`), and talking over HTTP/REST.

### 1.2 Bounded Contexts: How We Split `ParkingSimplified` into 4 Services
* **Bounded Context**: A domain boundary where each service owns a clear set of data and rules without overlapping another service's job:

| Service | Port | Owns | Does **Not** Know About |
| :--- | :---: | :--- | :--- |
| **`user-auth-service`** | `8001` | Corporate email OTPs, users, JWT minting | Vehicles, parking slots, bookings, payments |
| **`vehicle-service`** | `8002` | Employee vehicles, plate normalization, EV flags | OTPs, parking availability, payments |
| **`parking-service`** | `8003` | 100 parking slots, rules, slot holds, bookings | OTPs, card/UPI details |
| **`payment-service`** | `8004` | Payment records, `UPI`/`CARD`/`WALLET` processing | Slot numbers, license plates, OTPs |

### 1.3 Database-per-Service & Why Cross-Database `JOIN`s Are Forbidden
Each of our 4 services owns its own isolated PostgreSQL database (`user_db`, `vehicle_db`, `parking_db`, `payment_db`) with `REVOKE CONNECT ... FROM PUBLIC`.
* **Why forbid `parking-service` from reading `vehicle_db` directly?**
  If `parking-service` runs `SELECT ... FROM vehicle_db.vehicles` directly, then `vehicle-service` can never rename a column or move to MongoDB without breaking `parking-service`! Instead, services talk **only through documented APIs**.

### 1.4 The Price You Pay (Distributed Failures, No Cross-DB Transactions)
When everything moved from 1 database into 4 services, two hard problems appeared:
1. **Network Calls Can Fail or Hang**: Calling `vehicle-service` over HTTP takes milliseconds (or fails if port `8002` is down), unlike an in-memory Python function call.
2. **No Single `BEGIN ... COMMIT` Across Two Databases**: PostgreSQL cannot roll back a `Booking` in `parking_db` and a `Payment` in `payment_db` in one atomic SQL transaction. Topic 3 shows exactly how we solve both!

---

## Topic 2: Cross-Service Communication Basics (`httpx` & HTTP Contracts)

**Subtopics in this section:**
- 2.1 Synchronous REST Calls vs. Asynchronous Messaging (Queues / Callbacks)
- 2.2 Why We Use `httpx.Client` With Strict 3-Second Timeouts
- 2.3 Two Security Patterns: Token Propagation (`Bearer JWT`) vs. M2M (`X-Internal-Service-Token`)
- 2.4 Mapping Remote Errors Cleanly (`401`, `404` $\rightarrow$ `503 SERVICE_UNAVAILABLE`)

### 2.1 Synchronous REST Calls vs. Asynchronous Messaging (Queues / Callbacks)
Microservices talk in two styles:
1. **Synchronous Request-Response (HTTP/REST)**: Caller sends an HTTP request and **waits** for the answer before continuing.
   * *Where we use it*: `parking-service` calling `vehicle-service` (`GET /api/v1/vehicles/{id}`) before reserving a slot, and calling `payment-service` (`POST /internal/v1/payments`) to create a pending payment ID.
2. **Asynchronous Event / Callback Pattern**: One service finishes work later and **pushes** the outcome back via a webhook/callback or a message broker (Kafka/RabbitMQ).
   * *Where we use it*: When the employee pays (`POST /api/v1/payments/{id}/process`), `payment-service` delivers the result back to `parking-service` at `POST /internal/v1/bookings/{id}/payment-result` via `ParkingCallbackClient`.

*(Note: Production teams often replace HTTP callbacks with a message broker like Kafka or RabbitMQ + Outbox pattern so callbacks retry even if the receiver is temporarily offline; our HTTP callback achieves the same decoupled flow cleanly without extra broker infrastructure.)*

### 2.2 Why We Use `httpx.Client` With Strict 3-Second Timeouts
Look at `services/parking-service/app/services/clients.py` and `services/payment-service/app/services/parking_callback.py`:
```python
with httpx.Client(timeout=3.0) as client:
    resp = client.get(url, headers=headers)
```
* **`httpx`**: Modern Python HTTP client library (replaces older `requests`, supports both sync `Client` and async `AsyncClient`, and powers FastAPI's `TestClient`).
* **Why `timeout=3.0` is mandatory**: If you call `httpx.get(url)` with no timeout and `vehicle-service` hangs, all Uvicorn worker threads in `parking-service` freeze waiting forever (**Cascading Failure**!). A strict 3-second timeout fails fast so other endpoints like `GET /health` and `GET /bookings` stay responsive.

### 2.3 Two Security Patterns: Token Propagation (`Bearer JWT`) vs. M2M (`X-Internal-Service-Token`)
Notice how `parking-service` uses **two different authentication headers** depending on which service it calls:

1. **User Token Propagation (`parking-service` $\rightarrow$ `vehicle-service`)**:
   ```python
   # From services/parking-service/app/services/clients.py
   headers = {"Authorization": f"Bearer {bearer_token}"}
   resp = client.get(f"{settings.VEHICLE_SERVICE_URL}/api/v1/vehicles/{vehicle_id}", headers=headers)
   ```
   * **Why?** `vehicle-service` exposes a user-facing `GET /api/v1/vehicles/{id}` endpoint that checks ownership (`Vehicle.user_id == jwt_user_id`). Forwarding the user's exact Bearer JWT means `vehicle-service` proves the caller actually owns that vehicle!
2. **Machine-to-Machine (`X-Internal-Service-Token`)**:
   ```python
   # Used in both PaymentServiceClient and ParkingCallbackClient
   headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
   ```
   * **Why?** Creating a payment record (`/internal/v1/payments`) or marking a booking `"CONFIRMED"` (`/internal/v1/bookings/{id}/payment-result`) must **never** be callable directly by an end user's browser! Only trusted peer microservices know `INTERNAL_SERVICE_TOKEN`.

### 2.4 Mapping Remote Errors Cleanly (`401`, `404` $\rightarrow$ `503 SERVICE_UNAVAILABLE`)
When `parking-service` calls `vehicle-service`, look at how `VehicleServiceClient.get_owned_vehicle()` translates HTTP responses cleanly:
```python
# From services/parking-service/app/services/clients.py
except httpx.HTTPError:
    raise AppError(503, "VEHICLE_SERVICE_UNAVAILABLE", "Vehicle Service is currently unavailable.")

if resp.status_code == 404:
    raise AppError(404, "VEHICLE_NOT_FOUND", "Vehicle not found or inactive.")
if resp.status_code == 401:
    raise AppError(401, "UNAUTHENTICATED", "Authentication rejected by Vehicle Service.")
if resp.status_code != 200:
    raise AppError(503, "VEHICLE_SERVICE_UNAVAILABLE", "Failed to validate vehicle with Vehicle Service.")
```
* **Graceful Degradation**: Never let a raw `httpx.ConnectError` crash with an ugly `500`. Catching `httpx.HTTPError` turns network outages into an explicit **`503 Service Unavailable`** JSON error telling the user exactly which downstream service is down.
* Also note the **Resilient Callback** in `ParkingCallbackClient.deliver_payment_result()`: it catches `httpx.HTTPError` and returns `False` instead of crashing after `payment-service` has already committed the user's `SUCCESS` payment!

---

## Topic 3: Distributed Data Patterns in `ParkingSimplified`

**Subtopics in this section:**
- 3.1 Data Ownership & Snapshot Pattern (`vehicle_*_snapshot` in `bookings`)
- 3.2 Saga-Style Two-Step Orchestration (`PAYMENT_PENDING` Hold $\rightarrow$ Callback `CONFIRMED`)
- 3.3 Idempotency: Safe Retries Across Unreliable Networks (`POST /internal/v1/payments` & Callback)
- 3.4 Dealing With Network Partitions & Late Callbacks (`EXPIRED_NO_RESURRECTION`)

### 3.1 Data Ownership & Snapshot Pattern (`vehicle_*_snapshot` in `bookings`)
* **Anti-Pattern (Chatty Microservices)**: Imagine if `GET /api/v1/parking/bookings` fetched 20 bookings from `parking_db` and then made 20 HTTP calls to `vehicle-service` just to display license plates! Slow, fragile, and breaks completely if a user later deletes their vehicle.
* **Solution — Snapshot Pattern**: When `create_booking()` validates the vehicle **once** via `VehicleServiceClient`, it copies the vehicle's plate, type, and EV flag directly onto the `Booking` row:
  ```python
  vehicle_number_snapshot=vehicle.vehicle_number,
  vehicle_type_snapshot=vehicle.vehicle_type,
  is_ev_snapshot=vehicle.is_ev,
  ```
  Now `GET /bookings` works with **zero network calls** to `vehicle-service` and historical booking receipts remain accurate forever!

### 3.2 Saga-Style Two-Step Orchestration (`PAYMENT_PENDING` Hold $\rightarrow$ Callback `CONFIRMED`)
* **Saga Pattern**: A way to manage a business workflow that spans multiple independent databases **without** a distributed two-phase lock:
  1. **Step 1 (Provisional Reservation)**: `parking-service` creates `Booking(status="PAYMENT_PENDING", hold_expires_at=now + 5 min)` and asks `payment-service` to create `Payment(status="PENDING")`.
  2. **Step 2 (Completion or Compensating Expiry)**:
     * If user pays within 5 minutes $\rightarrow$ `payment-service` marks `Payment = SUCCESS` and calls `parking-service` $\rightarrow$ `Booking` transitions to `CONFIRMED`.
     * If payment fails or 5 minutes pass $\rightarrow$ `Booking` becomes `EXPIRED` (compensating action releasing the slot automatically!).

### 3.3 Idempotency: Safe Retries Across Unreliable Networks (`POST /internal/v1/payments` & Callback)
* **Idempotency**: Calling the exact same API multiple times produces the **same final state** without creating duplicate records or charging twice!
  Why does this matter? Over networks, a request might succeed on the server, then drop its response before reaching the caller—prompting a retry.
* **How `payment-service` handles duplicate `create_internal_payment()` (`payments.py`)**:
  * `Payment.booking_id` has a `UNIQUE` constraint.
  * If a `Payment` already exists for `booking_id` with identical `(user_id, amount)`, it returns `200 OK` with the existing `payment_id` instead of creating a 2nd payment.
  * If `user_id` or `amount` differs (tampered/conflicting retry), it rejects with `409 PAYMENT_REQUEST_CONFLICT`.
* **How `parking-service` handles duplicate `apply_payment_result()` (`internal.py`)**:
  * If `booking.status == "CONFIRMED"` already, it returns `200 OK` with `result="ALREADY_APPLIED"` instead of throwing an error.

### 3.4 Dealing With Network Partitions & Late Callbacks (`EXPIRED_NO_RESURRECTION`)
What if an employee opens the payment page at `10:00`, walks away for 6 minutes (hold expires at `10:05`), and meanwhile another employee legitimately books that freed slot—then a delayed `SUCCESS` callback arrives at `10:06`?
* Inside `apply_payment_result()` (`services/parking-service/app/api/internal.py`):
  ```python
  hold_expired = booking.hold_expires_at is None or as_utc(booking.hold_expires_at) <= now_utc
  if hold_expired or payload.status == "FAILED":
      booking.status = "EXPIRED"
  ```
  It **refuses to resurrect** an expired hold into `CONFIRMED` (returning `EXPIRED_NO_RESURRECTION`), protecting the slot against double allocation!

---

## Topic 4: Concurrency Fundamentals (Why Multi-User Systems Break)

**Subtopics in this section:**
- 4.1 Sequential vs. Concurrent Requests (What Happens When 10 Employees Click "Book" Together)
- 4.2 Anatomy of a Race Condition (Time-of-Check to Time-of-Use / Double-Booking)
- 4.3 Why Python Variables & `threading.Lock()` Fail Across Microservice Workers

### 4.1 Sequential vs. Concurrent Requests (What Happens When 10 Employees Click "Book" Together)
When you test manually in Swagger UI, requests arrive **one after another** (sequentially).
In real production at 08:59 AM, **10 employees click "Book EV Bike Slot" at the exact same millisecond** (`T = 0.000s`). Uvicorn runs all 10 requests **concurrently** across worker threads!

### 4.2 Anatomy of a Race Condition (Time-of-Check to Time-of-Use / Double-Booking)
* **Race Condition (TOCTOU — Time-of-Check to Time-of-Use)**: A bug where two concurrent requests check a shared condition (`"Is slot B40 free?"`), both see `"Yes!"` before either writes, and both proceed—causing **corrupted state**:

```text
Time     Thread A (User 1)                         Thread B (User 2)
0.001s   SELECT occupied slots -> B40 is FREE!
0.002s                                             SELECT occupied slots -> B40 is ALSO FREE!
0.003s   INSERT booking (slot = B40) -> COMMIT!
0.004s                                             INSERT booking (slot = B40) -> COMMIT!  <-- DOUBLE BOOKED!
```

### 4.3 Why Python Variables & `threading.Lock()` Fail Across Microservice Workers
A beginner's instinct is to put `lock = threading.Lock()` in `parking.py`. **Why does that fail in real deployments?**
1. In production, you run multiple Uvicorn worker **processes** (`--workers 4`) or multiple Docker containers/servers behind a load balancer. Each OS process has its **own separate memory**—Process 2 cannot see a `threading.Lock()` sitting inside Process 1!
2. Even in a single process, locking inside Python doesn't protect if a migration/admin job or another service instance writes to `parking_db`.
* **Golden Rule**: Concurrency control for database state belongs **in the shared database** (or a shared distributed lock), never in local Python memory!

---

## Topic 5: Database Concurrency Control in `ParkingSimplified`

**Subtopics in this section:**
- 5.1 Moving Synchronization to PostgreSQL (`SELECT ... FOR UPDATE`)
- 5.2 Locking Parent Inventory (`parking_slots`) Instead of Non-Existent `bookings` Rows
- 5.3 Transaction Boundary Discipline: Commit Before Calling Other Services over HTTP!
- 5.4 Preventing Self-Contention (`USER_BOOKING_OVERLAP`) Under Concurrent Double-Clicks
- 5.5 Pessimistic Locking (What We Used) vs. Optimistic Locking & Redis Distributed Locks

### 5.1 Moving Synchronization to PostgreSQL (`SELECT ... FOR UPDATE`)
Look at `create_booking()` in `services/parking-service/app/api/v1/parking.py`:
```python
slot_stmt = (
    select(ParkingSlot)
    .where(
        ParkingSlot.vehicle_type == vehicle.vehicle_type,
        ParkingSlot.is_charging_enabled.is_(payload.requires_charging),
    )
    .order_by(ParkingSlot.slot_number.asc())
)
if db.bind is not None and db.bind.dialect.name == "postgresql":
    slot_stmt = slot_stmt.with_for_update()

compatible_slots = list(db.execute(slot_stmt).scalars().all())
```
**Now trace the exact same 10-user rush WITH `.with_for_update()`:**
```text
Time     Thread A (User 1)                         Thread B (User 2)
0.001s   SELECT ... FROM parking_slots FOR UPDATE
         (Acquires PostgreSQL row locks!)
0.002s                                             SELECT ... FROM parking_slots FOR UPDATE
                                                   --> PAUSED BY POSTGRESQL (waits for A)
0.003s   Checks bookings -> picks B40
         INSERT booking (B40) -> COMMIT!
         (Releases PostgreSQL row locks!)
0.004s                                             --> WAKES UP! Reads fresh committed data:
                                                   Sees B40 is OCCUPIED! Returns 409 NO_PARKING_CAPACITY!
```

### 5.2 Locking Parent Inventory (`parking_slots`) Instead of Non-Existent `bookings` Rows
**Why lock `parking_slots` instead of `bookings`?**
When zero bookings exist for `10:00–11:00`, `SELECT ... FROM bookings WHERE ... FOR UPDATE` finds **0 rows to lock**—so two concurrent threads would both lock 0 rows and both insert!
By locking the **compatible `parking_slots` rows** (`C51`–`C60` or `B36`–`B40`), which **always exist** in PostgreSQL, PostgreSQL cleanly serializes every booking attempt for that vehicle/charging pool!
*(And because `ORDER BY ParkingSlot.slot_number.asc()` is deterministic, all concurrent transactions lock rows in the exact same order, avoiding **Deadlocks**!)*

### 5.3 Transaction Boundary Discipline: Commit Before Calling Other Services over HTTP!
Look closely at lines 234–246 of `services/parking-service/app/api/v1/parking.py`:
1. Acquire `FOR UPDATE` locks on `parking_slots`
2. Insert `Booking(status="PAYMENT_PENDING")`
3. **`db.commit()` FIRST** (releases PostgreSQL locks immediately!)
4. **THEN** call `payment_client.create_payment(...)` over HTTP
5. Save `booking.payment_id = payment_id` and `db.commit()`.

* **Why never make HTTP calls while holding a database lock?** If `payment-service` takes 3 seconds to respond while you hold `FOR UPDATE` locks on `parking_slots`, **every other employee trying to book a parking spot freezes for 3 seconds!** Committing the hold first keeps database locks held for mere milliseconds.

### 5.4 Preventing Self-Contention (`USER_BOOKING_OVERLAP`) Under Concurrent Double-Clicks
What if **one user** impatiently clicks "Book" 4 times in 1 millisecond (or uses 4 browser tabs)?
Because `slot_stmt.with_for_update()` runs **before** checking `user_overlap`:
1. Request 1 locks compatible slots, checks `user_overlap` (none), inserts Booking 1, and commits.
2. Requests 2, 3, and 4 wake up one by one **after** Request 1 commits, immediately see Booking 1 in `user_overlap`, and return `409 USER_BOOKING_OVERLAP`!

### 5.5 Pessimistic Locking (What We Used) vs. Optimistic Locking & Redis Distributed Locks
| Technique | How It Works | Trade-Offs | Best Fit |
| :--- | :--- | :--- | :--- |
| **PostgreSQL `FOR UPDATE` (Pessimistic — What We Used)** | Database blocks competing transactions on the slot rows until commit. | Zero wasted retries; works across multiple Uvicorn workers with zero extra servers. | Contended shared inventory (last few parking slots). |
| **Optimistic Locking (Version Column)** | Read `version = 1`; update `WHERE version = 1`; retry if `0` rows updated. | Great when conflicts are rare; ugly retry loops under high contention. | Editing user profiles / documents. |
| **Redis Distributed Lock (`Redlock`)** | Acquire lock key in external Redis cluster before DB write. | Adds Redis infrastructure dependency & lock-expiry lease tuning edge cases. | Multi-database/non-SQL resource locking. |

---

## Topic 6: Testing Real Multi-Service Communication & Race Conditions

**Subtopics in this section:**
- 6.1 Unit Mocking (`FakeVehicleClient`) vs. Live Multi-Process E2E (`test_e2e_journey.py`)
- 6.2 Simulating True Concurrent Race Conditions With `threading.Barrier` (`test_pg_concurrency.py`)

### 6.1 Unit Mocking (`FakeVehicleClient`) vs. Live Multi-Process E2E (`test_e2e_journey.py`)
* **Fast Unit Tests (`services/parking-service/tests/test_parking.py`)**: Swap `VehicleServiceClient` and `PaymentServiceClient` with `FakeVehicleClient` / `FakePaymentClient` via `app.dependency_overrides` to test business rules in milliseconds.
* **True Multi-Process E2E Test (`tests/test_e2e_journey.py`)**:
  1. Uses `subprocess.Popen` to launch **all 4 real Uvicorn servers** simultaneously on ports `18001`–`18004` connected to all 4 real PostgreSQL databases!
  2. Polls `/health` until every service is ready (`_wait_for_health`).
  3. Runs a real `httpx.Client` user journey: register EV car (`:18002`) $\rightarrow$ check availability (`:18003` calling `:18002`) $\rightarrow$ create booking (`:18003` calling `:18002` & `:18004`) $\rightarrow$ process UPI payment (`:18004` calling callback back to `:18003`) $\rightarrow$ verify booking is `"CONFIRMED"`, then cancel and verify `"CANCELLED"`.

### 6.2 Simulating True Concurrent Race Conditions With `threading.Barrier` (`test_pg_concurrency.py`)
If you just run a `for` loop calling an endpoint 10 times, requests run sequentially—not concurrently!
* **`threading.Barrier(10)`**: A synchronization gate that pauses all 10 threads at `barrier.wait()` until all 10 are lined up, then releases **all 10 simultaneously** into `POST /api/v1/parking/bookings`!

Look at what `tests/test_pg_concurrency.py` verifies against real `parking_db`:
1. **`test_pg_ev_bike_slot_race_no_double_allocation()`**: 10 threads race simultaneously for the 5 EV bike slots (`B36`–`B40`) $\rightarrow$ proves **exactly 5 return `201`** (with 5 distinct `slot_number`s!) and **exactly 5 return `409 NO_PARKING_CAPACITY`**.
2. **`test_pg_same_user_simultaneous_overlap_serialized()`**: 1 user fires 4 overlapping booking requests at the exact same millisecond $\rightarrow$ proves **exactly 1 returns `201`** and **3 return `409 USER_BOOKING_OVERLAP`**.
