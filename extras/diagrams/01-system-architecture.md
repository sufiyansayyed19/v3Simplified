# System Architecture Diagram — Corporate Parking Platform (`ParkingSimplified`)

> **Diagram Standard:** Enterprise C4-Container / Layered System Architecture showing Clients, Security Boundaries, Microservices, Sync/Async Inter-Service Contracts, and Isolated PostgreSQL Databases.

---

## 1. Full System Architecture (Layered Blueprint)

```mermaid
flowchart TB
    %% ==================== CLIENT & EXTERNAL TIER ====================
    subgraph ClientTier["Client & Actor Layer"]
        User(["Corporate Employee\n(@company.com)\nSwagger UI / REST Client / App"])
    end

    subgraph ExternalTier["Simulated External Adapters (Local Dev)"]
        EmailOut["ConsoleEmailSender\n(OTP Delivery Channel)"]
        PaySim["Simulated Payment Engine\n(UPI / CARD / WALLET)"]
    end

    %% ==================== MICROSERVICES APPLICATION TIER ====================
    subgraph ServiceTier["Microservices Application Tier — Python 3.13 / FastAPI / Uvicorn"]
        direction LR

        AuthSvc["User & Auth Service (:8001)\n- POST /api/v1/auth/company/send-code\n- POST /api/v1/auth/company/verify\n- GET /api/v1/users/me\n[Mints HS256 JWT | CSPRNG OTP]"]

        VehSvc["Vehicle Service (:8002)\n- POST / GET /api/v1/vehicles\n- GET / PUT / DELETE /api/v1/vehicles/:id\n[Local JWT Verify | Plate Norm | Soft Delete]"]

        ParkSvc["Parking Service (:8003)\n- GET /api/v1/parking/availability\n- POST / GET /bookings & /cancel\n- POST /internal/v1/.../payment-result\n[Asia/Kolkata Rules | FOR UPDATE Lock | Snapshots]"]

        PaySvc["Payment Service (:8004)\n- POST /internal/v1/payments\n- POST /api/v1/payments/:id/process\n- GET /api/v1/payments/:id\n[Idempotent Create | Expiry & Replay Guards]"]
    end

    %% ==================== DATA PERSISTENCE TIER ====================
    subgraph DataTier["Persistence Tier — PostgreSQL 15+ (Database-per-Service Isolation)"]
        direction LR
        UserDB[("user_db\nRole: user_auth_user\n- users\n- verification_codes")]
        VehDB[("vehicle_db\nRole: vehicle_user\n- vehicles")]
        ParkDB[("parking_db\nRole: parking_user\n- parking_slots (100)\n- bookings\n[Alembic Managed]")]
        PayDB[("payment_db\nRole: payment_user\n- payments")]
    end

    %% ==================== CLIENT -> SERVICE FLOWS ====================
    User -->|"1. HTTPS / REST\nOTP Login & Profile"| AuthSvc
    User -->|"2. HTTPS / REST\nAuthorization: Bearer JWT"| VehSvc
    User -->|"3. HTTPS / REST\nAuthorization: Bearer JWT"| ParkSvc
    User -->|"4. HTTPS / REST\nAuthorization: Bearer JWT"| PaySvc

    %% ==================== EXTERNAL ADAPTER LINKS ====================
    AuthSvc -.->|"Prints 6-Digit OTP\n(5-min TTL)"| EmailOut
    EmailOut -.->|"OTP Verification Code"| User
    PaySvc ---|"Processes Simulated\nUPI / CARD / WALLET"| PaySim

    %% ==================== INTER-SERVICE COMMUNICATION ====================
    ParkSvc -->|"Sync HTTP GET (3s timeout)\nForwarded Bearer JWT"| VehSvc
    ParkSvc -->|"Sync HTTP POST (3s timeout)\nX-Internal-Service-Token"| PaySvc
    PaySvc -.->|"Internal Callback POST (3s timeout)\nX-Internal-Service-Token"| ParkSvc

    %% ==================== SERVICE -> ISOLATED DB LINKS ====================
    AuthSvc -->|"SQLAlchemy 2.0 / psycopg3\n(Isolated Connect)"| UserDB
    VehSvc -->|"SQLAlchemy 2.0 / psycopg3\n(Isolated Connect)"| VehDB
    ParkSvc -->|"SQLAlchemy 2.0 / psycopg3\nSELECT ... FOR UPDATE"| ParkDB
    PaySvc -->|"SQLAlchemy 2.0 / psycopg3\n(Isolated Connect)"| PayDB
```

---

## 2. Security Boundaries & Cross-Service Trust Topology

```mermaid
flowchart LR
    Client["Employee Client"]
    Auth["User/Auth Service\n(:8001)"]
    Veh["Vehicle Service\n(:8002)"]
    Park["Parking Service\n(:8003)"]
    Pay["Payment Service\n(:8004)"]

    Client -->|"Unauthenticated\n(@company.com OTP)"| Auth
    Auth -- "Issues Signed HS256 JWT\n(sub=user_id, exp=60m)" --> Client

    subgraph ZeroTrustLocal["Local Stateless JWT Verification (Shared JWT_SECRET_KEY)"]
        Veh
        Park
        Pay
    end

    Client -->|"Bearer JWT"| Veh
    Client -->|"Bearer JWT"| Park
    Client -->|"Bearer JWT"| Pay

    Park -->|"User-Scoped Delegation\n(Forwarded Bearer JWT)"| Veh
    Park <-->|"M2M Trust Boundary\n(X-Internal-Service-Token)"| Pay
```

---

## 3. Architectural Components Summary

| Layer | Component | Responsibility & Key Mechanism |
| :--- | :--- | :--- |
| **Client Layer** | Employee / API Consumer | Calls public `/api/v1/*` endpoints directly on ports `8001`–`8004` using `Authorization: Bearer <JWT>`. |
| **Identity & Auth** | `user-auth-service` (`:8001`) | Restricts login to `@company.com`, generates CSPRNG 6-digit OTPs, provisions users lazily, and mints HS256 JWTs. |
| **Vehicle Registry** | `vehicle-service` (`:8002`) | Verifies JWT locally, normalizes license plates (`KA01AB1234`), prevents active duplicates, and uses soft deletes (`is_active=False`). |
| **Booking Core** | `parking-service` (`:8003`) | Enforces `Asia/Kolkata` facility rules, locks compatible slots via PostgreSQL `SELECT ... FOR UPDATE`, snapshots vehicle info, and expires 5-minute holds lazily. |
| **Payment Engine** | `payment-service` (`:8004`) | Creates idempotent pending payments, simulates `UPI`/`CARD`/`WALLET` settlement, blocks double/expired payments, and notifies `parking-service`. |
| **Data Layer** | 4 Isolated PostgreSQL DBs | Enforces Database-per-Service (`REVOKE CONNECT ... FROM PUBLIC`); zero cross-database SQL `JOIN`s or foreign keys. |
