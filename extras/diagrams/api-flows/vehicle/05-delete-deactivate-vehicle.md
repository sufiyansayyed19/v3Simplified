# API Flow: `DELETE /api/v1/vehicles/{vehicle_id}`

- **Service:** `vehicle-service` (`:8002`)
- **Router / Handler:** [vehicles.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/vehicle-service/app/api/v1/vehicles.py) $\rightarrow$ `deactivate_vehicle()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_current_user_id)`)
- **Database:** `vehicle_db` (`vehicles` — Soft Delete)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_current_user_id()
    participant Handler as vehicles.py: deactivate_vehicle()
    participant DB as vehicle_db (vehicles)

    Client->>Sec: DELETE /api/v1/vehicles/{vehicle_id} [Bearer JWT]
    Sec->>Sec: decode_access_token() locally
    alt Invalid JWT
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec-->>Handler: user_id (UUID)
    Handler->>DB: _get_owned_active_vehicle(id, user_id)
    alt Not found, foreign owner, or already inactive
        Handler-->>Client: 404 VEHICLE_NOT_FOUND
    end
    Handler->>DB: UPDATE vehicles SET is_active = false WHERE id = :vid + COMMIT
    Handler-->>Client: 200 OK {"id": ..., "is_active": false, "message": "Vehicle removed successfully"}
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["DELETE /api/v1/vehicles/id"]) --> Auth{"Valid Bearer JWT?"}
    Auth -- No --> Err401["401 UNAUTHENTICATED"]
    Auth -- Yes --> Own{"Owned active vehicle exists?"}
    Own -- No --> Err404["404 VEHICLE_NOT_FOUND"]
    Own -- Yes --> Soft["Set vehicle.is_active = False & commit"]
    Soft --> Ok200(["200 OK VehicleDeactivateResponse"])
```
