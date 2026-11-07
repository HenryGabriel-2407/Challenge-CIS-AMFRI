from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    BASE_URL: str = "http://localhost:8000"

    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str
    SMTP_SERVER: str
    SMTP_PORT: int