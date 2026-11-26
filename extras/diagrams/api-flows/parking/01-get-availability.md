# API Flow: `GET /api/v1/parking/availability`

- **Service:** `parking-service` (`:8003`)
- **Router / Handler:** [parking.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/parking-service/app/api/v1/parking.py) $\rightarrow$ `check_availability()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_auth_context)`)
- **Cross-Service Calls:** `VehicleServiceClient.get_owned_vehicle` $\rightarrow$ `vehicle-service` (`:8002`)
- **Database:** `parking_db` (`parking_slots`, `bookings`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_auth_context()
    participant Handler as parking.py: check_availability()
    participant Rules as rules.py
    participant VehSvc as vehicle-service (:8002)
    participant DB as parking_db

    Client->>Sec: GET /api/v1/parking/availability?date=...&start_time=...&end_time=...&vehicle_id=...&requires_charging=...
    alt Missing or invalid Bearer JWT
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec-->>Handler: AuthContext(user_id, raw_token)
    Handler->>Rules: validate_booking_interval(date, start_time, end_time, now)
    alt Bad horizon, Sunday, non-whole hour, outside 07:00-22:00, >12h, or past start
        Rules-->>Client: 422 BOOKING_WINDOW_VIOLATION / INVALID_BOOKING_TIME
    end
    Handler->>VehSvc: GET /api/v1/vehicles/{vehicle_id} [Forwarded Bearer JWT]
    alt Vehicle Service unreachable / 404 / 401
        VehSvc-->>Handler: Error response or timeout
        Handler-->>Client: 503 VEHICLE_SERVICE_UNAVAILABLE / 404 / 401
    end
    VehSvc-->>Handler: VehicleInfo(vehicle_type, is_ev, is_active)
    Handler->>Rules: validate_charging_compatibility(vehicle.is_ev, requires_charging)
    alt requires_charging=True AND is_ev=False
        Rules-->>Client: 422 CHARGING_NOT_SUPPORTED
    end
    Handler->>DB: SELECT id FROM parking_slots WHERE vehicle_type=:vt AND is_charging_enabled=:req
    Handler->>DB: SELECT DISTINCT slot_id FROM bookings WHERE overlap AND _active_booking_filter(now_utc)
    Handler->>Rules: calculate_hourly_rate(requires_charging) -> 10.00 or 20.00
    Handler-->>Client: 200 OK {available, available_slots, vehicle_type, is_ev, requires_charging, rate_per_hour}
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["GET /api/v1/parking/availability"]) --> Auth{"Valid Bearer JWT?"}
    Auth -- No --> Err401["401 UNAUTHENTICATED"]
    Auth -- Yes --> Interval{"validate_booking_interval() passes?"}
    Interval -- No --> Err422T["422 BOOKING_WINDOW_VIOLATION or INVALID_BOOKING_TIME"]
    Interval -- Yes --> VehCall["Call vehicle-service GET /vehicles/id"]
    VehCall -- Unavailable / Missing --> ErrVeh["503 or 404 VEHICLE_NOT_FOUND"]
    VehCall -- OK --> EVCheck{"validate_charging_compatibility() passes?"}
    EVCheck -- No --> Err422EV["422 CHARGING_NOT_SUPPORTED"]
    EVCheck -- Yes --> Count["Count compatible_slot_ids minus occupied_slot_ids"]
    Count --> Ok200(["200 OK AvailabilityResponse"])
```
