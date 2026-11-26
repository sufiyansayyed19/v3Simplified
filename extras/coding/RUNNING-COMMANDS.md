# Running Commands Guide (PowerShell & Bash)

All copy-pasteable commands for setup, database creation, starting the 4 microservices, and running tests.

---

## 1. Port & Service Reference

| Service | Port | Directory | Swagger UI |
| :--- | :---: | :--- | :--- |
| **User/Auth Service** | `8001` | `services/user-auth-service/` | `http://127.0.0.1:8001/docs` |
| **Vehicle Service** | `8002` | `services/vehicle-service/` | `http://127.0.0.1:8002/docs` |
| **Parking Service** | `8003` | `services/parking-service/` | `http://127.0.0.1:8003/docs` |
| **Payment Service** | `8004` | `services/payment-service/` | `http://127.0.0.1:8004/docs` |

---

## 2. Virtual Environment Setup

```powershell
# Create virtual environment (one-time)
python -m venv .venv

# Install dependencies
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 3. Database Initialization (PostgreSQL)

Run `scripts/init_postgres.sql` once as the PostgreSQL superuser (`postgres`) to create the 4 isolated databases (`user_db`, `vehicle_db`, `parking_db`, `payment_db`) and roles.

```powershell
psql -U postgres -f scripts/init_postgres.sql
```

> **Automatic Startup + Alembic Demonstration:** Each microservice automatically creates its own tables on startup using `Base.metadata.create_all(bind=engine)`, and `parking-service` automatically seeds all 100 parking slots (`C01–C60`, `B01–B40`) when `parking_slots` is empty. In addition, `parking-service` includes an **Alembic** migration setup (`services/parking-service/alembic/`) to demonstrate database schema versioning (`upgrade` / `downgrade`):
> ```powershell
> cd services\parking-service
> ..\..\.venv\Scripts\python.exe -m alembic upgrade head
> ..\..\.venv\Scripts\python.exe -m alembic current
> cd ..\..
> ```

---

## 4. Starting the 4 Microservices

### Option A: Start All 4 Services with 1 Script
```powershell
.\scripts\start_all.ps1
```

### Option B: Start Services Individually
```powershell
# Terminal 1 — User/Auth Service (Port 8001)
cd services\user-auth-service
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001 --reload

# Terminal 2 — Vehicle Service (Port 8002)
cd services\vehicle-service
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8002 --reload

# Terminal 3 — Parking Service (Port 8003)
cd services\parking-service
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8003 --reload

# Terminal 4 — Payment Service (Port 8004)
cd services\payment-service
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8004 --reload
```

---

## 5. Running Tests

### Run All Test Suites
```powershell
.\scripts\run_all_tests.ps1
```

### Run Individual Suites
```powershell
.\.venv\Scripts\python.exe -m pytest services/user-auth-service/tests/test_auth.py -v
.\.venv\Scripts\python.exe -m pytest services/vehicle-service/tests/test_vehicles.py -v
.\.venv\Scripts\python.exe -m pytest services/parking-service/tests/test_parking.py -v
.\.venv\Scripts\python.exe -m pytest services/parking-service/tests/test_internal.py -v
.\.venv\Scripts\python.exe -m pytest services/payment-service/tests/test_payments.py -v
.\.venv\Scripts\python.exe -m pytest tests/test_pg_concurrency.py -v
.\.venv\Scripts\python.exe -m pytest tests/test_e2e_journey.py -v
```
