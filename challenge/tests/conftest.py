"""Fixture de testes: SQLite em memória, sem qualquer conexão com PostgreSQL."""

import os
from collections.abc import Generator

from cryptography.fernet import Fernet

# Definido ANTES de importar a aplicação: settings e crypto são singletons lazy.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "chave-de-teste-apenas-com-48-bytes-de-tamanho-seguro!"
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["ALGORITHM"] = "HS256"
os.environ["ADMIN_EMAIL"] = "admin@elo.saude"
os.environ["ADMIN_PASSWORD"] = "Admin@Elo2026"
os.environ["CREATE_SCHEMA_ON_STARTUP"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from challenge.app import app  # noqa: E402
from challenge.database import get_session  # noqa: E402
from challenge.enums import FacilityType  # noqa: E402
from challenge.models import Base, Facility  # noqa: E402
from challenge.seed import seed_demo_data  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        seed_demo_data(db)
        yield db
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        with TestingSessionLocal() as db:
            yield db

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def facility_ids(session: Session) -> dict[str, str]:
    return {
        "hospital": str(session.query(Facility).filter(Facility.type == FacilityType.HOSPITAL).first().id),
        "ubs": str(session.query(Facility).filter(Facility.type == FacilityType.UBS).first().id),
    }


@pytest.fixture()
def auth_headers(client: TestClient):
    def _login(email: str, password: str = "Senha@123") -> dict[str, str]:
        response = client.post("/api/auth/login", data={"username": email, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login
