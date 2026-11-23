"""Configuração centralizada carregada de variáveis de ambiente / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    DATABASE_URL: str = "sqlite:///./elo_saude.db"
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    ADMIN_EMAIL: str = "admin@elo.saude"
    ADMIN_PASSWORD: str = "Admin@Elo2026"

    BASE_URL: str = "http://localhost:8000"
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"
    COOKIE_SECURE: bool = False
    CREATE_SCHEMA_ON_STARTUP: bool = True

    SMTP_SERVER: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_FROM_EMAIL: str = "nao-responder@elo.saude"
    SMTP_PASSWORD: str = "nao-usado-no-mvp"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Settings singleton; permite que testes definam env vars antes do primeiro uso."""
    return Settings()
