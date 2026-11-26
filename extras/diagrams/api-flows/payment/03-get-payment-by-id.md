# API Flow: `GET /api/v1/payments/{payment_id}`

- **Service:** `payment-service` (`:8004`)
- **Router / Handler:** [payments.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/payment-service/app/api/v1/payments.py) $\rightarrow$ `get_payment()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_current_user_id)`)
- **Database:** `payment_db` (`payments`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_current_user_id()
    participant Handler as payments.py: get_payment()
    participant DB as payment_db (payments)

    Client->>Sec: GET /api/v1/payments/{payment_id} [Bearer JWT]
    alt Invalid JWT or bad UUID
        Sec-->>Client: 401 UNAUTHENTICATED / 422 INVALID_PAYMENT_REQUEST
    end
    Sec-->>Handler: user_id (UUID)
    Handler->>DB: SELECT * FROM payments WHERE id=:pid AND user_id=:uid
    alt Payment not found or owned by another user
        Handler-->>Client: 404 PAYMENT_NOT_FOUND
    end
    Handler-->>Client: 200 OK PaymentDetailResponse
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["GET /api/v1/payments/id"]) --> Auth{"Valid Bearer JWT & UUID?"}
    Auth -- No --> ErrAuth["401 or 422"]
    Auth -- Yes --> Lookup{"Payment exists AND user_id == caller?"}
    Lookup -- No --> Err404["404 PAYMENT_NOT_FOUND"]
    Lookup -- Yes --> Ok200(["200 OK PaymentDetailResponse"])
```
