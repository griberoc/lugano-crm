from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, resource: str, id: str | None = None):
        detail = f"{resource} não encontrado"
        if id:
            detail = f"{resource} '{id}' não encontrado"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class UnprocessableError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Acesso negado"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class InsufficientPointsError(UnprocessableError):
    def __init__(self, available: int, required: int):
        super().__init__(
            detail=f"Pontos insuficientes. Disponível: {available}, necessário: {required}"
        )


class PromotionExpiredError(UnprocessableError):
    def __init__(self):
        super().__init__(detail="Promoção expirada ou inativa")


class PromotionLimitReachedError(UnprocessableError):
    def __init__(self):
        super().__init__(detail="Limite de usos desta promoção foi atingido")
