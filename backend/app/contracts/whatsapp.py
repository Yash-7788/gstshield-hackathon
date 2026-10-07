"""Local authenticated channel controls; bearer download tokens never enter DTO history."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from app.contracts.http import Meta
from app.contracts.imports import UploadMetadata


class LinkContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registration_id: UUID
    period: str
    period_check = field_validator("period")(classmethod(UploadMetadata.period_check.__func__))


class LinkUpdate(LinkContext):
    expected_version: StrictInt = Field(gt=0)
    consent_alerts: StrictBool = False


class LinkRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: StrictInt = Field(gt=0)


class LinkCodeData(BaseModel):
    code: str
    expires_at: int
    registration_id: UUID
    period: str


class LinkCodeResponse(BaseModel):
    data: LinkCodeData
    meta: Meta


class ChannelLink(BaseModel):
    id: UUID
    workspace_id: UUID
    registration_id: UUID
    period: str
    masked_phone: str
    version: int
    consent_alerts: bool
    active: bool


class DeliveryStateEvent(BaseModel):
    state: str
    created_at: int


class DeliveryData(BaseModel):
    id: UUID
    state: Literal[
        "QUEUED", "ATTEMPTED", "ACKNOWLEDGED", "DELIVERED", "READ", "FAILED", "UNKNOWN", "CANCELLED"
    ]
    error_code: str | None
    created_at: int
    updated_at: int
    action_id: UUID | None = None
    draft_id: UUID | None = None
    history: list[DeliveryStateEvent] = Field(default_factory=list)


class ChannelData(BaseModel):
    enabled: bool
    sending_enabled: bool
    link: ChannelLink | None
    deliveries: list[DeliveryData]
    remaining_send_budget: int
    physical_phone_verified: Literal[False] = False


class ChannelResponse(BaseModel):
    data: ChannelData
    meta: Meta


class SupplierConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: UUID
    draft_id: UUID
    expected_version: StrictInt = Field(gt=0)


class SupplierSendRequest(SupplierConsentRequest):
    recipient_id: UUID


class ConsentCodeData(BaseModel):
    code: str
    expires_at: int
    masked_phone: str
    draft_id: UUID


class ConsentCodeResponse(BaseModel):
    data: ConsentCodeData
    meta: Meta


class SupplierRecipientData(BaseModel):
    id: UUID
    action_id: UUID
    draft_id: UUID
    masked_phone: str
    verified_at: int


class SupplierRecipientsResponse(BaseModel):
    data: list[SupplierRecipientData]
    meta: Meta


class SupplierSendResponse(BaseModel):
    data: DeliveryData
    meta: Meta
