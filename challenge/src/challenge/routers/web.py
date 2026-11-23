"""Telas HTML simples (Jinja2) para Hospital, UBS e Paciente."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from challenge.database import get_session
from challenge.enums import DischargeStatus, FacilityType, UserRole, VisitPeriod
from challenge.exceptions import DomainError
from challenge.models import Facility, User
from challenge.schemas import (
    CarePlanCreate,
    DischargeCreate,
    DischargeSchedule,
    PatientCreate,
    PrescriptionCreate,
)
from challenge.security import authenticate_user, create_access_token, decode_access_token
from challenge.services import DischargeService
from challenge.settings import get_settings

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def _redirect(endpoint: str, message: str | None = None, kind: str = "erro") -> RedirectResponse:
    url = endpoint
    if message:
        url = f"{endpoint}?{kind}={quote(message)}"
    return RedirectResponse(url=url, status_code=303)


def _current_web_user(request: Request, session: Session) -> User | None:
    token = request.cookies.get("elo_token")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None
    email = payload.get("sub")
    if not email:
        return None
    user = session.scalar(select(User).where(User.email == email))
    return user if user and user.is_active else None


def _needs_login(user: User | None, allowed: tuple[UserRole, ...] | None = None) -> RedirectResponse | None:
    if user is None:
        return _redirect("/ui/login", "Faça login para continuar.")
    if allowed and user.role not in allowed and user.role is not UserRole.ADMIN:
        return _redirect("/ui/login", "Seu perfil não pode acessar esta tela.")
    return None


def _error_message(exc: Exception) -> str:
    if isinstance(exc, DomainError):
        return exc.message
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        return f"Campo inválido ({'.'.join(str(p) for p in first['loc'])}): {first['msg']}"
    return "Não foi possível concluir a operação. Verifique os dados informados."


@router.get("/")
def index() -> RedirectResponse:
    return RedirectResponse(url="/ui/login", status_code=302)


@router.get("/ui/login")
def login_page(request: Request, session: Session = Depends(get_session)):
    user = _current_web_user(request, session)
    if user:
        return RedirectResponse(url="/ui/hospital" if user.role is UserRole.HOSPITAL else "/ui/ubs", status_code=302)
    return templates.TemplateResponse(request=request, name="login.html", context={"user": None})


@router.post("/ui/login")
async def login_submit(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    user = authenticate_user(session, str(form.get("email", "")), str(form.get("password", "")))
    if user is None:
        return _redirect("/ui/login", "E-mail ou senha incorretos.")

    token = create_access_token({"sub": user.email, "role": user.role.value})
    destination = "/ui/hospital" if user.role in (UserRole.HOSPITAL, UserRole.ADMIN) else "/ui/ubs"
    response = RedirectResponse(url=destination, status_code=303)
    response.set_cookie(
        key="elo_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=get_settings().COOKIE_SECURE,
        max_age=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@router.post("/ui/logout")
def logout() -> RedirectResponse:
    response = _redirect("/ui/login")
    response.delete_cookie("elo_token")
    return response


@router.get("/ui/hospital")
def hospital_page(request: Request, session: Session = Depends(get_session)):
    user = _current_web_user(request, session)
    guard = _needs_login(user, (UserRole.HOSPITAL,))
    if guard:
        return guard
    ubs_list = session.scalars(
        select(Facility).where(Facility.type == FacilityType.UBS, Facility.is_active.is_(True))
    ).all()
    return templates.TemplateResponse(
        request=request, name="hospital.html", context={"user": user, "ubs_list": ubs_list, "form": {}}
    )


@router.post("/ui/hospital")
async def hospital_submit(request: Request, session: Session = Depends(get_session)):
    user = _current_web_user(request, session)
    guard = _needs_login(user, (UserRole.HOSPITAL,))
    if guard:
        return guard

    form = dict(await request.form())
    ubs_list = session.scalars(
        select(Facility).where(Facility.type == FacilityType.UBS, Facility.is_active.is_(True))
    ).all()

    try:
        origin_id = user.facility_id
        if origin_id is None:
            origin = session.scalar(
                select(Facility).where(Facility.type.in_([FacilityType.HOSPITAL, FacilityType.UPA]))
            )
            if origin is None:
                raise DomainError("Nenhuma unidade de origem disponível.")
            origin_id = origin.id

        payload = DischargeCreate(
            patient=PatientCreate(
                name=str(form.get("patient_name", "")),
                cpf=str(form.get("cpf", "")),
                birth_date=date.fromisoformat(str(form.get("birth_date", ""))),
                phone=str(form.get("phone", "")) or None,
            ),
            origin_facility_id=origin_id,
            target_ubs_id=uuid.UUID(str(form.get("target_ubs_id", ""))),
            summary=str(form.get("summary", "")),
            prescriptions=[
                PrescriptionCreate(
                    medication=str(form.get("medication", "")),
                    dosage=str(form.get("dosage", "")),
                    frequency=str(form.get("frequency", "")),
                    instructions=str(form.get("prescription_instructions", "")) or None,
                )
            ],
            care_plan=CarePlanCreate(instructions=str(form.get("care_instructions", ""))),
        )
        discharge = DischargeService(session).create_discharge(payload, user)
        return _redirect("/ui/hospital", f"Alta {str(discharge.id)[:8]} enviada à UBS com sucesso.", "ok")
    except (DomainError, ValidationError, ValueError) as exc:
        return templates.TemplateResponse(
            request=request,
            name="hospital.html",
            context={"user": user, "ubs_list": ubs_list, "form": form, "error": _error_message(exc)},
        )


@router.get("/ui/ubs")
def ubs_page(request: Request, session: Session = Depends(get_session)):
    user = _current_web_user(request, session)
    guard = _needs_login(user, (UserRole.UBS,))
    if guard:
        return guard
    if user.facility_id is None:
        return _redirect("/ui/hospital", "Selecione uma UBS vinculada para acessar o painel.")

    ubs = session.get(Facility, user.facility_id)
    discharges = DischargeService(session).list_for_ubs(user.facility_id)
    return templates.TemplateResponse(
        request=request,
        name="ubs.html",
        context={"user": user, "ubs": ubs, "discharges": discharges},
    )


@router.post("/ui/ubs/{discharge_id}/confirm")
def ubs_confirm(discharge_id: uuid.UUID, request: Request, session: Session = Depends(get_session)):
    user = _current_web_user(request, session)
    guard = _needs_login(user, (UserRole.UBS,))
    if guard:
        return guard
    try:
        DischargeService(session).confirm(discharge_id, user)
        return _redirect("/ui/ubs", "Recebimento confirmado.", "ok")
    except DomainError as exc:
        return _redirect("/ui/ubs", exc.message)


@router.post("/ui/ubs/{discharge_id}/schedule")
async def ubs_schedule(discharge_id: uuid.UUID, request: Request, session: Session = Depends(get_session)):
    user = _current_web_user(request, session)
    guard = _needs_login(user, (UserRole.UBS,))
    if guard:
        return guard
    form = await request.form()
    try:
        payload = DischargeSchedule(
            visit_date=date.fromisoformat(str(form.get("visit_date", ""))),
            period=VisitPeriod(str(form.get("period", ""))),
        )
        DischargeService(session).schedule(discharge_id, payload, user)
        return _redirect("/ui/ubs", "Visita domiciliar agendada.", "ok")
    except (DomainError, ValidationError, ValueError) as exc:
        return _redirect("/ui/ubs", _error_message(exc))


@router.post("/ui/ubs/{discharge_id}/notify")
def ubs_notify(discharge_id: uuid.UUID, request: Request, session: Session = Depends(get_session)):
    user = _current_web_user(request, session)
    guard = _needs_login(user, (UserRole.UBS,))
    if guard:
        return guard
    try:
        notification = DischargeService(session).notify_patient(discharge_id, user)
        return _redirect(f"/ui/paciente/{discharge_id}", f"Aviso registrado: {notification.channel}", "ok")
    except DomainError as exc:
        return _redirect("/ui/ubs", exc.message)


@router.get("/ui/paciente/{discharge_id}")
def patient_view(discharge_id: uuid.UUID, request: Request, session: Session = Depends(get_session)):
    user = _current_web_user(request, session)
    guard = _needs_login(user)
    if guard:
        return guard
    try:
        notification = DischargeService(session).preview_notification(discharge_id)
    except DomainError as exc:
        return _redirect("/ui/ubs", exc.message)
    return templates.TemplateResponse(
        request=request, name="paciente.html", context={"user": user, "notification": notification}
    )
