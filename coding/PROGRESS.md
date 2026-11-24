# Corporate Parking Reservation System — Coding Progress

> Master tracker for the simplified 4-service architecture.

## Service Map & Local Ports

| Component | Path | Local Port | PostgreSQL DB | DB Role | Tables | Schema Management |
|---|---|---:|---|---|---|---|
| **User/Auth Service** | `services/user-auth-service/` | `8001` | `user_db` | `user_auth_user` | `users`, `verification_codes` | `Base.metadata.create_all` |
| **Vehicle Service** | `services/vehicle-service/` | `8002` | `vehicle_db` | `vehicle_user` | `vehicles` | `Base.metadata.create_all` |
| **Parking Service** | `services/parking-service/` | `8003` | `parking_db` | `parking_user` | `parking_slots`, `bookings` | **Alembic** + `create_all` + auto-seed 100 slots |
| **Payment Service** | `services/payment-service/` | `8004` | `payment_db` | `payment_user` | `payments` | `Base.metadata.create_all` |

## Milestones

| Milestone | Scope | Status | Log |
|---|---|---|---|
| **m0** | Finalize simplified microservices architecture & design decisions | Done | [m0/iter-01.md](m0/iter-01.md) |
| **m1** | Monorepo scaffold (`services/*`), DB init SQL, `/health`, Alembic in `parking-service` | Done | [m1/iter-01.md](m1/iter-01.md) |
| **m2** | User/Auth Service (3 APIs: Company Email OTP, HS256 JWT, `/users/me`) | Done | [m2/iter-01.md](m2/iter-01.md) |
| **m3** | Vehicle Service (5 APIs: standalone owner-scoped CRUD, soft delete, plate normalization) | Done | [m3/iter-01.md](m3/iter-01.md) |
| **m4** | Parking Service Core (5 public APIs: availability, booking + `FOR UPDATE` locking, history, cancel) | Done | [m4/iter-01.md](m4/iter-01.md) |
| **m5** | Payment Service (3 APIs) + Parking Internal Callback API (`payment-result`) | Done | [m5/iter-01.md](m5/iter-01.md) |
| **m6** | Multi-Service Launcher Scripts (`scripts/start_all.ps1`, `scripts/start_all.sh`) | Done | [m6/iter-01.md](m6/iter-01.md) |
| **m7** | End-to-End & PostgreSQL Concurrency Tests (`scripts/run_all_tests.ps1`) | Done | [m7/iter-01.md](m7/iter-01.md) |
