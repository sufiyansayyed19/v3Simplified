# API Flow: `GET /api/v1/parking/bookings/{booking_id}`

- **Service:** `parking-service` (`:8003`)
- **Router / Handler:** [parking.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/api/v1/parking.py) $\rightarrow$ `get_booking()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_auth_context)`)
- **Database:** `parking_db` (`bookings` `LEFT OUTER JOIN` `parking_slots`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_auth_context()
    participant Handler as parking.py: get_booking()
    participant DB as parking_db

    Client->>Sec: GET /api/v1/parking/bookings/{booking_id} [Bearer JWT]
    alt Invalid JWT or bad UUID
        Sec-->>Client: 401 UNAUTHENTICATED / 422 INVALID_BOOKING_REQUEST
    end
    Sec-->>Handler: AuthContext(user_id)
    Handler->>DB: SELECT Booking + joinedload(slot) WHERE id=:bid AND user_id=:uid
    alt Booking missing or owned by another user
        Handler-->>Client: 404 BOOKING_NOT_FOUND
    end
    Handler->>Handler: _expire_stale_holds(db, [booking], now_utc)
    opt PAYMENT_PENDING AND hold_expires_at <= now_utc
        Handler->>DB: UPDATE status = 'EXPIRED' + COMMIT
    end
    Handler-->>Client: 200 OK BookingResponse
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["GET /api/v1/parking/bookings/id"]) --> Auth{"Valid JWT & UUID?"}
    Auth -- No --> ErrAuth["401 or 422"]
    Auth -- Yes --> Lookup{"Exists AND user_id == caller?"}
    Lookup -- No --> Err404["404 BOOKING_NOT_FOUND"]
    Lookup -- Yes --> Lazy["_expire_stale_holds(): mark EXPIRED if past hold_expires_at"]
    Lazy --> Ok200(["200 OK BookingResponse"])
```
