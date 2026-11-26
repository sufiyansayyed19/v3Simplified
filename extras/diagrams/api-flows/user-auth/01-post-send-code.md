# API Flow: `POST /api/v1/auth/company/send-code`

- **Service:** `user-auth-service` (`:8001`)
- **Router / Handler:** [auth.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/api/v1/auth.py) $\rightarrow$ `send_company_code()`
- **Authentication:** Public (no JWT required)
- **Database:** `user_db` (`verification_codes`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant FastAPI as Pydantic (SendCodeRequest)
    participant Handler as auth.py: send_company_code()
    participant Sec as security.py
    participant DB as user_db (verification_codes)
    participant Mailer as ConsoleEmailSender

    Client->>FastAPI: POST /api/v1/auth/company/send-code {"email": "Alice@Company.com"}
    alt Invalid email syntax
        FastAPI-->>Client: 422 INVALID_REQUEST
    end
    FastAPI->>Handler: Validated payload
    Handler->>Sec: normalize_email(email) -> "alice@company.com"
    Handler->>Sec: is_allowed_corporate_email("alice@company.com")
    alt Domain != company.com
        Sec-->>Handler: False
        Handler-->>Client: 403 CORPORATE_EMAIL_REQUIRED
    end
    Handler->>DB: SELECT * FROM verification_codes WHERE email=:email AND consumed_at IS NULL
    loop Each prior unused OTP row
        Handler->>Handler: row.consumed_at = now (invalidate old OTPs)
    end
    Handler->>Sec: generate_otp_code() -> 6-digit CSPRNG string
    Handler->>DB: INSERT INTO verification_codes (id, email, code_hash, expires_at=now+5m) + COMMIT
    Handler->>Mailer: send_otp(email, code, expires_minutes=5)
    Mailer-->>Handler: Printed to stdout (dev mode)
    Handler-->>Client: 200 OK {"message": "Verification code sent successfully"}
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["Request: email"]) --> Norm["normalize_email(): strip & lowercase"]
    Norm --> Domain{"Domain == company.com?"}
    Domain -- No --> Err403["403 CORPORATE_EMAIL_REQUIRED"]
    Domain -- Yes --> Invalidate["Set consumed_at = now on prior unused OTPs"]
    Invalidate --> Gen["generate_otp_code() via secrets.randbelow(1_000_000)"]
    Gen --> Save["Insert VerificationCode (expires_at = now + 5m) & commit"]
    Save --> Send["ConsoleEmailSender.send_otp()"]
    Send --> Ok200(["200 OK MessageResponse"])
```
