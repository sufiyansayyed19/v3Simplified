# Vehicle Service API Contract

**Service Path:** `services/vehicle-service/` | **Port:** `8002` | **Database:** `vehicle_db` (`vehicles`)

---

## 1. Responsibilities
Vehicle Service is a **100% standalone CRUD microservice** owning registered vehicle records (`vehicles`). It validates the user's HS256 Bearer JWT locally using `JWT_SECRET_KEY`, normalizes license plates, and scopes all operations to the authenticated `user_id`.

Because `Parking Service` stores immutable vehicle snapshots (`vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`) on each booking at creation time, `Vehicle Service` does not make any outbound HTTP calls to `Parking Service`.

---

## 2. Endpoint Inventory (5 Endpoints — All Require Bearer JWT)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/vehicles` | Register a new active vehicle |
| `GET` | `/api/v1/vehicles` | List the current user's active vehicles |
| `GET` | `/api/v1/vehicles/{vehicle_id}` | Retrieve one active vehicle owned by the current user |
| `PUT` | `/api/v1/vehicles/{vehicle_id}` | Update `vehicle_number`, `vehicle_type`, and `is_ev` |
| `DELETE` | `/api/v1/vehicles/{vehicle_id}` | Soft-deactivate a vehicle (`is_active = false`) |

---

## 3. `POST /api/v1/vehicles`

### Request
```json
{
  "vehicle_number": "mh 12-ab 1234",
  "vehicle_type": "CAR",
  "is_ev": true
}
```

### Processing
1. Normalize `vehicle_number` (uppercase, strip spaces and hyphens → `"MH12AB1234"`).
2. Validate `vehicle_type` is `"CAR"` or `"BIKE"`.
3. Check if an active vehicle (`is_active = true`) with the same `user_id` and `vehicle_number` already exists (`409 VEHICLE_ALREADY_REGISTERED`).
4. Insert and return the new active vehicle (`201 Created`).

---

## 4. `GET /api/v1/vehicles` & `GET /api/v1/vehicles/{vehicle_id}`
- `GET /api/v1/vehicles` returns `{"vehicles": [...]}` containing all active vehicles for `user_id`.
- `GET /api/v1/vehicles/{vehicle_id}` returns the single active vehicle if owned by `user_id`, or `404 VEHICLE_NOT_FOUND`. (Also called by `Parking Service` forwarding the user's Bearer JWT during availability and booking creation.)

---

## 5. `PUT /api/v1/vehicles/{vehicle_id}` & `DELETE /api/v1/vehicles/{vehicle_id}`
- `PUT /api/v1/vehicles/{vehicle_id}` updates the vehicle after checking for duplicate active plate numbers under the same user.
- `DELETE /api/v1/vehicles/{vehicle_id}` sets `is_active = false` and returns:
  ```json
  {
    "id": "<vehicle-uuid>",
    "is_active": false,
    "message": "Vehicle removed successfully"
  }
  ```
