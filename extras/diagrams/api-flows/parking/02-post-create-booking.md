# API Flow: `POST /api/v1/parking/bookings`

- **Service:** `parking-service` (`:8003`)
- **Router / Handler:** [parking.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/api/v1/parking.py) $\rightarrow$ `create_booking()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_auth_context)`)
- **Cross-Service Calls:** `VehicleServiceClient` (`:8002`) + `PaymentServiceClient` (`:8004`)
- **Database:** `parking_db` (`parking_slots` with `FOR UPDATE`, `bookings`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Handler as parking.py: create_booking()
    participant Rules as rules.py
    participant VehSvc as vehicle-service (:8002)
    participant DB as parking_db (PostgreSQL)
    participant PaySvc as payment-service (:8004)

    Client->>Handler: POST /api/v1/parking/bookings [Bearer JWT + JSON]
    Handler->>Rules: validate_booking_interval(...)
    Handler->>VehSvc: GET /api/v1/vehicles/{vehicle_id} [Forwarded Bearer JWT]
    VehSvc-->>Handler: VehicleInfo (plate, type, is_ev, is_active)
    Handler->>Rules: validate_charging_compatibility() & calculate_booking_amount()
    Handler->>DB: SELECT * FROM parking_slots WHERE ... ORDER BY slot_number ASC FOR UPDATE
    Note over DB: Acquires PostgreSQL row locks to prevent double-booking!
    Handler->>DB: SELECT id FROM bookings WHERE user_id=:uid AND overlap AND active LIMIT 1
    alt User already has overlapping active booking
        Handler-->>Client: 409 USER_BOOKING_OVERLAP
    end
    Handler->>DB: SELECT DISTINCT slot_id FROM bookings WHERE slot_id IN (...) AND overlap AND active
    alt All compatible slots occupied
        Handler-->>Client: 409 NO_PARKING_CAPACITY
    end
    Handler->>DB: INSERT Booking(status='PAYMENT_PENDING', vehicle snapshots, hold_expires_at=now+5m) + COMMIT
    Note over DB: Locks released BEFORE calling Payment Service!
    Handler->>PaySvc: POST /internal/v1/payments [X-Internal-Service-Token]
    alt Payment Service unreachable
        PaySvc-->>Handler: Timeout / Error
        Handler-->>Client: 503 PAYMENT_SERVICE_UNAVAILABLE
    end
    PaySvc-->>Handler: 201 Created {payment_id}
    Handler->>DB: UPDATE booking.payment_id = payment_id + COMMIT
    Handler-->>Client: 201 Created BookingResponse (PAYMENT_PENDING)
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["POST /api/v1/parking/bookings"]) --> Validate["Auth + Interval Rules + Vehicle Check + EV Check"]
    Validate -- Fails --> ErrPre["401 / 404 / 422 / 503"]
    Validate -- Passes --> Lock["SELECT compatible parking_slots FOR UPDATE (PostgreSQL)"]
    Lock --> SelfOverlap{"User already has overlapping active booking?"}
    SelfOverlap -- Yes --> ErrUser["409 USER_BOOKING_OVERLAP"]
    SelfOverlap -- No --> FreeSlot{"First compatible slot not in occupied_slot_ids?"}
    FreeSlot -- None --> ErrCap["409 NO_PARKING_CAPACITY"]
    FreeSlot -- Found --> CommitHold["Insert PAYMENT_PENDING Booking (5m hold + snapshots) & commit"]
    CommitHold --> InitPay["POST /internal/v1/payments (3s timeout)"]
    InitPay -- Fails --> Err503["503 PAYMENT_SERVICE_UNAVAILABLE"]
    InitPay -- OK --> SavePayId["Save booking.payment_id & commit"]
    SavePayId --> Ok201(["201 Created BookingResponse"])
```
