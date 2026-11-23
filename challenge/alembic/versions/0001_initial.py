"""Migração inicial — Elo Saúde (schema completo do MVP).

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


def upgrade() -> None:
    op.create_table(
        "facilities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("cnpj", sa.String(20), nullable=True, unique=True),
        sa.Column(
            "type",
            _enum("facilitytype", "HOSPITAL", "UPA", "UBS"),
            nullable=False,
        ),
        sa.Column("municipality", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_facilities_type", "facilities", ["type"])

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            _enum("userrole", "HOSPITAL", "UBS", "ADMIN"),
            nullable=False,
        ),
        sa.Column("facility_id", sa.Uuid(), sa.ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("cpf_encrypted", sa.String(256), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("phone_encrypted", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "discharges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("origin_facility_id", sa.Uuid(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("target_ubs_id", sa.Uuid(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("summary_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "status",
            _enum("dischargestatus", "PENDENTE", "CONFIRMADA", "AGENDADA", "NOTIFICADA"),
            nullable=False,
        ),
        sa.Column("discharged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_discharges_status", "discharges", ["status"])
    op.create_index("ix_discharges_target_ubs", "discharges", ["target_ubs_id"])

    op.create_table(
        "prescriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("discharge_id", sa.Uuid(), sa.ForeignKey("discharges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("medication", sa.String(150), nullable=False),
        sa.Column("dosage", sa.String(80), nullable=False),
        sa.Column("frequency", sa.String(80), nullable=False),
        sa.Column("instructions_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "care_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("discharge_id", sa.Uuid(), sa.ForeignKey("discharges.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("instructions_encrypted", sa.Text(), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=True),
        sa.Column("period", _enum("visitperiod", "MANHA", "TARDE"), nullable=True),
        sa.Column("status", _enum("careplanstatus", "PENDENTE", "AGENDADA"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("discharge_id", sa.Uuid(), sa.ForeignKey("discharges.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_email", sa.String(150), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(50), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("discharge_id", sa.Uuid(), sa.ForeignKey("discharges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False, server_default="WHATSAPP_SIMULADO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notification_logs")
    op.drop_table("audit_logs")
    op.drop_table("care_plans")
    op.drop_table("prescriptions")
    op.drop_index("ix_discharges_target_ubs", table_name="discharges")
    op.drop_index("ix_discharges_status", table_name="discharges")
    op.drop_table("discharges")
    op.drop_table("patients")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_facilities_type", table_name="facilities")
    op.drop_table("facilities")
