# API Flow: `POST /internal/v1/payments`

- **Service:** `payment-service` (`:8004`)
- **Router / Handler:** [payments.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/payment-service/app/api/v1/payments.py) $\rightarrow$ `create_internal_payment()`
- **Authentication:** `X-Internal-Service-Token` (`dependencies=[Depends(require_parking_service_token)]`)
- **Called By:** `parking-service` (`PaymentServiceClient.create_payment`)
- **Database:** `payment_db` (`payments`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant ParkSvc as parking-service (:8003)
    participant Guard as security.py: require_parking_service_token()
    participant Handler as payments.py: create_internal_payment()
    participant DB as payment_db (payments)

    ParkSvc->>Guard: POST /internal/v1/payments [X-Internal-Service-Token + JSON]
    alt Invalid internal token
        Guard-->>ParkSvc: 401 INTERNAL_CALLER_UNAUTHORIZED
    end
    Guard->>Handler: Validated InternalPaymentCreateRequest
    Handler->>DB: SELECT * FROM payments WHERE booking_id = :booking_id
    alt Existing payment found for booking_id
        alt Same user_id AND same amount (Idempotent retry)
            Handler-->>ParkSvc: 200 OK {payment_id, booking_id, amount, status, expires_at}
        else Different user_id or amount
            Handler-->>ParkSvc: 409 PAYMENT_REQUEST_CONFLICT
        end
    else No existing payment
        Handler->>DB: INSERT Payment(status='PENDING', expires_at=req_expires_utc) + COMMIT
        Handler-->>ParkSvc: 201 Created {payment_id, booking_id, amount, status: 'PENDING', expires_at}
    end
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["POST /internal/v1/payments"]) --> Token{"X-Internal-Service-Token valid?"}
    Token -- No --> Err401["401 INTERNAL_CALLER_UNAUTHORIZED"]
    Token -- Yes --> Exists{"Payment already exists for booking_id?"}
    Exists -- No --> Insert["Insert PENDING Payment & commit -> 201 Created"]
    Exists -- Yes --> Same{"Same user_id AND same amount?"}
    Same -- Yes --> Idemp["Set response.status_code=200 -> 200 OK"]
    Same -- No --> Err409["409 PAYMENT_REQUEST_CONFLICT"]
```
