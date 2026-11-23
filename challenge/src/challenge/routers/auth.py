"""Autenticação da API (OAuth2 password flow → JWT)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from challenge.schemas import Token
from challenge.security import TSession, authenticate_user, create_access_token

router = APIRouter(prefix="/api/auth", tags=["autenticação"])


@router.post("/login", response_model=Token, summary="Realiza login e retorna um JWT")
def login(
    session: TSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    user = authenticate_user(session, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user.email, "role": user.role.value})
    return Token(access_token=token, token_type="bearer", role=user.role, user_name=user.name)
