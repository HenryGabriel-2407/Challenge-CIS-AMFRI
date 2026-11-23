"""Endpoints da contrarreferência (altas hospitalares)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from challenge.enums import DischargeStatus, UserRole
from challenge.exceptions import ForbiddenError
from challenge.models import User
from challenge.schemas import (
    DischargeCreate,
    DischargeRead,
    DischargeSchedule,
    PatientNotification,
)
from challenge.security import TSession, require_roles
from challenge.services import DischargeService

router = APIRouter(prefix="/api/discharges", tags=["contrarreferência"])

HospitalUser = Annotated[User, Depends(require_roles(UserRole.HOSPITAL))]
UbsUser = Annotated[User, Depends(require_roles(UserRole.UBS))]
AnyStaff = Annotated[User, Depends(require_roles(UserRole.HOSPITAL, UserRole.UBS))]


@router.post("/", response_model=DischargeRead, status_code=status.HTTP_201_CREATED)
def create_discharge(
    data: DischargeCreate,
    session: TSession,
    current_user: HospitalUser,
):
    """Hospital/UPA registra a alta, prescrições e orientações de cuidado."""
    return DischargeService(session).create_discharge(data, current_user)


@router.get("/ubs/{ubs_id}", response_model=list[DischargeRead])
def list_pending_discharges(ubs_id: uuid.UUID, session: TSession, current_user: UbsUser):
    """UBS lista as altas pendentes de confirmação."""
    if current_user.role is UserRole.UBS and current_user.facility_id != ubs_id:
        raise ForbiddenError("Você só pode consultar as altas da sua UBS.")
    return DischargeService(session).list_for_ubs(ubs_id, [DischargeStatus.PENDENTE])


@router.patch("/{discharge_id}/confirm", response_model=DischargeRead)
def confirm_discharge(discharge_id: uuid.UUID, session: TSession, current_user: UbsUser):
    """UBS confirma o recebimento da contrarreferência."""
    return DischargeService(session).confirm(discharge_id, current_user)


@router.patch("/{discharge_id}/schedule", response_model=DischargeRead)
def schedule_visit(
    discharge_id: uuid.UUID,
    data: DischargeSchedule,
    session: TSession,
    current_user: UbsUser,
):
    """UBS agenda a visita domiciliar informando dia e período."""
    return DischargeService(session).schedule(discharge_id, data, current_user)


@router.get("/{discharge_id}/notify-patient", response_model=PatientNotification)
def notify_patient(discharge_id: uuid.UUID, session: TSession, current_user: AnyStaff):
    """Simula o envio da mensagem ao paciente e retorna o conteúdo gerado."""
    return DischargeService(session).notify_patient(discharge_id, current_user)
