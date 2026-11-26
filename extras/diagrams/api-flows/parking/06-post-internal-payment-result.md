# API Flow: `POST /internal/v1/bookings/{booking_id}/payment-result`

- **Service:** `parking-service` (`:8003`)
- **Router / Handler:** [internal.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/api/internal.py) $\rightarrow$ `apply_payment_result()`
- **Authentication:** `X-Internal-Service-Token` (`dependencies=[Depends(_require_internal_token)]`)
- **Called By:** `payment-service` (`ParkingCallbackClient.deliver_payment_result`)
- **Database:** `parking_db` (`bookings`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant PaySvc as payment-service (:8004)
    participant Guard as internal.py: _require_internal_token()
    participant Handler as internal.py: apply_payment_result()
    participant DB as parking_db (bookings)

    PaySvc->>Guard: POST /internal/v1/bookings/{id}/payment-result [X-Internal-Service-Token]
    alt Missing or invalid internal token
        Guard-->>PaySvc: 401 INTERNAL_CALLER_UNAUTHORIZED
    end
    Guard->>Handler: Valid internal caller
    Handler->>DB: SELECT * FROM bookings WHERE id = :booking_id
    alt Booking missing
        Handler-->>PaySvc: 404 BOOKING_NOT_FOUND
    end
    alt booking.payment_id exists AND != payload.payment_id
        Handler-->>PaySvc: 409 PAYMENT_REFERENCE_MISMATCH
    end
    alt booking.status == "CONFIRMED"
        Handler-->>PaySvc: 200 OK {status: "CONFIRMED", result: "ALREADY_APPLIED"}
    else booking.status == "EXPIRED"
        Handler-->>PaySvc: 200 OK {status: "EXPIRED", result: "EXPIRED_NO_RESURRECTION"}
    else booking.status == "CANCELLED"
        Handler-->>PaySvc: 409 INVALID_BOOKING_TRANSITION
    else booking.status == "PAYMENT_PENDING"
        alt hold_expires_at <= now_utc OR payload.status == "FAILED"
            Handler->>DB: booking.status = "EXPIRED" + COMMIT
        else payload.status == "SUCCESS" AND hold active
            Handler->>DB: booking.status = "CONFIRMED" + COMMIT
        end
        Handler-->>PaySvc: 200 OK {booking_id, status, result: "APPLIED"}
    end
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["POST /internal/v1/bookings/id/payment-result"]) --> Token{"X-Internal-Service-Token valid?"}
    Token -- No --> Err401["401 INTERNAL_CALLER_UNAUTHORIZED"]
    Token -- Yes --> Find{"Booking exists?"}
    Find -- No --> Err404["404 BOOKING_NOT_FOUND"]
    Find -- Yes --> Match{"payment_id matches?"}
    Match -- No --> Err409M["409 PAYMENT_REFERENCE_MISMATCH"]
    Match -- Yes --> State{"Current booking.status?"}
    State -- CONFIRMED --> Idemp["200 OK ALREADY_APPLIED"]
    State -- EXPIRED --> NoRes["200 OK EXPIRED_NO_RESURRECTION"]
    State -- CANCELLED --> Err409C["409 INVALID_BOOKING_TRANSITION"]
    State -- PAYMENT_PENDING --> Eval{"hold_expires_at > now_utc AND status == SUCCESS?"}
    Eval -- Yes --> Confirm["Set CONFIRMED & commit -> 200 APPLIED"]
    Eval -- No --> Expire["Set EXPIRED & commit -> 200 APPLIED"]
```
