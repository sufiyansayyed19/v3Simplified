# API Flow: `POST /api/v1/auth/company/verify`

- **Service:** `user-auth-service` (`:8001`)
- **Router / Handler:** [auth.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/api/v1/auth.py) $\rightarrow$ `verify_company_code()`
- **Authentication:** Public (exchanges OTP for HS256 JWT)
- **Database:** `user_db` (`verification_codes`, `users`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant FastAPI as Pydantic (VerifyCodeRequest)
    participant Handler as auth.py: verify_company_code()
    participant DB as user_db
    participant Sec as security.py

    Client->>FastAPI: POST /api/v1/auth/company/verify {"email": "alice@company.com", "code": "749201"}
    alt Code not 6 numeric digits or bad email
        FastAPI-->>Client: 422 INVALID_REQUEST
    end
    FastAPI->>Handler: Validated payload
    Handler->>Sec: normalize_email(email)
    Handler->>DB: SELECT * FROM verification_codes WHERE email=:email AND consumed_at IS NULL ORDER BY created_at DESC LIMIT 1
    alt No unused OTP OR expires_at <= now OR code mismatch
        Handler-->>Client: 401 INVALID_OR_EXPIRED_CODE
    end
    Handler->>Handler: verification.consumed_at = now (prevent replay)
    Handler->>DB: SELECT * FROM users WHERE email = :email
    opt First-time login (user is None)
        Handler->>DB: Stage new User(email=email, name=None)
    end
    Handler->>DB: COMMIT & REFRESH user
    Handler->>Sec: create_access_token(user.id) -> HS256 JWT (60m TTL)
    Handler-->>Client: 200 OK {access_token, token_type: "bearer", expires_in: 3600, user}
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["Request: email + 6-digit code"]) --> Fetch["Query latest unconsumed VerificationCode (created_at DESC)"]
    Fetch --> Check{"Found AND expires_at > now AND code matches?"}
    Check -- No --> Err401["401 INVALID_OR_EXPIRED_CODE"]
    Check -- Yes --> Consume["Set consumed_at = now"]
    Consume --> FindUser{"User exists in users?"}
    FindUser -- No --> CreateUser["Create User(email, name=None)"]
    FindUser -- Yes --> Commit["db.commit() & db.refresh(user)"]
    CreateUser --> Commit
    Commit --> Mint["create_access_token(user.id) using HS256"]
    Mint --> Ok200(["200 OK AuthTokenResponse"])
```
