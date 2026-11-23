"""Unidades e usuários fictícios para demonstração do MVP."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from challenge.enums import FacilityType, UserRole
from challenge.models import Facility, User
from challenge.security import hash_password
from challenge.settings import get_settings

DEMO_PASSWORD = "Senha@123"


def seed_demo_data(session: Session) -> None:
    """Idempotente: só popula quando não existir nenhuma unidade."""
    if session.scalar(select(Facility).limit(1)) is not None:
        return

    hospital = Facility(
        name="Hospital Municipal Dr. João Batista",
        cnpj="00000000000191",
        type=FacilityType.HOSPITAL,
        municipality="Itajaí",
    )
    upa = Facility(
        name="UPA Centro",
        cnpj="00000000000276",
        type=FacilityType.UPA,
        municipality="Itajaí",
    )
    ubs = Facility(
        name="UBS Jardim das Palmeiras",
        cnpj="00000000000351",
        type=FacilityType.UBS,
        municipality="Itajaí",
    )
    ubs_praia = Facility(
        name="UBS Praia dos Amores",
        cnpj="00000000000436",
        type=FacilityType.UBS,
        municipality="Balneário Camboriú",
    )
    session.add_all([hospital, upa, ubs, ubs_praia])
    session.flush()

    settings = get_settings()
    session.add_all(
        [
            User(
                name="Equipe de Alta — Hospital",
                email="hospital@elo.saude",
                password_hash=hash_password(DEMO_PASSWORD),
                role=UserRole.HOSPITAL,
                facility_id=hospital.id,
            ),
            User(
                name="Equipe UPA",
                email="upa@elo.saude",
                password_hash=hash_password(DEMO_PASSWORD),
                role=UserRole.HOSPITAL,
                facility_id=upa.id,
            ),
            User(
                name="Equipe UBS Jardim das Palmeiras",
                email="ubs@elo.saude",
                password_hash=hash_password(DEMO_PASSWORD),
                role=UserRole.UBS,
                facility_id=ubs.id,
            ),
            User(
                name="Coordenação Elo Saúde",
                email=settings.ADMIN_EMAIL.strip().lower(),
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                facility_id=None,
            ),
        ]
    )
    session.commit()
