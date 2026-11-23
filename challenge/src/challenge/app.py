"""Fábrica da aplicação FastAPI do Elo Saúde."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from challenge.database import SessionLocal, get_engine
from challenge.exceptions import DomainError
from challenge.models import Base
from challenge.routers import auth, discharges, web
from challenge.seed import seed_demo_data
from challenge.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cria o schema e semeia dados fictícios no MVP local.

    Em produção, use `alembic upgrade head` e mantenha CREATE_SCHEMA_ON_STARTUP=false.
    """
    settings = get_settings()
    if settings.CREATE_SCHEMA_ON_STARTUP:
        Base.metadata.create_all(bind=get_engine())
        with SessionLocal() as session:
            seed_demo_data(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Elo Saúde — Contrarreferência",
        description="MVP de transição do cuidado entre hospital/UPA e Atenção Primária.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.get("/health", tags=["saúde"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "elo-saude"}

    app.include_router(auth.router)
    app.include_router(discharges.router)
    app.include_router(web.router)
    return app


app = create_app()
