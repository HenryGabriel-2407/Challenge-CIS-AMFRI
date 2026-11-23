"""Engine, sessões e dependência de banco de dados (SQLAlchemy 2.x)."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from challenge.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine(), expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """Dependência FastAPI: uma sessão por requisição, sempre fechada."""
    with SessionLocal() as session:
        yield session
