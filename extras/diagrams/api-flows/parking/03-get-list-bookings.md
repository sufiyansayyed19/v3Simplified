# API Flow: `GET /api/v1/parking/bookings`

- **Service:** `parking-service` (`:8003`)
- **Router / Handler:** [parking.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/api/v1/parking.py) $\rightarrow$ `list_bookings()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_auth_context)`)
- **Database:** `parking_db` (`bookings` `LEFT OUTER JOIN` `parking_slots`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_auth_context()
    participant Handler as parking.py: list_bookings()
    participant DB as parking_db

    Client->>Sec: GET /api/v1/parking/bookings?page=1&page_size=20 [Bearer JWT]
    alt Invalid JWT or bad page/page_size bounds
        Sec-->>Client: 401 UNAUTHENTICATED / 422 INVALID_BOOKING_REQUEST
    end
    Sec-->>Handler: AuthContext(user_id)
    Handler->>DB: SELECT count(id) FROM bookings WHERE user_id = :uid
    Handler->>DB: SELECT bookings.*, parking_slots.* FROM bookings LEFT OUTER JOIN parking_slots ... ORDER BY created_at DESC OFFSET ... LIMIT ...
    Handler->>Handler: _expire_stale_holds(db, rows, now_utc)
    opt Any row has PAYMENT_PENDING AND hold_expires_at <= now_utc
        Handler->>DB: UPDATE status = 'EXPIRED' + COMMIT
    end
    Handler-->>Client: 200 OK BookingListResponse {items, page, page_size, total_items}
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["GET /api/v1/parking/bookings"]) --> Auth{"Valid JWT & page bounds?"}
    Auth -- No --> Err["401 or 422"]
    Auth -- Yes --> Count["Count total_items for user_id"]
    Count --> Fetch["Fetch page via joinedload(Booking.slot), created_at DESC"]
    Fetch --> Expire["_expire_stale_holds(): flip past-deadline PAYMENT_PENDING to EXPIRED"]
    Expire --> Ok200(["200 OK BookingListResponse"])
```
