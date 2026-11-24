# Milestone 2 (m2) — Iteration 01: User/Auth Service (3 APIs)

## Goal
Implement the simplified **User/Auth Service** (`services/user-auth-service/`, port `8001`, DB `user_db`) with 2 PostgreSQL tables (`users`, `verification_codes`), corporate email OTP sender, and HS256 JWT authentication.

## What Was Built

### 1. ORM Models (`app/models/auth.py`)
- `users` (`id`, `email`, `name`, `created_at`, `updated_at`)
- `verification_codes` (`id`, `email`, `code`, `expires_at`, `attempt_count`, `consumed_at`, `created_at`)

### 2. Security & OTP Delivery
- `app/core/security.py` — Email normalization, corporate domain check (`COMPANY_EMAIL_DOMAIN`), 6-digit OTP generation, HS256 JWT creation/verification (`JWT_SECRET_KEY`), and `get_current_user` dependency.
- `app/services/email_sender.py` — `ConsoleEmailSender` printing the 6-digit OTP in the terminal during local development.

### 3. API Endpoints (`app/api/v1/auth.py`)
1. `POST /api/v1/auth/company/send-code` — Checks corporate email domain, marks previous unused codes as consumed, saves a 6-digit OTP (5-min expiry), and prints it via `EmailSender`.
2. `POST /api/v1/auth/company/verify` — Verifies OTP, marks it consumed, finds or creates `User`, and returns an HS256 `access_token`.
3. `GET /api/v1/users/me` — Validates Bearer HS256 JWT and returns `{ id, email, name }`.
