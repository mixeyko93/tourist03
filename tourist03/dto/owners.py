from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class OwnerLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class OwnerForgotPasswordRequest(BaseModel):
    email: EmailStr


class OwnerResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=12, max_length=256)


class OwnerProfilePatchRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=160)
    company: str | None = Field(default=None, max_length=240)
    phone: str | None = Field(default=None, max_length=64)
    telegram: str | None = Field(default=None, max_length=300)
    whatsapp: str | None = Field(default=None, max_length=300)
    max: str | None = Field(default=None, max_length=300)
    preferred_contact_type: Literal["email", "phone", "telegram", "whatsapp", "max"] | None = None


class OwnerPasswordPatchRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class OwnerChangePatchRequest(BaseModel):
    content_version: int = Field(ge=1)
    proposed_payload: dict[str, Any] = Field(default_factory=dict)


class OwnerChangeSubmitRequest(OwnerChangePatchRequest):
    pass


class OwnerEntityCreateRequest(BaseModel):
    entity_kind: Literal[
        "accommodation",
        "service",
        "activity",
        "food",
        "transport",
        "rental",
        "guide",
        "event",
        "sight",
        "excursion",
    ]
    subtype: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=240)
    short_description: str | None = Field(default=None, max_length=2000)
    region: str | None = Field(default=None, max_length=160)
    district: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=500)
    lat: float | None = None
    lng: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    min_price: int | None = Field(default=None, ge=0, le=1_000_000_000)
    price_mode: Literal["from", "fixed", "request", "free", "none"] = "none"
    currency: str = Field(default="RUB", min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")


class OwnerChangeDecisionRequest(BaseModel):
    status: Literal["in_review", "needs_changes", "approved", "rejected", "archived"]
    comment: str | None = Field(default=None, max_length=4000)


class OwnerChangeApplyRequest(BaseModel):
    idempotency_key: str = Field(min_length=12, max_length=200)


class OwnerAccountCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=160)
    company: str | None = Field(default=None, max_length=240)


class OwnerAccountAdminPatchRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=160)
    company: str | None = Field(default=None, max_length=240)
    is_active: bool | None = None
    account_status: Literal["active", "suspended", "invited", "archived"] | None = None


class OwnerCampLinkRequest(BaseModel):
    camp_id: int = Field(ge=1)
    role_key: Literal["primary_owner", "owner", "representative", "manager", "editor", "viewer"] = "owner"
    is_primary: bool = False
