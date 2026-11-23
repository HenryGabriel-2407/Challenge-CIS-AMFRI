"""Testes do fluxo de contrarreferência do Elo Saúde."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from challenge.enums import DischargeStatus
from challenge.models import AuditLog, NotificationLog, Patient


def discharge_payload(facility_ids: dict[str, str]) -> dict:
    return {
        "patient": {
            "name": "Maria da Silva",
            "cpf": "529.982.247-25",  # CPF sintético válido
            "birth_date": "1944-03-12",
            "phone": "47999999999",
        },
        "origin_facility_id": facility_ids["hospital"],
        "target_ubs_id": facility_ids["ubs"],
        "summary": "Pós-operatório de cirurgia de fêmur; necessita curativo e fisioterapia domiciliar.",
        "prescriptions": [
            {
                "medication": "Paracetamol",
                "dosage": "500 mg",
                "frequency": "8 em 8 horas",
                "instructions": "Tomar após as refeições.",
            }
        ],
        "care_plan": {"instructions": "Avaliar dor, curativo e orientar a família sobre mobilização."},
    }


def create_discharge(client: TestClient, headers: dict[str, str], facility_ids: dict[str, str]) -> dict:
    response = client.post("/api/discharges/", json=discharge_payload(facility_ids), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_discharge_encrypts_sensitive_data_and_audits(
    client: TestClient,
    session: Session,
    facility_ids: dict[str, str],
    auth_headers,
):
    headers = auth_headers("hospital@elo.saude")
    body = create_discharge(client, headers, facility_ids)

    assert body["status"] == DischargeStatus.PENDENTE.value
    assert body["patient"]["cpf"] == "***.982.247-**"
    assert body["patient"]["phone"] == "*****9999"
    assert body["care_plan"]["status"] == "PENDENTE"

    patient = session.scalar(select(Patient).where(Patient.name == "Maria da Silva"))
    assert patient is not None
    assert "52998224725" not in patient.cpf_encrypted
    assert "47999999999" not in patient.phone_encrypted
    assert patient.cpf == "52998224725"  # decifra transparente no domínio

    audit = session.scalar(select(AuditLog).where(AuditLog.action == "DISCHARGE_CREATED"))
    assert audit is not None
    assert audit.actor_email == "hospital@elo.saude"


def test_ubs_lists_only_pending_discharges(
    client: TestClient, facility_ids: dict[str, str], auth_headers
):
    create_discharge(client, auth_headers("hospital@elo.saude"), facility_ids)

    response = client.get(
        f"/api/discharges/ubs/{facility_ids['ubs']}",
        headers=auth_headers("ubs@elo.saude"),
    )
    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 1
    assert items[0]["patient"]["name"] == "Maria da Silva"
    assert items[0]["status"] == "PENDENTE"


def test_full_flow_confirm_schedule_and_notify(
    client: TestClient, session: Session, facility_ids: dict[str, str], auth_headers
):
    hospital_headers = auth_headers("hospital@elo.saude")
    ubs_headers = auth_headers("ubs@elo.saude")

    discharge = create_discharge(client, hospital_headers, facility_ids)
    discharge_id = discharge["id"]
    visit_date = date.today().isoformat()

    confirmed = client.patch(f"/api/discharges/{discharge_id}/confirm", headers=ubs_headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "CONFIRMADA"
    assert confirmed.json()["confirmed_at"] is not None

    scheduled = client.patch(
        f"/api/discharges/{discharge_id}/schedule",
        json={"visit_date": visit_date, "period": "MANHA"},
        headers=ubs_headers,
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["status"] == "AGENDADA"
    assert scheduled.json()["care_plan"]["period"] == "MANHA"

    notification = client.get(f"/api/discharges/{discharge_id}/notify-patient", headers=ubs_headers)
    assert notification.status_code == 200, notification.text
    message = notification.json()["message"]
    assert date.today().strftime("%d/%m/%Y") in message
    assert "manhã (09:00 às 12:00)" in message
    assert notification.json()["channel"] == "WHATSAPP_SIMULADO"

    assert session.scalar(select(NotificationLog)) is not None
    second_attempt = client.get(f"/api/discharges/{discharge_id}/notify-patient", headers=ubs_headers)
    assert second_attempt.status_code == 409


def test_invalid_transition_and_rbac(client: TestClient, facility_ids: dict[str, str], auth_headers):
    hospital_headers = auth_headers("hospital@elo.saude")
    ubs_headers = auth_headers("ubs@elo.saude")
    discharge_id = create_discharge(client, hospital_headers, facility_ids)["id"]

    # UBS não pode criar alta; hospital não pode consultar a fila da UBS.
    assert client.post("/api/discharges/", json=discharge_payload(facility_ids), headers=ubs_headers).status_code == 403
    assert client.get(f"/api/discharges/ubs/{facility_ids['ubs']}", headers=hospital_headers).status_code == 403

    # Não é possível agendar antes de confirmar.
    scheduled = client.patch(
        f"/api/discharges/{discharge_id}/schedule",
        json={"visit_date": date.today().isoformat(), "period": "TARDE"},
        headers=ubs_headers,
    )
    assert scheduled.status_code == 409


def test_web_screens_hospital_ubs_and_patient(
    client: TestClient, facility_ids: dict[str, str], auth_headers
):
    discharge_id = create_discharge(client, auth_headers("hospital@elo.saude"), facility_ids)["id"]
    ubs_headers = auth_headers("ubs@elo.saude")

    confirm = client.patch(f"/api/discharges/{discharge_id}/confirm", headers=ubs_headers)
    assert confirm.status_code == 200
    schedule = client.patch(
        f"/api/discharges/{discharge_id}/schedule",
        json={"visit_date": date.today().isoformat(), "period": "TARDE"},
        headers=ubs_headers,
    )
    assert schedule.status_code == 200

    login = client.post(
        "/ui/login", data={"email": "ubs@elo.saude", "password": "Senha@123"}, follow_redirects=False
    )
    assert login.status_code == 303
    assert client.get("/ui/ubs").status_code == 200

    patient_page = client.get(f"/ui/paciente/{discharge_id}")
    assert patient_page.status_code == 200
    assert "continuidade do seu atendimento" in patient_page.text
