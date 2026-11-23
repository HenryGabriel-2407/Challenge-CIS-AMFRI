"""Erros de domínio mapeados para respostas HTTP pela camada de interface."""


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(DomainError):
    def __init__(self, message: str = "Recurso não encontrado."):
        super().__init__(message, 404)


class ConflictError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, 409)


class ForbiddenError(DomainError):
    def __init__(self, message: str = "Você não tem permissão para esta operação."):
        super().__init__(message, 403)
