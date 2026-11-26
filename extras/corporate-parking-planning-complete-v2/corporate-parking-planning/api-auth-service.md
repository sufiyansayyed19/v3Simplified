# User/Auth Service API Contract

**Service Path:** `services/user-auth-service/` | **Port:** `8001` | **Database:** `user_db` (`users`, `verification_codes`)

---

## 1. Responsibilities
User/Auth Service owns user identity (`users`) and corporate-email OTP records (`verification_codes`). It validates that emails match `COMPANY_EMAIL_DOMAIN`, generates 6-digit OTPs, and issues stateless **HS256 JWT** access tokens signed with `JWT_SECRET_KEY`.

---

## 2. Endpoint Inventory (3 Endpoints)

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/auth/company/send-code` | Public | Send a 6-digit OTP to a corporate email address |
| `POST` | `/api/v1/auth/company/verify` | Public | Verify the 6-digit OTP and return an HS256 Bearer JWT |
| `GET` | `/api/v1/users/me` | Bearer JWT | Return the authenticated user's profile |

---

## 3. `POST /api/v1/auth/company/send-code`

### Request
```json
{
  "email": "employee@company.com"
}
```

### Processing
1. Normalize email (trim and lowercase) and verify domain matches `COMPANY_EMAIL_DOMAIN` (`403 CORPORATE_EMAIL_REQUIRED` if not).
2. Mark any previous unconsumed verification codes for this email as consumed.
3. Generate a 6-digit OTP code (`OTP_EXPIRE_MINUTES = 5`) and save it in `verification_codes`.
4. Deliver the OTP via `EmailSender` (prints `[DEV EMAIL OTP] To: ... | Code: ...` in the terminal in development).

### Response (`200 OK`)
```json
{
  "message": "Verification code sent successfully"
}
```

---

## 4. `POST /api/v1/auth/company/verify`

### Request
```json
{
  "email": "employee@company.com",
  "code": "123456"
}
```

### Processing
1. Look up the latest unconsumed `VerificationCode` for the email.
2. If missing, expired (`expires_at <= now`), or `code != payload.code`, return `401 INVALID_OR_EXPIRED_CODE`.
3. Mark `consumed_at = now`.
4. Find or create the `User` row in `users`.
5. Sign and return an **HS256** JWT access token (`sub = str(user.id)`).

### Response (`200 OK`)
```json
{
  "access_token": "<hs256-jwt-token>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "<user-uuid>",
    "email": "employee@company.com",
    "name": null
  }
}
```

---

## 5. `GET /api/v1/users/me`

Requires `Authorization: Bearer <access_token>`. Decodes the HS256 JWT, looks up the `User` in `user_db`, and returns `{ "id", "email", "name" }` (`200 OK`).
