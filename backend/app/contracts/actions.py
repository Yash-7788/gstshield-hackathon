"""Private business-action commands, using the established exact-money/session contract."""

import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictBool, field_validator, model_validator

from app.contracts.http import Meta
from app.contracts.workflows import Money, ObservedDate, Reason, StrictModel

ActionState = Literal["OPEN", "AWAITING_SUPPLIER", "EVIDENCE_REQUIRED", "REVIEW_REQUIRED", "CLOSED"]


class ActionUpdate(Reason):
    state: ActionState
    review_on: ObservedDate | None = None
    assigned_to: UUID | None = None


class Followup(Reason):
    kind: Literal["DRAFT", "ATTEMPT_RECORDED"] = "DRAFT"
    contact: str = Field(min_length=3, max_length=200)
    request: str = Field(min_length=1, max_length=1000)
    draft_id: UUID | None = None
    observed_on: ObservedDate | None = None

    @field_validator("contact", "request")
    @classmethod
    def text(cls, value):
        return Reason.readable(value)

    @field_validator("contact")
    @classmethod
    def address(cls, value):
        if not re.fullmatch(r"(?:\+[1-9][0-9]{7,14}|[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+)", value):
            raise ValueError("Provide an explicit international phone number or email")
        return value

    @model_validator(mode="after")
    def attempt(self):
        if self.kind == "ATTEMPT_RECORDED" and (not self.draft_id or not self.observed_on):
            raise ValueError("A recorded attempt requires its draft and observed date")
        if self.kind == "DRAFT" and (self.draft_id or self.observed_on):
            raise ValueError("A draft does not record a send")
        return self


class ActionOutcome(Reason):
    kind: Literal["REVIEW_DECISION", "FILING_OBSERVATION", "NOTICE_SUBMISSION_OBSERVATION"]
    decision: Literal["REVIEW_ACCEPTED", "EVIDENCE_REQUIRED", "REJECTED"] | None = None
    amount: Money | None = None
    reference: str | None = Field(default=None, min_length=1, max_length=200)
    observed_on: ObservedDate | None = None
    evidence_event_ids: list[UUID] = Field(default_factory=list, max_length=20)
    provenance: Literal["USER_PROVIDED", "SYNTHETIC_DEMO"] = "USER_PROVIDED"

    @field_validator("reference")
    @classmethod
    def reference_text(cls, value):
        return Reason.readable(value) if value is not None else None

    @model_validator(mode="after")
    def observation(self):
        if len(set(self.evidence_event_ids)) != len(self.evidence_event_ids):
            raise ValueError("Duplicate evidence references")
        if self.kind == "REVIEW_DECISION":
            if self.decision is None or self.reference is not None or self.observed_on is not None:
                raise ValueError("Review requires a decision rather than a filing assertion")
        elif (
            self.decision is not None
            or not self.reference
            or not self.observed_on
            or not self.evidence_event_ids
        ):
            raise ValueError("Actual observation requires a reference, date and case evidence")
        if self.kind == "FILING_OBSERVATION" and self.amount is None:
            raise ValueError("A filed reclaim observation requires an amount")
        if self.observed_on is not None and self.observed_on > datetime.now(UTC).date():
            raise ValueError("Observation cannot be future-dated")
        return self


class ActionData(StrictModel):
    id: UUID
    workspace_id: UUID
    registration_id: UUID
    period: str
    document_id: UUID
    kind: str
    case_id: UUID | None
    run_id: UUID
    result_id: UUID
    source: dict
    state: ActionState
    version: int
    assigned_to: UUID | None
    due_at: int | None
    reminded_at: int | None
    outcome: dict | None
    sources_current: StrictBool
    created_at: int
    updated_at: int
    timeline: list[dict]


class AutomationData(StrictModel):
    checked_at: int | None
    error_code: str | None
    pending_sources: int
    interval_seconds: int
    channel_delivery: Literal["DISABLED", "PAUSED", "ENABLED"] = "DISABLED"


class ActionListData(StrictModel):
    actions: list[ActionData]
    next_cursor: UUID | None
    automation: AutomationData


class ActionResponse(StrictModel):
    data: ActionData
    meta: Meta


class ActionListResponse(StrictModel):
    data: ActionListData
    meta: Meta


class WorksheetResponse(StrictModel):
    data: dict
    meta: Meta
