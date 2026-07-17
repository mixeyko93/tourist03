"""Request/response contracts for placement submissions."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SubmissionDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locale: str = Field(default="ru", max_length=16)
    source: str = Field(default="web", max_length=32)


class SubmissionDraftResponseDTO(BaseModel):
    ok: bool = True
    public_number: str
    draft_token: str
    expires_at: Any
    content_version: int


class SubmissionDraftPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_version: Optional[int] = Field(default=None, ge=1)
    applicant_role: Optional[str] = Field(default=None, max_length=32)
    applicant_name: Optional[str] = Field(default=None, max_length=160)
    applicant_organization: Optional[str] = Field(default=None, max_length=240)
    applicant_position: Optional[str] = Field(default=None, max_length=160)
    applicant_phone: Optional[str] = Field(default=None, max_length=64)
    applicant_email: Optional[str] = Field(default=None, max_length=320)
    applicant_telegram: Optional[str] = Field(default=None, max_length=300)
    applicant_whatsapp: Optional[str] = Field(default=None, max_length=300)
    applicant_max: Optional[str] = Field(default=None, max_length=300)
    preferred_contact_type: Optional[str] = Field(default=None, max_length=32)
    place_name: Optional[str] = Field(default=None, max_length=240)
    place_type_id: Optional[int] = Field(default=None, ge=1)
    region: Optional[str] = Field(default=None, max_length=160)
    district: Optional[str] = Field(default=None, max_length=160)
    city: Optional[str] = Field(default=None, max_length=160)
    locality: Optional[str] = Field(default=None, max_length=160)
    address: Optional[str] = Field(default=None, max_length=500)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    short_description: Optional[str] = Field(default=None, max_length=320)
    description: Optional[str] = Field(default=None, max_length=10_000)
    seasonality: Optional[str] = Field(default=None, max_length=500)
    working_hours: Optional[dict[str, Any]] = None
    min_price: Optional[int] = Field(default=None, ge=0, le=1_000_000_000)
    public_contacts: Optional[list[dict[str, Any]]] = None
    amenities: Optional[list[Any]] = None
    rooms_payload: Optional[list[dict[str, Any]]] = None
    video_urls: Optional[list[str]] = None
    extra_data: Optional[dict[str, Any]] = None
    consents: Optional[dict[str, bool]] = None


class SubmissionDraftStateDTO(BaseModel):
    ok: bool = True
    public_number: str
    status: str
    content_version: int
    updated_at: Any


class SubmissionSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_token: str = Field(min_length=32, max_length=200)
    idempotency_key: str = Field(min_length=16, max_length=200)
    captcha_token: str = Field(min_length=1, max_length=4000)
    honeypot: str = Field(default="", max_length=200)


class SubmissionSubmitResponseDTO(BaseModel):
    ok: bool = True
    public_number: str
    tracking_token: str
    tracking_url: str
    status: str
    preferred_contact_type: Optional[str] = None


class SubmissionPublicStatusDTO(BaseModel):
    ok: bool = True
    public_number: str
    status: str
    status_label: str
    public_comment: Optional[str] = None
    updated_at: Any
    place_url: Optional[str] = None
    can_respond: bool = False


class SubmissionAdminPatchRequest(SubmissionDraftPatchRequest):
    content_version: int = Field(ge=1)
    assigned_admin_id: Optional[int] = Field(default=None, ge=1)
    status_public_comment: Optional[str] = Field(default=None, max_length=2000)


class SubmissionStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=2, max_length=40)
    content_version: int = Field(ge=1)
    public_comment: Optional[str] = Field(default=None, max_length=2000)
    internal_comment: Optional[str] = Field(default=None, max_length=5000)


class SubmissionNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=5000)
    is_visible_to_applicant: bool = False


class SubmissionObjectDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=16, max_length=200)


class SubmissionClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=2, max_length=5000)
