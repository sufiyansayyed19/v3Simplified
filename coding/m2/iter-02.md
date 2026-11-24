# Milestone 2 (m2) — Iteration 02: Simplified Auth Consolidation

## Summary
Consolidated authentication to corporate-email OTP only (`COMPANY_EMAIL_DOMAIN`) with 2 tables (`users`, `verification_codes`), 3 endpoints (`send-code`, `verify`, `users/me`), and HS256 Bearer JWT authentication (`JWT_SECRET_KEY`). Dropped Google OAuth, `auth_identities`, `refresh_sessions`, and RS256 PEM keys.
