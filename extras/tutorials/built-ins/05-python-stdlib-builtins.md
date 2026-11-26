# Topic 5: Python Standard Library Built-ins Used Directly

This file covers every Python standard library function, class, and decorator called directly in `ParkingSimplified`, with full parameter breakdowns and real code examples.

**Contents:**
1. [`uuid.uuid4()`, `uuid.UUID(...)` & `.hex`](#1-uuiduuid4-uuiduuid--hex)
2. [`secrets.randbelow(...)`](#2-secretsrandbelow)
3. [`datetime.now(...)`](#3-datetimenow)
4. [`datetime.combine(...)`](#4-datetimecombine)
5. [`timedelta(...)`](#5-timedelta)
6. [`timezone.utc`](#6-timezoneutc)
7. [`ZoneInfo(...)`](#7-zoneinfo)
8. [`Decimal(...)`](#8-decimal)
9. [`ABC` & `@abstractmethod`](#9-abc--abstractmethod)
10. [`@dataclass`](#10-dataclass)
11. [`re.compile(...)` & `re.sub(...)`](#11-recompile--resub)
12. [`Generator[...]`](#12-generator)

---

## 1. `uuid.uuid4()`, `uuid.UUID(...)` & `.hex`

* **Import:** `import uuid`
* **In Simple Words:** Generates random 128-bit universally unique identifiers and converts between strings and UUID objects.

| Function / Attribute | Parameters | Returns | What it does |
| :--- | :--- | :--- | :--- |
| `uuid.uuid4()` | None | `uuid.UUID` | Generates a cryptographically random v4 UUID (`e.g. 9f8b2c4e-...`). |
| `uuid.UUID(hex_or_str)` | `hex: str` (UUID string) | `uuid.UUID` | Parses and validates a string like `"9f8b2c4e-..."` into a `UUID` object (raises `ValueError` if invalid). |
| `my_uuid.hex` | Property (no params) | `str` (32 chars) | Returns the UUID without hyphens. |

* **Project Example (`services/payment-service/app/api/v1/payments.py` & `security.py`):**
  ```python
  txn_id = f"TXN{uuid.uuid4().hex[:10].upper()}"  # e.g. "TXN4B8C1E0A2F"
  user_id = uuid.UUID(payload["sub"])
  ```

---

## 2. `secrets.randbelow(...)`

* **Import:** `import secrets`
* **In Simple Words:** Cryptographically secure random integer generator (CSPRNG). Used instead of `random.randint` for security-sensitive 6-digit OTPs.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `exclusive_upper_bound` | `int` | **Required** | Generates a random integer `k` where `0 <= k < exclusive_upper_bound`. |

* **Returns:** `int`.
* **Project Example (`services/user-auth-service/app/core/security.py`):**
  ```python
  def generate_otp_code() -> str:
      return f"{secrets.randbelow(1_000_000):06d}"  # e.g. "048291"
  ```

---

## 3. `datetime.now(...)`

* **Import:** `from datetime import datetime, timezone`
* **In Simple Words:** Returns the current date and time.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `tz` | `tzinfo \| None` | `None` | Always pass `timezone.utc` or `ZoneInfo(...)` so the returned `datetime` is **timezone-aware** (prevents naive-vs-aware comparison crashes). |

* **Returns:** `datetime`.
* **Project Example (`services/user-auth-service/app/api/v1/auth.py`):**
  ```python
  def _utcnow() -> datetime:
      return datetime.now(timezone.utc)
  ```

---

## 4. `datetime.combine(...)`

* **Import:** `from datetime import datetime`
* **In Simple Words:** Merges a separate `date` and `time` object into a single `datetime` object.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `date` | `datetime.date` | **Required** | The calendar date (e.g. `booking.booking_date`). |
| `time` | `datetime.time` | **Required** | The clock time (e.g. `booking.start_time`). |
| `tzinfo` | `tzinfo \| None` | `time.tzinfo` | Attaches a timezone (e.g. `ZoneInfo("Asia/Kolkata")`) to the combined `datetime`. |

* **Returns:** `datetime`.
* **Project Example (`services/parking-service/app/services/rules.py`):**
  ```python
  start_local = datetime.combine(booking_date, start_time, tzinfo=facility_tz)
  if start_local <= now_local:
      raise AppError(400, "PAST_BOOKING_NOT_ALLOWED", "Booking start time must be in the future.")
  ```

---

## 5. `timedelta(...)`

* **Import:** `from datetime import timedelta`
* **In Simple Words:** Represents a duration of time that can be added to or subtracted from `datetime` objects.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `days` | `float` | `0` | Number of days. |
| `seconds` | `float` | `0` | Number of seconds. |
| `minutes` | `float` | `0` | Number of minutes (e.g. `timedelta(minutes=5)` for booking hold TTL). |
| `hours` | `float` | `0` | Number of hours. |

* **Returns:** `timedelta` duration object.
* **Project Example (`services/parking-service/app/api/v1/parking.py`):**
  ```python
  hold_expires_at = now_utc + timedelta(minutes=HOLD_DURATION_MINUTES)
  ```

---

## 6. `timezone.utc`

* **Import:** `from datetime import timezone`
* **In Simple Words:** Constant `tzinfo` object representing Coordinated Universal Time (UTC+0). All timestamps stored in PostgreSQL use UTC.
* **Project Example (`services/payment-service/app/api/v1/payments.py`):**
  ```python
  def _as_utc(dt: datetime) -> datetime:
      return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
  ```

---

## 7. `ZoneInfo(...)`

* **Import:** `from zoneinfo import ZoneInfo`
* **In Simple Words:** Standard library IANA timezone object handling regional offsets and daylight saving rules.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `key` | `str` | **Required** | IANA timezone name (e.g. `"Asia/Kolkata"`). |

* **Returns:** `ZoneInfo` timezone object.
* **Project Example (`services/parking-service/app/services/rules.py`):**
  ```python
  facility_tz = ZoneInfo(settings.FACILITY_TIMEZONE)  # "Asia/Kolkata"
  now_local = as_utc(now).astimezone(facility_tz)
  ```

---

## 8. `Decimal(...)`

* **Import:** `from decimal import Decimal`
* **In Simple Words:** Exact base-10 arithmetic for money calculations, avoiding binary floating-point rounding bugs (`0.1 + 0.2 != 0.3`).

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `value` | `str \| int \| Decimal` | `"0"` | Pass a **string** like `"10.00"` (never a float like `10.1`) to guarantee exact decimal representation. |

* **Returns:** `Decimal`.
* **Project Example (`services/parking-service/app/services/rules.py`):**
  ```python
  rate = Decimal("15.00") if requires_charging else Decimal("10.00")
  amount = (rate * Decimal(hours)).quantize(Decimal("0.01"))
  ```

---

## 9. `ABC` & `@abstractmethod`

* **Import:** `from abc import ABC, abstractmethod`
* **In Simple Words:** Defines an abstract base interface (`class EmailSender(ABC)`) requiring subclasses (`ConsoleEmailSender`) to implement every method decorated with `@abstractmethod`.
* **Project Example (`services/user-auth-service/app/services/email_sender.py`):**
  ```python
  class EmailSender(ABC):
      @abstractmethod
      def send_otp(self, email: str, code: str, expires_minutes: int) -> None:
          """Deliver a one-time verification code to the user's corporate email."""
  ```

---

## 10. `@dataclass`

* **Import:** `from dataclasses import dataclass`
* **In Simple Words:** Class decorator that auto-generates `__init__`, `__repr__`, and `__eq__` from type-annotated class fields.

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `frozen` | `bool` | `False` | If `True`, makes instances immutable (read-only after creation). |
| `slots` | `bool` | `False` | Reduces memory usage per instance. |

* **Project Example (`services/parking-service/app/core/security.py`):**
  ```python
  @dataclass
  class AuthContext:
      user_id: uuid.UUID
      raw_token: str
  ```

---

## 11. `re.compile(...)` & `re.sub(...)`

* **Import:** `import re`
* **In Simple Words:** Regular expression tools for matching and cleaning license plate strings.

| Function | Parameters | Returns | What it does |
| :--- | :--- | :--- | :--- |
| `re.compile(pattern)` | `pattern: str` (regex string) | `re.Pattern` | Pre-compiles a regex once at startup for fast repeated `.match(...)` calls. |
| `re.sub(pattern, repl, string)` | `pattern: str`, `repl: str`, `string: str` | `str` | Replaces every substring matching `pattern` with `repl`. |

* **Project Example (`services/vehicle-service/app/schemas/vehicle.py`):**
  ```python
  _PLATE_PATTERN = re.compile(r"^[A-Z0-9]{4,12}$")
  cleaned = re.sub(r"[\s-]+", "", value.strip().upper())
  ```

---

## 12. `Generator[...]`

* **Import:** `from collections.abc import Generator`
* **In Simple Words:** Return type annotation for Python generator functions using `yield`.
* **Type Parameters:** `Generator[YieldType, SendType, ReturnType]`
* **Project Example (`services/parking-service/app/core/database.py`):**
  ```python
  def get_db() -> Generator[Session, None, None]:
      db = SessionLocal()
      try:
          yield db
      finally:
          db.close()
  ```
