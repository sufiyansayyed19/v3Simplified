# Project Overview

## 1. Project Name
**Corporate Parking Reservation and Management System**

## 2. Purpose
The system provides company employees with a clean way to reserve limited corporate parking capacity. It supports registered cars and bikes, distinguishes normal spaces from EV charging spaces, allocates compatible spaces automatically using PostgreSQL row locking (`SELECT ... FOR UPDATE`), and confirms reservations after simulated payment succeeds.

The project demonstrates core microservice architecture fundamentals:
- **Database-per-Service isolation** (`user_db`, `vehicle_db`, `parking_db`, `payment_db`).
- **Stateless HS256 JWT authentication** across services.
- **Inter-service HTTP communication** via `httpx`.
- **Concurrency safety** using SQLAlchemy `.with_for_update()`.
- **Database migrations** demonstrated with Alembic in `parking-service`.

## 3. Problem Statement
An organization has 100 parking spaces for ~500 employees. The system ensures:
- employees can check whether compatible parking capacity is available for a requested time window;
- authenticated employees can reserve a space for a registered vehicle;
- simultaneous requests never assign the same slot to overlapping bookings;
- one user cannot hold overlapping bookings;
- EV charging reservations are matched only to charging-enabled slots;
- booking and payment history are preserved.

## 4. Operating Assumptions

| Item | Baseline Assumption |
|---|---|
| Expected users | 500 employees |
| Total parking capacity | 100 spaces (`C01–C60`, `B01–B40`) |
| Car spaces | 60 (`C01–C50` normal, `C51–C60` EV charging) |
| Bike spaces | 40 (`B01–B35` normal, `B36–B40` EV charging) |
| Operating hours | `07:00–22:00` (whole-hour slots) |
| Operating days | Monday–Saturday (Sunday closed) |
| Business timezone | `Asia/Kolkata` |
| Booking horizon | Today and tomorrow only (`start_time > now`) |
| Maximum booking duration | 12 hours (ending no later than `22:00`) |

## 5. Product Scope

### 5.1 Included in Scope
- Corporate-email OTP authentication (`COMPANY_EMAIL_DOMAIN`) issuing HS256 Bearer JWTs.
- User profile lookup (`GET /api/v1/users/me`).
- Vehicle registration, listing, retrieval, update, and soft deactivation (`is_active = false`).
- Vehicle plate normalization (`"mh 12-ab 1234"` → `"MH12AB1234"`).
- Informational availability lookup (`GET /api/v1/parking/availability`).
- Atomic slot allocation with 5-minute `PAYMENT_PENDING` holds and immutable vehicle snapshots (`vehicle_number_snapshot`, `vehicle_type_snapshot`, `is_ev_snapshot`).
- Pricing calculation (`₹10/hr` normal, `₹20/hr` with EV charging).
- Simulated payment creation and processing (`UPI`, `CARD`, `WALLET`).
- Internal payment-result callback to confirm or expire bookings.
- Booking history, detail retrieval, lazy hold expiry, and cancellation before `start_time`.

### 5.2 Outside Current Scope
- Custom API Gateway process (each microservice exposes its own `/docs` Swagger UI directly on ports `8001`–`8004`).
- Google OAuth or password-based login.
- Physical sensors, RFID, ANPR, check-in/check-out sessions, or kWh energy billing.
- Real payment gateways (Stripe/Razorpay).
- Redis, Celery, Kafka, or RabbitMQ background workers.
