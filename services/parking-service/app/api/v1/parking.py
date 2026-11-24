from datetime import date, datetime, time, timedelta
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.clock import as_utc, get_now
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import AuthContext, get_auth_context
from app.models.parking import Booking, ParkingSlot
from app.schemas.parking import (
    AvailabilityResponse,
    BookingCancelResponse,
    BookingCreateRequest,
    BookingListResponse,
    BookingResponse,
)
from app.services.clients import (
    PaymentServiceClient,
    VehicleServiceClient,
    get_payment_client,
    get_vehicle_client,
)
from app.services.rules import (
    calculate_booking_amount,
    calculate_hourly_rate,
    can_cancel_booking,
    validate_booking_interval,
    validate_charging_compatibility,
)

router = APIRouter(prefix="/api/v1/parking", tags=["parking"])

HOLD_DURATION_MINUTES = 5


def _active_booking_filter(now_utc: datetime):
    return or_(
        Booking.status == "CONFIRMED",
        and_(Booking.status == "PAYMENT_PENDING", Booking.hold_expires_at > now_utc),
    )


def _format_time(t: time) -> str:
    return t.strftime("%H:%M")


def _to_booking_response(booking: Booking, slot_number: str) -> BookingResponse:
    return BookingResponse(
        booking_id=booking.id,
        vehicle_id=booking.vehicle_id,
        vehicle_number_snapshot=booking.vehicle_number_snapshot,
        vehicle_type_snapshot=booking.vehicle_type_snapshot,
        is_ev_snapshot=booking.is_ev_snapshot,
        slot_number=slot_number,
        date=booking.booking_date,
        start_time=_format_time(booking.start_time),
        end_time=_format_time(booking.end_time),
        requires_charging=booking.requires_charging,
        amount=booking.amount,
        status=booking.status,
        payment_id=booking.payment_id,
        hold_expires_at=booking.hold_expires_at,
        cancelled_at=booking.cancelled_at,
    )


def _expire_stale_holds(db: Session, bookings: list[Booking], now_utc: datetime) -> None:
    changed = False
    for b in bookings:
        if b.status == "PAYMENT_PENDING" and b.hold_expires_at is not None and as_utc(b.hold_expires_at) <= now_utc:
            b.status = "EXPIRED"
            changed = True
    if changed:
        db.commit()


@router.get("/availability", response_model=AvailabilityResponse)
def check_availability(
    booking_date: date = Query(alias="date"),
    start_time: time = Query(...),
    end_time: time = Query(...),
    vehicle_id: uuid.UUID = Query(...),
    requires_charging: bool = Query(...),
    auth: AuthContext = Depends(get_auth_context),
    now: datetime = Depends(get_now),
    db: Session = Depends(get_db),
    vehicle_client: VehicleServiceClient = Depends(get_vehicle_client),
):
    validate_booking_interval(booking_date, start_time, end_time, now)

    vehicle = vehicle_client.get_owned_vehicle(
        vehicle_id=vehicle_id,
        bearer_token=auth.raw_token,
    )
    validate_charging_compatibility(vehicle.is_ev, requires_charging)

    now_utc = as_utc(now)
    compatible_slot_ids = list(
        db.execute(
            select(ParkingSlot.id).where(
                ParkingSlot.vehicle_type == vehicle.vehicle_type,
                ParkingSlot.is_charging_enabled.is_(requires_charging),
            )
        ).scalars().all()
    )

    if not compatible_slot_ids:
        available_count = 0
    else:
        occupied_slot_ids = set(
            db.execute(
                select(Booking.slot_id)
                .where(
                    Booking.slot_id.in_(compatible_slot_ids),
                    Booking.booking_date == booking_date,
                    Booking.start_time < end_time,
                    Booking.end_time > start_time,
                    _active_booking_filter(now_utc),
                )
                .distinct()
            ).scalars().all()
        )
        available_count = len(compatible_slot_ids) - len(occupied_slot_ids)

    return AvailabilityResponse(
        available=available_count > 0,
        available_slots=available_count,
        vehicle_type=vehicle.vehicle_type,
        is_ev=vehicle.is_ev,
        requires_charging=requires_charging,
        rate_per_hour=calculate_hourly_rate(requires_charging),
    )


@router.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreateRequest,
    auth: AuthContext = Depends(get_auth_context),
    now: datetime = Depends(get_now),
    db: Session = Depends(get_db),
    vehicle_client: VehicleServiceClient = Depends(get_vehicle_client),
    payment_client: PaymentServiceClient = Depends(get_payment_client),
):
    now_utc = as_utc(now)

    # 1. Validate booking rules and vehicle ownership via Vehicle Service
    validate_booking_interval(payload.date, payload.start_time, payload.end_time, now)
    vehicle = vehicle_client.get_owned_vehicle(
        vehicle_id=payload.vehicle_id,
        bearer_token=auth.raw_token,
    )
    validate_charging_compatibility(vehicle.is_ev, payload.requires_charging)

    amount = calculate_booking_amount(payload.start_time, payload.end_time, payload.requires_charging)
    hold_expires_at = now_utc + timedelta(minutes=HOLD_DURATION_MINUTES)

    # 2. Lock compatible slots in PostgreSQL with FOR UPDATE to prevent double-booking
    slot_stmt = (
        select(ParkingSlot)
        .where(
            ParkingSlot.vehicle_type == vehicle.vehicle_type,
            ParkingSlot.is_charging_enabled.is_(payload.requires_charging),
        )
        .order_by(ParkingSlot.slot_number.asc())
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        slot_stmt = slot_stmt.with_for_update()

    compatible_slots = list(db.execute(slot_stmt).scalars().all())
    compatible_slot_ids = [s.id for s in compatible_slots]

    # 3. Check if this user already has an overlapping active booking
    user_overlap = db.execute(
        select(Booking.id)
        .where(
            Booking.user_id == auth.user_id,
            Booking.booking_date == payload.date,
            Booking.start_time < payload.end_time,
            Booking.end_time > payload.start_time,
            _active_booking_filter(now_utc),
        )
        .limit(1)
    ).scalar_one_or_none()
    if user_overlap is not None:
        raise AppError(
            409,
            "USER_BOOKING_OVERLAP",
            "You already have an overlapping active booking for this time interval.",
        )

    # 4. Find the first compatible slot that is not occupied
    occupied_slot_ids = set()
    if compatible_slot_ids:
        occupied_slot_ids = set(
            db.execute(
                select(Booking.slot_id)
                .where(
                    Booking.slot_id.in_(compatible_slot_ids),
                    Booking.booking_date == payload.date,
                    Booking.start_time < payload.end_time,
                    Booking.end_time > payload.start_time,
                    _active_booking_filter(now_utc),
                )
                .distinct()
            ).scalars().all()
        )

    chosen_slot = next((s for s in compatible_slots if s.id not in occupied_slot_ids), None)
    if chosen_slot is None:
        raise AppError(
            409,
            "NO_PARKING_CAPACITY",
            "No compatible parking slot is available for the requested interval.",
        )

    booking = Booking(
        user_id=auth.user_id,
        vehicle_id=vehicle.id,
        vehicle_number_snapshot=vehicle.vehicle_number,
        vehicle_type_snapshot=vehicle.vehicle_type,
        is_ev_snapshot=vehicle.is_ev,
        slot_id=chosen_slot.id,
        booking_date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        requires_charging=payload.requires_charging,
        status="PAYMENT_PENDING",
        amount=amount,
        hold_expires_at=hold_expires_at,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # 5. Create pending payment in Payment Service
    payment_id = payment_client.create_payment(
        booking_id=booking.id,
        user_id=auth.user_id,
        amount=booking.amount,
        expires_at=hold_expires_at,
    )
    booking.payment_id = payment_id
    db.commit()
    db.refresh(booking)

    return _to_booking_response(booking, chosen_slot.slot_number)


@router.get("/bookings", response_model=BookingListResponse)
def list_bookings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(get_auth_context),
    now: datetime = Depends(get_now),
    db: Session = Depends(get_db),
):
    now_utc = as_utc(now)
    total_items = db.execute(
        select(func.count(Booking.id)).where(Booking.user_id == auth.user_id)
    ).scalar_one()

    rows = list(
        db.execute(
            select(Booking)
            .options(joinedload(Booking.slot))
            .where(Booking.user_id == auth.user_id)
            .order_by(desc(Booking.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    _expire_stale_holds(db, rows, now_utc)

    return BookingListResponse(
        items=[_to_booking_response(b, b.slot.slot_number) for b in rows],
        page=page,
        page_size=page_size,
        total_items=total_items,
    )


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    now: datetime = Depends(get_now),
    db: Session = Depends(get_db),
):
    booking = db.execute(
        select(Booking)
        .options(joinedload(Booking.slot))
        .where(Booking.id == booking_id, Booking.user_id == auth.user_id)
    ).scalar_one_or_none()
    if booking is None:
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found.")

    _expire_stale_holds(db, [booking], as_utc(now))
    return _to_booking_response(booking, booking.slot.slot_number)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingCancelResponse)
def cancel_booking(
    booking_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    now: datetime = Depends(get_now),
    db: Session = Depends(get_db),
):
    booking = db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.user_id == auth.user_id)
    ).scalar_one_or_none()
    if booking is None:
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found.")

    now_utc = as_utc(now)
    _expire_stale_holds(db, [booking], now_utc)

    if booking.status != "CONFIRMED":
        raise AppError(
            409,
            "BOOKING_NOT_CANCELLABLE",
            f"Only confirmed bookings can be cancelled (current status: {booking.status}).",
        )

    if not can_cancel_booking(booking.booking_date, booking.start_time, now):
        raise AppError(
            409,
            "BOOKING_NOT_CANCELLABLE",
            "Confirmed bookings can only be cancelled before the booking start time.",
        )

    booking.status = "CANCELLED"
    booking.cancelled_at = now_utc
    db.commit()
    db.refresh(booking)

    return BookingCancelResponse(
        booking_id=booking.id,
        status=booking.status,
        cancelled_at=booking.cancelled_at,
    )
