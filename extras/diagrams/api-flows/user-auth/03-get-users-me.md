# API Flow: `GET /api/v1/users/me`

- **Service:** `user-auth-service` (`:8001`)
- **Router / Handler:** [auth.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/user-auth-service/app/api/v1/auth.py) $\rightarrow$ `get_me()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_current_user)`)
- **Database:** `user_db` (`users`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Bearer as security.py: HTTPBearer
    participant Sec as security.py: get_current_user()
    participant DB as user_db (users)
    participant Handler as auth.py: get_me()

    Client->>Bearer: GET /api/v1/users/me [Header: Authorization: Bearer <jwt>]
    Bearer->>Sec: HTTPAuthorizationCredentials (or None)
    alt Header missing or scheme != bearer
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec->>Sec: decode_access_token(token) -> jwt.decode(..., algorithms=["HS256"])
    alt Signature invalid, expired, or bad sub UUID
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec->>DB: db.get(User, user_id)
    alt User row not found
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec-->>Handler: User ORM object
    Handler-->>Client: 200 OK UserProfile {id, email, name}
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["Request + Authorization Header"]) --> HeaderCheck{"Bearer token present?"}
    HeaderCheck -- No --> Err401["401 UNAUTHENTICATED"]
    HeaderCheck -- Yes --> Decode{"decode_access_token() valid HS256 & UUID sub?"}
    Decode -- No --> Err401
    Decode -- Yes --> DbLookup{"db.get(User, user_id) exists?"}
    DbLookup -- No --> Err401
    DbLookup -- Yes --> Ok200(["200 OK UserProfile"])
```
