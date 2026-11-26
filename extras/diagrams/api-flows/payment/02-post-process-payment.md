# API Flow: `POST /api/v1/payments/{payment_id}/process`

- **Service:** `payment-service` (`:8004`)
- **Router / Handler:** [payments.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/payment-service/app/api/v1/payments.py) $\rightarrow$ `process_payment()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_current_user_id)`)
- **Cross-Service Callback:** `ParkingCallbackClient.deliver_payment_result` $\rightarrow$ `parking-service` (`:8003`)
- **Database:** `payment_db` (`payments`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_current_user_id()
    participant Handler as payments.py: process_payment()
    participant DB as payment_db (payments)
    participant ParkCB as parking-service (:8003)

    Client->>Sec: POST /api/v1/payments/{payment_id}/process [Bearer JWT + {payment_method}]
    alt Missing or invalid Bearer JWT
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec-->>Handler: user_id (UUID)
    Handler->>DB: SELECT * FROM payments WHERE id=:pid AND user_id=:uid
    alt Payment missing or belongs to another user
        Handler-->>Client: 404 PAYMENT_NOT_FOUND
    end
    alt payment.status != "PENDING"
        Handler-->>Client: 409 PAYMENT_ALREADY_PROCESSED
    end
    alt now_utc >= payment.expires_at
        Handler-->>Client: 409 PAYMENT_EXPIRED
    end
    Handler->>Handler: _resolve_simulated_outcome(X-Test-Payment-Outcome) -> SUCCESS or FAILED
    Handler->>Handler: Generate TXN<10-hex> if SUCCESS else None
    Handler->>DB: UPDATE payment_method, status, transaction_id + COMMIT
    Handler->>ParkCB: POST /internal/v1/bookings/{booking_id}/payment-result [X-Internal-Service-Token]
    Note over ParkCB: Swallows httpx.HTTPError safely if callback fails transiently
    Handler-->>Client: 200 OK PaymentProcessResponse {payment_id, booking_id, amount, status, transaction_id}
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["POST /api/v1/payments/id/process"]) --> Auth{"Valid Bearer JWT & UPI/CARD/WALLET?"}
    Auth -- No --> ErrAuth["401 or 422"]
    Auth -- Yes --> Own{"Payment exists for caller user_id?"}
    Own -- No --> Err404["404 PAYMENT_NOT_FOUND"]
    Own -- Yes --> Pending{"status == PENDING?"}
    Pending -- No --> ErrProc["409 PAYMENT_ALREADY_PROCESSED"]
    Pending -- Yes --> Exp{"now_utc < expires_at?"}
    Exp -- No --> ErrExp["409 PAYMENT_EXPIRED"]
    Exp -- Yes --> Sim["Resolve simulated SUCCESS/FAILED + TXN ID -> commit"]
    Sim --> CB["Notify parking-service internal callback"]
    CB --> Ok200(["200 OK PaymentProcessResponse"])
```
