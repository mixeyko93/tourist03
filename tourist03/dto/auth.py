from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from tourist03.dto.common import OkResponseDTO


class AuthUserDTO(BaseModel):
    id: int
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    phone_verified: bool
    email_verified: bool
    created_at: Optional[datetime] = None


class AuthTokenUserResponseDTO(OkResponseDTO):
    token: Optional[str] = None
    user: AuthUserDTO


class AuthUserResponseDTO(OkResponseDTO):
    user: AuthUserDTO


class AuthProfileUpdateResponseDTO(AuthUserResponseDTO):
    need_phone_verify: bool
    need_email_verify: bool


class AuthUsersListItemDTO(BaseModel):
    id: int
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    email_verified: bool
    phone_verified: bool
    created_at: Optional[datetime] = None
