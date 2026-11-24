"""Create parking_slots and bookings tables

Revision ID: 0001_create_parking_tables
Revises: None
Create Date: 2026-11-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_create_parking_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parking_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slot_number", sa.String(10), nullable=False, unique=True),
        sa.Column("vehicle_type", sa.String(10), nullable=False),
        sa.Column("is_charging_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_number_snapshot", sa.String(20), nullable=False),
        sa.Column("vehicle_type_snapshot", sa.String(10), nullable=False),
        sa.Column("is_ev_snapshot", sa.Boolean(), nullable=False),
        sa.Column("slot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parking_slots.id"), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(timezone=False), nullable=False),
        sa.Column("end_time", sa.Time(timezone=False), nullable=False),
        sa.Column("requires_charging", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(20), nullable=False, server_default="PAYMENT_PENDING"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("bookings")
    op.drop_table("parking_slots")
