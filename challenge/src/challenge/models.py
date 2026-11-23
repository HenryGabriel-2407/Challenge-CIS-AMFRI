"""Entidades SQLAlchemy 2.x — camada de domínio."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from challenge.crypto import EncryptedString, EncryptedText, decrypt_value
from challenge.enums import (
    CarePlanStatus,
    DischargeStatus,
    FacilityType,
    UserRole,
    VisitPeriod,
)


class Base(DeclarativeBase):
    pass


def enum_column(enum_type: type, length: int = 32):
    """Enum portável entre PostgreSQL e SQLite (VARCHAR + CHECK)."""
    return SAEnum(
        enum_type,
        native_enum=False,
        values_callable=lambda cls: [member.value for member in cls],
        length=length,
    )


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    type: Mapped[FacilityType] = mapped_column(enum_column(FacilityType), nullable=False, index=True)
    municipality: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list[User]] = relationship(back_populates="facility", lazy="selectin")
    discharges_origin: Mapped[list[Discharge]] = relationship(
        back_populates="origin", foreign_keys="Discharge.origin_facility_id", lazy="selectin"
    )
    discharges_target: Mapped[list[Discharge]] = relationship(
        back_populates="target_ubs", foreign_keys="Discharge.target_ubs_id", lazy="selectin"
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole), nullable=False, index=True)
    facility_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    facility: Mapped[Facility | None] = relationship(back_populates="users", lazy="selectin")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    cpf_encrypted: Mapped[str] = mapped_column(EncryptedString(256), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    phone_encrypted: Mapped[str | None] = mapped_column(EncryptedString(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    discharges: Mapped[list[Discharge]] = relationship(back_populates="patient", lazy="selectin")

    @property
    def cpf(self) -> str:
        """CPF decifrado somente em memória (nunca exposto cru nas respostas)."""
        return decrypt_value(self.cpf_encrypted)

    @property
    def phone(self) -> str | None:
        if self.phone_encrypted is None:
            return None
        return decrypt_value(self.phone_encrypted)


class Discharge(Base):
    __tablename__ = "discharges"
    __table_args__ = (
        Index("ix_discharges_status", "status"),
        Index("ix_discharges_target_ubs", "target_ubs_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    origin_facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    target_ubs_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    summary_encrypted: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    status: Mapped[DischargeStatus] = mapped_column(
        enum_column(DischargeStatus), nullable=False, default=DischargeStatus.PENDENTE
    )
    discharged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    patient: Mapped[Patient] = relationship(back_populates="discharges", lazy="selectin")
    origin: Mapped[Facility] = relationship(
        back_populates="discharges_origin", foreign_keys=[origin_facility_id], lazy="selectin"
    )
    target_ubs: Mapped[Facility] = relationship(
        back_populates="discharges_target", foreign_keys=[target_ubs_id], lazy="selectin"
    )
    prescriptions: Mapped[list[Prescription]] = relationship(
        back_populates="discharge", cascade="all, delete-orphan", lazy="selectin"
    )
    care_plan: Mapped[CarePlan | None] = relationship(
        back_populates="discharge", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="discharge", lazy="selectin")
    notifications: Mapped[list[NotificationLog]] = relationship(back_populates="discharge", lazy="selectin")

    @property
    def summary(self) -> str:
        return decrypt_value(self.summary_encrypted)


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    discharge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discharges.id", ondelete="CASCADE"), nullable=False)
    medication: Mapped[str] = mapped_column(String(150), nullable=False)
    dosage: Mapped[str] = mapped_column(String(80), nullable=False)
    frequency: Mapped[str] = mapped_column(String(80), nullable=False)
    instructions_encrypted: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    discharge: Mapped[Discharge] = relationship(back_populates="prescriptions")

    @property
    def instructions(self) -> str | None:
        if self.instructions_encrypted is None:
            return None
        return decrypt_value(self.instructions_encrypted)


class CarePlan(Base):
    __tablename__ = "care_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    discharge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discharges.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    instructions_encrypted: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    visit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    period: Mapped[VisitPeriod | None] = mapped_column(enum_column(VisitPeriod), nullable=True)
    status: Mapped[CarePlanStatus] = mapped_column(
        enum_column(CarePlanStatus), nullable=False, default=CarePlanStatus.PENDENTE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    discharge: Mapped[Discharge] = relationship(back_populates="care_plan")

    @property
    def instructions(self) -> str:
        return decrypt_value(self.instructions_encrypted)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    discharge_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discharges.id", ondelete="SET NULL"), nullable=True
    )
    actor_email: Mapped[str] = mapped_column(String(150), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    discharge: Mapped[Discharge | None] = relationship(back_populates="audit_logs")


class NotificationLog(Base):
    """Registro do aviso simulado enviado ao paciente (canal, mensagem e timestamp)."""

    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    discharge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discharges.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="WHATSAPP_SIMULADO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    discharge: Mapped[Discharge] = relationship(back_populates="notifications")
