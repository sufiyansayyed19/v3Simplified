# API Flow: `GET /api/v1/vehicles/{vehicle_id}`

- **Service:** `vehicle-service` (`:8002`)
- **Router / Handler:** [vehicles.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/vehicle-service/app/api/v1/vehicles.py) $\rightarrow$ `get_vehicle()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_current_user_id)`)
- **Called By:** End users AND `parking-service` (`VehicleServiceClient.get_owned_vehicle`)
- **Database:** `vehicle_db` (`vehicles`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Caller as Employee Client OR Parking Service
    participant Sec as security.py: get_current_user_id()
    participant Handler as vehicles.py: get_vehicle()
    participant DB as vehicle_db (vehicles)

    Caller->>Sec: GET /api/v1/vehicles/{vehicle_id} [Bearer JWT]
    alt vehicle_id is not a valid UUID
        Sec-->>Caller: 422 INVALID_VEHICLE_DATA
    end
    Sec->>Sec: decode_access_token() locally (HS256)
    alt Missing or invalid/expired JWT
        Sec-->>Caller: 401 UNAUTHENTICATED
    end
    Sec-->>Handler: user_id (UUID)
    Handler->>DB: _get_owned_active_vehicle(): WHERE id=:vid AND user_id=:uid AND is_active IS true
    alt Not found, belongs to another user, or soft-deleted
        Handler-->>Caller: 404 VEHICLE_NOT_FOUND
    end
    Handler-->>Caller: 200 OK VehicleResponse
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["GET /api/v1/vehicles/id"]) --> Auth{"Valid Bearer JWT & UUID?"}
    Auth -- Bad JWT --> Err401["401 UNAUTHENTICATED"]
    Auth -- Bad UUID --> Err422["422 INVALID_VEHICLE_DATA"]
    Auth -- Yes --> Own{"Exists AND user_id == caller AND is_active?"}
    Own -- No --> Err404["404 VEHICLE_NOT_FOUND"]
    Own -- Yes --> Ok200(["200 OK VehicleResponse"])
```
