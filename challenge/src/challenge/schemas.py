"""Schemas Pydantic v2 — validação de entrada e saída da API."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from challenge.crypto import mask_cpf, mask_phone
from challenge.enums import (
    CarePlanStatus,
    DischargeStatus,
    FacilityType,
    UserRole,
    VisitPeriod,
)


def _digits(value: str) -> str:
    return "".join(filter(str.isdigit, value))


def _valid_cpf(cpf: str) -> bool:
    digits = _digits(cpf)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for size in (9, 10):
        weight = range(size + 1, 1, -1)
        total = sum(int(digit) * factor for digit, factor in zip(digits[:size], weight))
        remainder = total % 11
        expected = 0 if remainder < 2 else 11 - remainder
        if int(digits[size]) != expected:
            return False
    return True


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Facilities / usuários
# ---------------------------------------------------------------------------
class FacilityRead(ORMModel):
    id: uuid.UUID
    name: str
    type: FacilityType
    municipality: str


class Token(ORMModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    user_name: str


# ---------------------------------------------------------------------------
# Paciente
# ---------------------------------------------------------------------------
class PatientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    cpf: str
    birth_date: date
    phone: str | None = None

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, value: str) -> str:
        if not _valid_cpf(value):
            raise ValueError("CPF inválido.")
        return _digits(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = _digits(value)
        if len(digits) not in (10, 11):
            raise ValueError("Telefone deve ter 10 ou 11 dígitos.")
        return digits

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date) -> date:
        if value >= date.today():
            raise ValueError("Data de nascimento deve ser no passado.")
        return value


class PatientRead(ORMModel):
    id: uuid.UUID
    name: str
    cpf: str
    birth_date: date
    phone: str | None = None

    @field_validator("cpf")
    @classmethod
    def hide_cpf(cls, value: str) -> str:
        return mask_cpf(value) or "***.***.***-**"

    @field_validator("phone")
    @classmethod
    def hide_phone(cls, value: str | None) -> str | None:
        return mask_phone(value)


# ---------------------------------------------------------------------------
# Prescrição e plano de cuidados
# ---------------------------------------------------------------------------
class PrescriptionCreate(BaseModel):
    medication: str = Field(min_length=2, max_length=150)
    dosage: str = Field(min_length=1, max_length=80)
    frequency: str = Field(min_length=1, max_length=80)
    instructions: str | None = Field(default=None, max_length=1000)


class PrescriptionRead(ORMModel):
    id: uuid.UUID
    medication: str
    dosage: str
    frequency: str
    instructions: str | None = None


class CarePlanCreate(BaseModel):
    instructions: str = Field(min_length=5, max_length=2000)


class CarePlanRead(ORMModel):
    id: uuid.UUID
    instructions: str
    visit_date: date | None = None
    period: VisitPeriod | None = None
    status: CarePlanStatus


class DischargeSchedule(BaseModel):
    visit_date: date
    period: VisitPeriod

    @field_validator("visit_date")
    @classmethod
    def validate_visit_date(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("A data da visita não pode ser no passado.")
        return value


# ---------------------------------------------------------------------------
# Alta hospitalar
# ---------------------------------------------------------------------------
class DischargeCreate(BaseModel):
    patient: PatientCreate
    origin_facility_id: uuid.UUID
    target_ubs_id: uuid.UUID
    summary: str = Field(min_length=10, max_length=3000)
    discharged_at: datetime | None = None
    prescriptions: list[PrescriptionCreate] = Field(min_length=1)
    care_plan: CarePlanCreate


class DischargeRead(ORMModel):
    id: uuid.UUID
    patient: PatientRead
    origin: FacilityRead
    target_ubs: FacilityRead
    summary: str
    status: DischargeStatus
    discharged_at: datetime
    confirmed_at: datetime | None = None
    notified_at: datetime | None = None
    prescriptions: list[PrescriptionRead]
    care_plan: CarePlanRead | None = None


# ---------------------------------------------------------------------------
# Notificação simulada ao paciente
# ---------------------------------------------------------------------------
class PatientNotification(BaseModel):
    channel: str
    patient_name: str
    message: str
    visit_date: date
    period: VisitPeriod
    logged_at: datetime
    discharge_id: uuid.UUID
