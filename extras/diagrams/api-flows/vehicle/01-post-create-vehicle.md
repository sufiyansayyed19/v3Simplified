# API Flow: `POST /api/v1/vehicles`

- **Service:** `vehicle-service` (`:8002`)
- **Router / Handler:** [vehicles.py](file:///c:/Users/skamalud/OneDrive%20-%20Capgemini/Documents/ParkingSimplified/services/vehicle-service/app/api/v1/vehicles.py) $\rightarrow$ `create_vehicle()`
- **Authentication:** `Authorization: Bearer <JWT>` (`Depends(get_current_user_id)` — local decode, zero DB lookup)
- **Database:** `vehicle_db` (`vehicles`)

---

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client as Employee Client
    participant Sec as security.py: get_current_user_id()
    participant Schema as Pydantic (VehicleCreate)
    participant Handler as vehicles.py: create_vehicle()
    participant DB as vehicle_db (vehicles)

    Client->>Sec: POST /api/v1/vehicles [Bearer JWT + JSON]
    Sec->>Sec: decode_access_token() locally (HS256)
    alt Missing or invalid/expired JWT
        Sec-->>Client: 401 UNAUTHENTICATED
    end
    Sec-->>Schema: user_id (UUID)
    Schema->>Schema: normalize_vehicle_number() -> strip spaces/hyphens, uppercase
    alt Invalid plate (not 4-20 alnum) or type not CAR/BIKE
        Schema-->>Client: 422 INVALID_VEHICLE_DATA
    end
    Schema-->>Handler: Validated payload + user_id
    Handler->>DB: SELECT * FROM vehicles WHERE user_id=:uid AND vehicle_number=:plate AND is_active IS true
    alt Active duplicate exists
        Handler-->>Client: 409 VEHICLE_ALREADY_REGISTERED
    end
    Handler->>DB: INSERT INTO vehicles (..., is_active=true) + COMMIT
    Handler-->>Client: 201 Created VehicleResponse
```

---

## Step-by-Step Decision Flow

```mermaid
flowchart TD
    Start(["POST /api/v1/vehicles"]) --> Auth{"Valid Bearer JWT?"}
    Auth -- No --> Err401["401 UNAUTHENTICATED"]
    Auth -- Yes --> Valid{"Pydantic & normalize_vehicle_number() valid?"}
    Valid -- No --> Err422["422 INVALID_VEHICLE_DATA"]
    Valid -- Yes --> Dup{"Active duplicate for same user_id?"}
    Dup -- Yes --> Err409["409 VEHICLE_ALREADY_REGISTERED"]
    Dup -- No --> Insert["Insert Vehicle (is_active=True) & commit"]
    Insert --> Ok201(["201 Created VehicleResponse"])
```
