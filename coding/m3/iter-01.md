# Milestone 3 (m3) — Iteration 01: Vehicle Service (5 APIs)

## Goal
Implement the standalone **Vehicle Service** (`services/vehicle-service/`, port `8002`, DB `vehicle_db`) with its `vehicles` table, HS256 JWT authentication, plate normalization, and owner-scoped CRUD + soft delete.

## What Was Built

### 1. ORM Model (`app/models/vehicle.py`)
- `Vehicle` (`vehicles` table): `id`, `user_id` (logical UUID ref to `users.id`), `vehicle_number`, `vehicle_type` (`CAR` or `BIKE`), `is_ev`, `is_active`, `created_at`.

### 2. All 5 API Endpoints (`app/api/v1/vehicles.py`)
1. `POST /api/v1/vehicles` — Normalizes plate (`"mh 12-ab 1234"` → `"MH12AB1234"`), rejects duplicate active plate for the same user (`409`), and inserts a new active vehicle.
2. `GET /api/v1/vehicles` — Lists active vehicles owned by the authenticated user.
3. `GET /api/v1/vehicles/{vehicle_id}` — Fetches a single active vehicle owned by the user (`404` if missing, inactive, or owned by another user).
4. `PUT /api/v1/vehicles/{vehicle_id}` — Updates `vehicle_number`, `vehicle_type`, and `is_ev`.
5. `DELETE /api/v1/vehicles/{vehicle_id}` — Soft-deactivates the vehicle (`is_active = False`).
