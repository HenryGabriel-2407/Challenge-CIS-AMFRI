from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import decode, encode
from jwt.exceptions import ExpiredSignatureError, PyJWTError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from domotica_python.database import get_session
from domotica_python.models import User
from domotica_python.settings import Settings

pwd_context = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

settings = Settings()

T_Session = Annotated[Session, Depends(get_session)]


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password_hash(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(tz=ZoneInfo("UTC")) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    encoded_jwt = encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def get_current_user(
    session: T_Session,
    token: str = Depends(oauth2_scheme),
) -> User:
    credentials_exception = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except (ExpiredSignatureError, PyJWTError):
        raise credentials_exception

    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        raise credentials_exception

    return user