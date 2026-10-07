"""Typed reconciliation and review contracts for the website."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.contracts.http import Meta
from app.contracts.imports import UploadMetadata

ResultStatus = Literal[
    "EXACT_MATCH",
    "FUZZY_SUGGESTION",
    "AMOUNT_MISMATCH",
    "MISSING_IN_SNAPSHOT",
    "AMBIGUOUS",
    "EVIDENCE_INCOMPLETE",
    "REVIEW_ACCEPTED",
    "REJECTED",
]


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registration_id: UUID
    period: str
    purchase_import_id: UUID
    portal_import_id: UUID
    period_check = field_validator("period")(classmethod(UploadMetadata.period_check.__func__))


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: StrictInt = Field(gt=0)
    action: Literal["ACCEPT_CANDIDATE", "REJECT_MATCH"]
    candidate_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_check(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("A readable reason is required")
        return value

    @model_validator(mode="after")
    def candidate_check(self):
        if (self.action == "ACCEPT_CANDIDATE") != (self.candidate_id is not None):
            raise ValueError("Accept requires a candidate; reject requires no candidate")
        return self


class RunPolicy(BaseModel):
    version: str
    amount_tolerance: str
    fuzzy_threshold: str
    fuzzy_gap: str
    comparison: str
    max_pairs: int
    max_candidates: int
    max_rows: int
    max_result_bytes: int


class RunSource(BaseModel):
    id: UUID
    kind: Literal["PURCHASE", "PORTAL_2B"]
    sha256: str
    version: int
    adapter_version: str
    provenance: Literal["USER_PROVIDED", "SYNTHETIC_DEMO"]
    generated_at: datetime | None
    accepted_rows: int
    rejected_rows: int


class RunSummary(BaseModel):
    accepted_purchase_rows: int
    counts: dict[ResultStatus, int]
    tax_exposure_review: str
    credit_note_tax_review: str
    unknown_tax_exposure_rows: int
    unknown_credit_note_tax_rows: int
    currency: Literal["INR"]


class RunData(BaseModel):
    id: UUID
    run_id: UUID
    workspace_id: UUID
    registration_id: UUID
    period: str
    purchase_import_id: UUID
    portal_import_id: UUID
    revision: int
    version: int
    job_id: UUID
    state: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "SUPERSEDED"]
    policy_version: str
    policy: RunPolicy
    sources: list[RunSource]
    sources_current: bool
    provenance: Literal["USER_PROVIDED", "SYNTHETIC_DEMO"]
    summary: RunSummary | None
    superseded_by_run_id: UUID | None
    created_at: datetime
    updated_at: datetime


class RunResponse(BaseModel):
    data: RunData
    meta: Meta


class RunListData(BaseModel):
    runs: list[RunData]
    next_cursor: UUID | None


class RunListResponse(BaseModel):
    data: RunListData
    meta: Meta


class ResultData(BaseModel):
    id: UUID
    workspace_id: UUID
    run_id: UUID
    purchase_document_id: UUID
    source_row_number: int
    status: ResultStatus
    version: int
    canonical: dict[str, str | list[str] | None]
    assigned_portal_document_id: UUID | None
    provenance: Literal["USER_PROVIDED", "SYNTHETIC_DEMO"]
    reason_codes: list[str]


class CandidateData(BaseModel):
    id: UUID
    portal_document_id: UUID
    original_invoice_number: str
    invoice_date: str
    score: str
    rank: int
    hard_gates_passed: bool
    currently_available: bool
    amount_differences: dict[str, str | None]
    reason_codes: list[str]


class ReviewEvent(BaseModel):
    actor_id: UUID
    action: Literal["ACCEPT_CANDIDATE", "REJECT_MATCH"]
    reason: str
    candidate_id: UUID | None
    result_version: int
    created_at: datetime


class ResultDetail(ResultData):
    candidates: list[CandidateData]
    review_timeline: list[ReviewEvent]


class ResultResponse(BaseModel):
    data: ResultDetail
    meta: Meta


class ResultListData(BaseModel):
    results: list[ResultData]
    next_cursor: int | None


class ResultListResponse(BaseModel):
    data: ResultListData
    meta: Meta
