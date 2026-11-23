"""Enums de domínio do Elo Saúde."""

from enum import Enum


class FacilityType(str, Enum):
    HOSPITAL = "HOSPITAL"
    UPA = "UPA"
    UBS = "UBS"


class UserRole(str, Enum):
    HOSPITAL = "HOSPITAL"
    UBS = "UBS"
    ADMIN = "ADMIN"


class DischargeStatus(str, Enum):
    PENDENTE = "PENDENTE"
    CONFIRMADA = "CONFIRMADA"
    AGENDADA = "AGENDADA"
    NOTIFICADA = "NOTIFICADA"


class VisitPeriod(str, Enum):
    MANHA = "MANHA"
    TARDE = "TARDE"


class CarePlanStatus(str, Enum):
    PENDENTE = "PENDENTE"
    AGENDADA = "AGENDADA"
