"""Casos de uso da contrarreferência — regras de negócio do Elo Saúde."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from challenge.crypto import encrypt_value
from challenge.enums import (
    CarePlanStatus,
    DischargeStatus,
    FacilityType,
    UserRole,
    VisitPeriod,
)
from challenge.exceptions import ConflictError, ForbiddenError, NotFoundError
from challenge.models import (
    AuditLog,
    CarePlan,
    Discharge,
    Facility,
    NotificationLog,
    Patient,
    Prescription,
    User,
)
from challenge.schemas import (
    DischargeCreate,
    DischargeSchedule,
    PatientNotification,
)

PERIOD_LABEL = {
    VisitPeriod.MANHA: "manhã (09:00 às 12:00)",
    VisitPeriod.TARDE: "tarde (13:00 às 17:00)",
}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _audit(
    session: Session,
    *,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    discharge_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_email=actor.email,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            discharge_id=discharge_id,
            details=json.dumps(details or {}, ensure_ascii=False),
        )
    )


class DischargeService:
    def __init__(self, session: Session):
        self.session = session

    def _get_facility(self, facility_id: uuid.UUID) -> Facility:
        facility = self.session.get(Facility, facility_id)
        if facility is None or not facility.is_active:
            raise NotFoundError("Unidade de saúde não encontrada ou inativa.")
        return facility

    def _get_discharge(self, discharge_id: uuid.UUID) -> Discharge:
        discharge = self.session.get(Discharge, discharge_id)
        if discharge is None:
            raise NotFoundError("Alta hospitalar não encontrada.")
        return discharge

    def _authorize_ubs(self, discharge: Discharge, actor: User) -> None:
        if actor.role is UserRole.ADMIN:
            return
        if actor.role is not UserRole.UBS or actor.facility_id != discharge.target_ubs_id:
            raise ForbiddenError("Apenas a UBS de referência desta alta pode executar esta ação.")

    # -------------------------------------------------------------------
    # Hospital / UPA registra a alta
    # -------------------------------------------------------------------
    def create_discharge(self, data: DischargeCreate, actor: User) -> Discharge:
        origin = self._get_facility(data.origin_facility_id)
        target = self._get_facility(data.target_ubs_id)

        if origin.type not in (FacilityType.HOSPITAL, FacilityType.UPA):
            raise ConflictError("A unidade de origem deve ser um hospital ou UPA.")
        if target.type is not FacilityType.UBS:
            raise ConflictError("A unidade de destino deve ser uma UBS.")
        if actor.role is UserRole.UBS and actor.facility_id != target.id:
            raise ForbiddenError("A UBS só pode registrar altas destinadas a ela.")

        patient = Patient(
            name=data.patient.name,
            cpf_encrypted=encrypt_value(data.patient.cpf),
            birth_date=data.patient.birth_date,
            phone_encrypted=encrypt_value(data.patient.phone) if data.patient.phone else None,
        )
        discharge = Discharge(
            patient=patient,
            origin=origin,
            target_ubs=target,
            summary_encrypted=encrypt_value(data.summary),
            status=DischargeStatus.PENDENTE,
            discharged_at=data.discharged_at or _now(),
            prescriptions=[
                Prescription(
                    medication=item.medication,
                    dosage=item.dosage,
                    frequency=item.frequency,
                    instructions_encrypted=encrypt_value(item.instructions) if item.instructions else None,
                )
                for item in data.prescriptions
            ],
            care_plan=CarePlan(
                instructions_encrypted=encrypt_value(data.care_plan.instructions),
                status=CarePlanStatus.PENDENTE,
            ),
        )
        self.session.add(discharge)
        self.session.flush()

        _audit(
            self.session,
            actor=actor,
            action="DISCHARGE_CREATED",
            entity_type="Discharge",
            entity_id=discharge.id,
            discharge_id=discharge.id,
            details={"origin": origin.name, "target_ubs": target.name},
        )
        self.session.commit()
        self.session.refresh(discharge)
        return discharge

    # -------------------------------------------------------------------
    # UBS consulta, confirma e agenda
    # -------------------------------------------------------------------
    def list_for_ubs(
        self, ubs_id: uuid.UUID, statuses: list[DischargeStatus] | None = None
    ) -> list[Discharge]:
        target = self._get_facility(ubs_id)
        if target.type is not FacilityType.UBS:
            raise ConflictError("O identificador informado não corresponde a uma UBS.")

        statement = select(Discharge).where(Discharge.target_ubs_id == ubs_id)
        if statuses:
            statement = statement.where(Discharge.status.in_(statuses))
        statement = statement.order_by(Discharge.created_at.desc())
        return list(self.session.scalars(statement))

    def confirm(self, discharge_id: uuid.UUID, actor: User) -> Discharge:
        discharge = self._get_discharge(discharge_id)
        self._authorize_ubs(discharge, actor)

        if discharge.status is not DischargeStatus.PENDENTE:
            raise ConflictError(
                f"Não é possível confirmar uma alta no status {discharge.status.value}."
            )

        discharge.status = DischargeStatus.CONFIRMADA
        discharge.confirmed_at = _now()
        _audit(
            self.session,
            actor=actor,
            action="DISCHARGE_CONFIRMED",
            entity_type="Discharge",
            entity_id=discharge.id,
            discharge_id=discharge.id,
            details={"status": DischargeStatus.CONFIRMADA.value},
        )
        self.session.commit()
        self.session.refresh(discharge)
        return discharge

    def schedule(self, discharge_id: uuid.UUID, data: DischargeSchedule, actor: User) -> Discharge:
        discharge = self._get_discharge(discharge_id)
        self._authorize_ubs(discharge, actor)

        if discharge.status is not DischargeStatus.CONFIRMADA:
            raise ConflictError("Confirme o recebimento antes de agendar a visita.")
        if discharge.care_plan is None:
            raise ConflictError("Alta sem plano de cuidados não pode ser agendada.")

        discharge.care_plan.visit_date = data.visit_date
        discharge.care_plan.period = data.period
        discharge.care_plan.status = CarePlanStatus.AGENDADA
        discharge.status = DischargeStatus.AGENDADA

        _audit(
            self.session,
            actor=actor,
            action="VISIT_SCHEDULED",
            entity_type="CarePlan",
            entity_id=discharge.care_plan.id,
            discharge_id=discharge.id,
            details={"visit_date": data.visit_date.isoformat(), "period": data.period.value},
        )
        self.session.commit()
        self.session.refresh(discharge)
        return discharge

    # -------------------------------------------------------------------
    # Aviso simulado ao paciente
    # -------------------------------------------------------------------
    def _build_notification(self, discharge: Discharge) -> PatientNotification:
        if discharge.care_plan is None or not discharge.care_plan.visit_date or not discharge.care_plan.period:
            raise ConflictError("Agende a visita antes de notificar o paciente.")

        first_name = discharge.patient.name.strip().split()[0]
        visit_date = discharge.care_plan.visit_date.strftime("%d/%m/%Y")
        period = PERIOD_LABEL[discharge.care_plan.period]
        message = (
            f"Olá, {first_name}! A equipe da {discharge.target_ubs.name} confirma a continuidade "
            f"do seu atendimento no dia {visit_date}, no período da {period}. "
            "Nossa visita domiciliar será organizada pela UBS. "
            "Se precisar de algo antes disso, procure a unidade de referência."
        )
        return PatientNotification(
            channel="WHATSAPP_SIMULADO",
            patient_name=discharge.patient.name,
            message=message,
            visit_date=discharge.care_plan.visit_date,
            period=discharge.care_plan.period,
            logged_at=_now(),
            discharge_id=discharge.id,
        )

    def preview_notification(self, discharge_id: uuid.UUID) -> PatientNotification:
        """Monta a mensagem sem registrar envio — usada pela tela do paciente."""
        discharge = self._get_discharge(discharge_id)
        return self._build_notification(discharge)

    def notify_patient(self, discharge_id: uuid.UUID, actor: User) -> PatientNotification:
        discharge = self._get_discharge(discharge_id)
        if discharge.status is not DischargeStatus.AGENDADA:
            raise ConflictError("Agende a visita antes de notificar o paciente.")

        notification = self._build_notification(discharge)
        self.session.add(
            NotificationLog(
                discharge_id=discharge.id,
                channel=notification.channel,
                message=notification.message,
                created_at=notification.logged_at,
            )
        )
        discharge.status = DischargeStatus.NOTIFICADA
        discharge.notified_at = notification.logged_at
        _audit(
            self.session,
            actor=actor,
            action="PATIENT_NOTIFIED",
            entity_type="NotificationLog",
            entity_id=discharge.id,
            discharge_id=discharge.id,
            details={
                "channel": notification.channel,
                "visit_date": notification.visit_date.isoformat(),
            },
        )
        self.session.commit()
        return notification
