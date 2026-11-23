"""Criptografia em repouso para dados pessoais e sensíveis (LGPD)."""

from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, Text
from sqlalchemy.types import TypeDecorator

from challenge.settings import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().ENCRYPTION_KEY.encode())


def encrypt_value(value: str) -> str:
    """Cifra um valor; seguro para CPF, telefone, resumo clínico e instruções."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decifra um valor. InvalidToken indica chave trocada ou dado adulterado."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Não foi possível decifrar o dado protegido.") from exc


class _Encrypted(TypeDecorator):
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return encrypt_value(str(value))

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return decrypt_value(value)


class EncryptedString(_Encrypted):
    impl = String
    python_type = str


class EncryptedText(_Encrypted):
    impl = Text
    python_type = str


def mask_cpf(cpf: str | None) -> str | None:
    if not cpf:
        return None
    digits = "".join(filter(str.isdigit, cpf))
    if len(digits) != 11:
        return "***.***.***-**"
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(filter(str.isdigit, phone))
    if len(digits) < 4:
        return "****"
    return f"*****{digits[-4:]}"
