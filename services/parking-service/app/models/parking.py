import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Time, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_number: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    vehicle_type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_charging_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="slot")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Vehicle snapshot captured at booking time (since vehicles live in vehicle_db)
    vehicle_number_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_type_snapshot: Mapped[str] = mapped_column(String(10), nullable=False)
    is_ev_snapshot: Mapped[bool] = mapped_column(Boolean, nullable=False)

    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parking_slots.id"), nullable=False
    )
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    requires_charging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PAYMENT_PENDING")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    slot: Mapped["ParkingSlot"] = relationship("ParkingSlot", back_populates="bookings")


def seed_default_slots(db: Session) -> None:
    """Seed the 100 parking slots (C01-C60, B01-B40) if the table is empty."""
    count = db.execute(select(func.count(ParkingSlot.id))).scalar_one()
    if count > 0:
        return

    slots: list[ParkingSlot] = []
    # C01-C50: normal CAR slots; C51-C60: EV charging CAR slots
    for i in range(1, 61):
        slots.append(
            ParkingSlot(
                slot_number=f"C{i:02d}",
                vehicle_type="CAR",
                is_charging_enabled=(i >= 51),
            )
        )
    # B01-B35: normal BIKE slots; B36-B40: EV charging BIKE slots
    for i in range(1, 41):
        slots.append(
            ParkingSlot(
                slot_number=f"B{i:02d}",
                vehicle_type="BIKE",
                is_charging_enabled=(i >= 36),
            )
        )
    db.add_all(slots)
    db.commit()
