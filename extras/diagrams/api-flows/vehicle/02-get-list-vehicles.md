# API Flow: `GET /api/v1/vehicles`

- **Service:** `vehicle-service` (`:8002`)
- **Router / Handler:** [vehicles.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/vehicle-service/app/api/v1/vehicles.py) $\rightarrow$ `list_vehicles()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_current_user_id)`)
- **Database:** `vehicle_db` (`vehicles`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_current_user_id()
    participant Handler as vehicles.py: list_vehicles()
    participant DB as vehicle_db (vehicles)

    Client->>Sec: GET /api/v1/vehicles [Bearer JWT]
    Sec->>Sec: decode_access_token() locally (HS256)
    alt Missing or invalid/expired JWT
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec-->>Handler: user_id (UUID)
    Handler->>DB: SELECT * FROM vehicles WHERE user_id=:uid AND is_active IS true ORDER BY created_at ASC
    DB-->>Handler: List of active owned Vehicle rows
    Handler-->>Client: 200 OK {"vehicles": [...]}
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["GET /api/v1/vehicles"]) --> Auth{"Valid Bearer JWT?"}
    Auth -- No --> Err401["401 UNAUTHENTICATED"]
    Auth -- Yes --> Query["Query active vehicles scoped to user_id (created_at ASC)"]
    Query --> Ok200(["200 OK VehicleListResponse"])
```
