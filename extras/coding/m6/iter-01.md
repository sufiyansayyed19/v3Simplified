# Milestone 6 (m6) — Iteration 01: Multi-Service Launcher Scripts

## Goal
Provide one-command launcher scripts (`scripts/start_all.ps1` and `scripts/start_all.sh`) to start all 4 microservices (`:8001`–`:8004`) with their interactive Swagger UIs (`/docs`).

## What Was Built
- `scripts/start_all.ps1` — Launches `user-auth-service` (`:8001`), `vehicle-service` (`:8002`), `parking-service` (`:8003`), and `payment-service` (`:8004`) in dedicated PowerShell windows using `.venv\Scripts\python.exe -m uvicorn`.
- `scripts/start_all.sh` — Bash equivalent for Linux/macOS/Git Bash.
