# Topic 3: Schema Validation & Serialization (`app/schemas/*.py`)

This file explains every Pydantic v2 and typing built-in used to validate incoming JSON requests and serialize outgoing JSON responses.

**Contents:**
1. [`BaseModel`](#1-basemodel)
2. [`ConfigDict(...)`](#2-configdict)
3. [`Field(...)`](#3-field)
4. [`EmailStr`](#4-emailstr)
5. [`Literal[...]`](#5-literal)
6. [`@field_validator(...)`](#6-field_validator)
7. [`model_validate(...)`](#7-model_validate)

---

## 1. `BaseModel`

* **Import:** `from pydantic import BaseModel`
* **In Simple Words:** The parent class for all API request and response schemas (Data Transfer Objects). Whenever a request arrives, Pydantic reads the JSON, converts types (e.g. string `"2026-11-26"` $\rightarrow$ `datetime.date`), and rejects bad inputs with `422` before your route function runs.
* **Project Example (`services/parking-service/app/schemas/parking.py`):**
  ```python
  class BookingCreateRequest(BaseModel):
      vehicle_id: uuid.UUID
      date: date
      start_time: time
      end_time: time
      requires_charging: bool
  ```

---

## 2. `ConfigDict(...)`

* **Import:** `from pydantic import ConfigDict`
* **In Simple Words:** Settings dictionary assigned to `model_config` on a `BaseModel` class to customize how Pydantic reads and serializes data.

### Key Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `from_attributes` | `bool` | `False` | When `True`, Pydantic can read fields from object attributes (`orm_obj.email`) instead of requiring a dict (`orm_obj["email"]`). Essential for SQLAlchemy models! |
| `str_strip_whitespace` | `bool` | `False` | Automatically trims leading/trailing spaces on all string fields. |
| `extra` | `Literal["ignore", "forbid", "allow"]` | `"ignore"` | Controls whether unknown extra JSON keys from the client are ignored or rejected. |

* **Project Example (`services/vehicle-service/app/schemas/vehicle.py`):**
  ```python
  class VehicleResponse(BaseModel):
      id: uuid.UUID
      vehicle_number: str
      model_config = ConfigDict(from_attributes=True)
  ```

---

## 3. `Field(...)`

* **Import:** `from pydantic import Field`
* **In Simple Words:** Adds validation constraints, defaults, and OpenAPI documentation to a single schema field.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `default` | `Any` | `PydanticUndefined` | Default value if omitted (use `...` or omit `default` to mark required). |
| `min_length` / `max_length` | `int` | `None` | Minimum/maximum string length (e.g. `min_length=6, max_length=6` for OTP). |
| `pattern` | `str` | `None` | Regular expression that string must match (e.g. `r"^\d{6}$"`). |
| `gt` / `ge` / `lt` / `le` | `int \| float \| Decimal` | `None` | Numeric range checks (`gt=0` = strictly greater than zero). |
| `description` | `str` | `None` | Documentation text shown in Swagger UI. |

* **Project Example (`services/user-auth-service/app/schemas/auth.py`):**
  ```python
  code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
  ```

---

## 4. `EmailStr`

* **Import:** `from pydantic import EmailStr`
* **In Simple Words:** A validated string type that checks email syntax (must contain `@`, valid domain, no illegal whitespace/characters) using the `email-validator` package.
* **Project Example (`services/user-auth-service/app/schemas/auth.py`):**
  ```python
  from pydantic import BaseModel, EmailStr

  class SendCodeRequest(BaseModel):
      email: EmailStr
  ```

---

## 5. `Literal[...]`

* **Import:** `from typing import Literal`
* **In Simple Words:** Restricts a field strictly to a fixed set of exact constant values. Anything else fails validation with `422`.

### Syntax & Parameters
* `Literal[val1, val2, ...]` — pass any allowed constant strings, integers, or booleans inside square brackets.
* **Project Example:**
  ```python
  vehicle_type: Literal["CAR", "BIKE"]
  payment_method: Literal["UPI", "CARD", "WALLET"]
  ```

---

## 6. `@field_validator(...)`

* **Import:** `from pydantic import field_validator`
* **In Simple Words:** Decorator running custom Python transformation or validation logic on one or more fields before the route receives the schema.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `*fields` | `str` | **Required** | One or more field names to validate (e.g. `"vehicle_number"`). |
| `mode` | `Literal["before", "after", "wrap", "plain"]` | `"after"` | `"after"` runs after Pydantic type conversion; `"before"` runs on raw input before type conversion. |

* **Must be paired with `@classmethod`!**
* **Project Example (`services/vehicle-service/app/schemas/vehicle.py`):**
  ```python
  @field_validator("vehicle_number")
  @classmethod
  def normalize_vehicle_number(cls, value: str) -> str:
      cleaned = re.sub(r"[\s-]+", "", value.strip().upper())
      if not _PLATE_PATTERN.match(cleaned):
          raise ValueError("Invalid vehicle registration number.")
      return cleaned
  ```

---

## 7. `model_validate(...)`

* **Import:** Built-in class method on every `BaseModel` subclass.
* **In Simple Words:** Converts a dictionary or SQLAlchemy ORM object into a validated Pydantic schema instance.

### Parameters

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `obj` | `Any` | **Required** | The source dictionary or ORM instance (e.g., `user`, `vehicle`). |
| `from_attributes` | `bool \| None` | `None` | Optional one-off override of `ConfigDict(from_attributes=...)`. |
| `strict` | `bool \| None` | `None` | If `True`, disables automatic type coercion (e.g. `"123"` will not coerce to `123`). |

* **Returns:** Instance of the Pydantic schema class (`UserProfile`, `VehicleResponse`, etc.).
* **Project Example (`services/vehicle-service/app/api/v1/vehicles.py`):**
  ```python
  vehicle = _get_owned_active_vehicle(db, vehicle_id, user_id)
  return VehicleResponse.model_validate(vehicle)
  ```
