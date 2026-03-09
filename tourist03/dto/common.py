from typing import Optional

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
