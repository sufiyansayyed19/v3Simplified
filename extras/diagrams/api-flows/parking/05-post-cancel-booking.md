# API Flow: `POST /api/v1/parking/bookings/{booking_id}/cancel`

- **Service:** `parking-service` (`:8003`)
- **Router / Handler:** [parking.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/api/v1/parking.py) $\rightarrow$ `cancel_booking()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_auth_context)`)
- **Database:** `parking_db` (`bookings`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_auth_context()
    participant Handler as parking.py: cancel_booking()
    participant Rules as rules.py: can_cancel_booking()
    participant DB as parking_db

    Client->>Sec: POST /api/v1/parking/bookings/{booking_id}/cancel [Bearer JWT]
    alt Invalid JWT
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec-->>Handler: AuthContext(user_id)
    Handler->>DB: SELECT * FROM bookings WHERE id=:bid AND user_id=:uid
    alt Not found or foreign owner
        Handler-->>Client: 404 BOOKING_NOT_FOUND
    end
    Handler->>Handler: _expire_stale_holds(db, [booking], now_utc)
    alt booking.status != "CONFIRMED" (e.g. PAYMENT_PENDING, EXPIRED, CANCELLED)
        Handler-->>Client: 409 BOOKING_NOT_CANCELLABLE
    end
    Handler->>Rules: can_cancel_booking(booking_date, start_time, now) [Asia/Kolkata]
    alt now_local >= booking start_dt
        Handler-->>Client: 409 BOOKING_NOT_CANCELLABLE
    end
    Handler->>DB: UPDATE status='CANCELLED', cancelled_at=now_utc + COMMIT
    Handler-->>Client: 200 OK {booking_id, status: "CANCELLED", cancelled_at}
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["POST /bookings/id/cancel"]) --> Own{"Booking exists & owned by caller?"}
    Own -- No --> Err404["404 BOOKING_NOT_FOUND"]
    Own -- Yes --> Lazy["_expire_stale_holds()"]
    Lazy --> Status{"status == CONFIRMED?"}
    Status -- No --> Err409["409 BOOKING_NOT_CANCELLABLE"]
    Status -- Yes --> Cutoff{"now_local < start_time (Asia/Kolkata)?"}
    Cutoff -- No --> Err409
    Cutoff -- Yes --> Cancel["Set status='CANCELLED', cancelled_at=now_utc & commit"]
    Cancel --> Ok200(["200 OK BookingCancelResponse"])
```
