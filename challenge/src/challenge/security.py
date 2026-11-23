"""Autenticação (Argon2id + JWT) e controle de acesso baseado em perfis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import decode, encode
from jwt.exceptions import PyJWTError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from challenge.database import get_session
from challenge.enums import UserRole
from challenge.exceptions import ForbiddenError
from challenge.models import User
from challenge.settings import get_settings

pwd_context = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

TSession = Annotated[Session, Depends(get_session)]


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    now = datetime.now(tz=timezone.utc)
    payload.update(
        {
            "exp": now + timedelta(minutes=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": now,
        }
    )
    settings = get_settings()
    return encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas ou expiradas.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    user.last_login = datetime.now(tz=timezone.utc)
    session.add(user)
    session.commit()
    return user


def get_current_user(session: TSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    payload = decode_access_token(token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem identificação.")
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo ou inexistente.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """ADMIN sempre possui acesso; demais perfis precisam estar na lista."""

    def checker(user: CurrentUser) -> User:
        if user.role is not UserRole.ADMIN and user.role not in roles:
            raise ForbiddenError("Seu perfil não pode executar esta operação.")
        return user

    return checker
