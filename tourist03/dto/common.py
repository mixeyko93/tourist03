from typing import Any, List, Optional

from pydantic import BaseModel


class OkResponseDTO(BaseModel):
    ok: bool


class StatusResponseDTO(BaseModel):
    status: str


class UrlResponseDTO(BaseModel):
    url: str


class IdResponseDTO(OkResponseDTO):
    id: int


class PaymentLinkResponseDTO(OkResponseDTO):
    payment_url: Optional[str] = None


class ErrorResponseDTO(BaseModel):
    detail: str


class ValidationErrorItemDTO(BaseModel):
    loc: List[Any]
    msg: str
    type: str


class ValidationErrorResponseDTO(BaseModel):
    detail: List[ValidationErrorItemDTO]
