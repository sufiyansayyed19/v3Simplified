# Milestone 7 (m7) — Iteration 01: End-to-End & PostgreSQL Concurrency Tests

## Goal
Verify all 4 microservices end-to-end against real PostgreSQL databases and prove PostgreSQL slot locking (`SELECT ... FOR UPDATE`) under concurrent race conditions.

## What Was Built
1. `scripts/run_all_tests.ps1` & `scripts/run_all_tests.sh` — Runs all 7 test suites (5 unit test suites + PostgreSQL concurrency test + 4-service live E2E test) in isolated processes.
2. `tests/test_pg_concurrency.py` — Proves that when 10 users race for 5 EV-bike slots (`B36–B40`), `SELECT ... FOR UPDATE` allocates exactly 5 unique slots and rejects 5 with `409 NO_PARKING_CAPACITY`, and serializes same-user simultaneous overlapping requests.
3. `tests/test_e2e_journey.py` — Spins up all 4 microservices (`user-auth`, `vehicle`, `parking`, `payment`) against PostgreSQL and verifies the full journey: register EV car → check availability → create booking → process UPI payment → verify booking confirmed → cancel booking.
