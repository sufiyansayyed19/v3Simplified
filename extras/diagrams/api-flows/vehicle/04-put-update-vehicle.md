# API Flow: `PUT /api/v1/vehicles/{vehicle_id}`

- **Service:** `vehicle-service` (`:8002`)
- **Router / Handler:** [vehicles.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/vehicle-service/app/api/v1/vehicles.py) $\rightarrow$ `update_vehicle()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_current_user_id)`)
- **Database:** `vehicle_db` (`vehicles`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_current_user_id()
    participant Schema as Pydantic (VehicleUpdate)
    participant Handler as vehicles.py: update_vehicle()
    participant DB as vehicle_db (vehicles)

    Client->>Sec: PUT /api/v1/vehicles/{vehicle_id} [Bearer JWT + JSON]
    Sec->>Sec: decode_access_token() locally
    alt Invalid JWT
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec-->>Schema: user_id
    Schema->>Schema: normalize_vehicle_number()
    alt Validation fails
        Schema-->>Client: 422 INVALID_VEHICLE_DATA
    end
    Schema-->>Handler: Validated payload + user_id
    Handler->>DB: _get_owned_active_vehicle(id, user_id)
    alt Missing, foreign owner, or inactive
        Handler-->>Client: 404 VEHICLE_NOT_FOUND
    end
    Handler->>DB: SELECT * FROM vehicles WHERE user_id=:uid AND vehicle_number=:plate AND is_active IS true AND id <> :vid
    alt Collides with another active vehicle
        Handler-->>Client: 409 VEHICLE_ALREADY_REGISTERED
    end
    Handler->>DB: UPDATE vehicle_number, vehicle_type, is_ev + COMMIT
    Handler-->>Client: 200 OK VehicleResponse
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["PUT /api/v1/vehicles/id"]) --> Auth{"Valid JWT & VehicleUpdate?"}
    Auth -- No --> ErrAuth["401 or 422"]
    Auth -- Yes --> Own{"Owned active vehicle exists?"}
    Own -- No --> Err404["404 VEHICLE_NOT_FOUND"]
    Own -- Yes --> Dup{"Duplicate active plate (excluding self id)?"}
    Dup -- Yes --> Err409["409 VEHICLE_ALREADY_REGISTERED"]
    Dup -- No --> Save["Update fields & db.commit()"]
    Save --> Ok200(["200 OK VehicleResponse"])
```
