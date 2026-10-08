"""Strict workflow inputs: observed facts, not legal or payment conclusions."""

import re
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, field_validator

from app.contracts.http import Meta
from app.contracts.imports import UploadMetadata
from app.domain.imports import money_paise, money_string


def amount(value):
    return money_string(money_paise(value, "gross_total"))


def observed_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Use an ISO date")
    return date.fromisoformat(value)


ObservedDate = Annotated[date, BeforeValidator(observed_date)]
Money = Annotated[str, BeforeValidator(amount)]
Period = Annotated[str, BeforeValidator(UploadMetadata.period_check)]
CaseKind = Literal["MSME_REVIEW", "RULE37_REVIEW", "RULE37A_REVIEW", "IRN_REVIEW", "NOTICE_REVIEW"]
CaseState = Literal["OPEN", "EVIDENCE_REQUIRED", "REVIEW_READY", "CLOSED"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Facts(StrictModel):
    observation_refs: list[UUID] = Field(default_factory=list, max_length=20)


class PaymentFacts(Facts):
    amount_paid: Money | None = None
    payment_observed_on: ObservedDate | None = None


class MSMEFacts(PaymentFacts):
    supplier_classification: Literal["MICRO", "SMALL", "MEDIUM", "OTHER", "UNKNOWN"] = "UNKNOWN"
    acceptance_date: ObservedDate | None = None
    agreed_credit_days: StrictInt | None = Field(default=None, ge=0, le=3650)
    dispute_note: str | None = Field(default=None, max_length=1000)


class Rule37Facts(PaymentFacts):
    original_claim_period: Period | None = None
    original_claim_amount: Money | None = None
    payment_due_date: ObservedDate | None = None


class Rule37AFacts(Facts):
    original_claim_period: Period | None = None
    original_claim_amount: Money | None = None
    reversal_period: Period | None = None
    reversal_amount: Money | None = None
    supplier_return_period: Period | None = None
    supplier_return_status: Literal["FILED", "NOT_FILED", "UNKNOWN"] = "UNKNOWN"
    filing_observed_on: ObservedDate | None = None


class IRNFacts(Facts):
    irn: str | None = Field(default=None, max_length=128)
    applicability: Literal["APPLIES", "DOES_NOT_APPLY", "UNKNOWN"] = "UNKNOWN"


class NoticeFacts(Facts):
    notice_reference: str | None = Field(default=None, max_length=200)
    notice_date: ObservedDate | None = None
    response_due_date: ObservedDate | None = None


FACT_MODELS = {
    "MSME_REVIEW": MSMEFacts,
    "RULE37_REVIEW": Rule37Facts,
    "RULE37A_REVIEW": Rule37AFacts,
    "IRN_REVIEW": IRNFacts,
    "NOTICE_REVIEW": NoticeFacts,
}


class CaseCreate(StrictModel):
    registration_id: UUID
    result_id: UUID
    purchase_document_id: UUID
    kind: CaseKind
    amount: Money
    currency: Literal["INR"] = "INR"
    facts: dict = Field(default_factory=dict)


class Reason(StrictModel):
    expected_version: StrictInt = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def readable(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Readable text is required")
        return value


class CaseEvidence(Reason):
    event_kind: Literal[
        "NOTE",
        "DOCUMENT",
        "PAYMENT_OBSERVATION",
        "FILING_OBSERVATION",
        "ACCEPTANCE_OBSERVATION",
        "IRN_OBSERVATION",
    ]
    import_id: UUID | None = None
    facts_patch: dict = Field(default_factory=dict)


class CaseTransition(Reason):
    state: CaseState


class BalanceObservation(StrictModel):
    document_id: UUID
    evidence_case_id: UUID
    expected_case_version: StrictInt = Field(gt=0)


class Allocation(StrictModel):
    document_id: UUID
    amount: Money
    purpose: Literal["SUPPLIER_PROPOSED", "INTERNAL_RESERVE_ILLUSTRATIVE"]


class ProposalCreate(StrictModel):
    run_id: UUID
    expected_run_version: StrictInt = Field(gt=0)
    expected_result_versions: dict[UUID, StrictInt] = Field(min_length=1, max_length=100)
    balance_observations: list[BalanceObservation] = Field(min_length=1, max_length=100)
    allocations: list[Allocation] = Field(min_length=1, max_length=200)


class ArtifactCreate(StrictModel):
    kind: Literal["RECONCILIATION_PDF", "EVIDENCE_PDF", "PROPOSAL_CSV", "ROW_ERRORS_CSV"]
    source_id: UUID
    expected_version: StrictInt = Field(gt=0)
    selected_result_ids: list[UUID] = Field(default_factory=list, max_length=200)


class CleanupCreate(StrictModel):
    expired_only: Literal[True] = True


# Public responses exclude bytes, private paths and job leases.
class CaseData(StrictModel):
    id: UUID
    workspace_id: UUID
    registration_id: UUID
    result_id: UUID
    purchase_document_id: UUID
    kind: CaseKind
    amount: Money
    currency: Literal["INR"]
    facts: dict
    provenance: Literal["USER_PROVIDED", "SYNTHETIC_DEMO"]
    state: CaseState
    version: int
    created_at: int
    updated_at: int
    missing_facts: list[str]
    sources_current: bool
    stored_state: CaseState
    irn_observation: Literal["NOT_PROVIDED", "FORMAT_ONLY", "FORMAT_INVALID"]
    timeline: list[dict]


class CaseResponse(StrictModel):
    data: CaseData
    meta: Meta


class CaseListData(StrictModel):
    cases: list[CaseData]
    next_cursor: UUID | None


class CaseListResponse(StrictModel):
    data: CaseListData
    meta: Meta


class ProposalData(StrictModel):
    id: UUID
    workspace_id: UUID
    run_id: UUID
    snapshot: dict
    snapshot_sha256: str
    state: Literal["DRAFT", "APPROVED", "EXPORTED", "STALE"]
    stored_state: Literal["DRAFT", "APPROVED", "EXPORTED"]
    version: int
    created_at: int
    updated_at: int
    sources_current: bool
    timeline: list[dict]


class ProposalResponse(StrictModel):
    data: ProposalData
    meta: Meta


class ProposalListData(StrictModel):
    proposals: list[ProposalData]
    next_cursor: UUID | None


class ProposalListResponse(StrictModel):
    data: ProposalListData
    meta: Meta


class ArtifactData(StrictModel):
    id: UUID
    workspace_id: UUID
    kind: Literal["RECONCILIATION_PDF", "EVIDENCE_PDF", "PROPOSAL_CSV", "ROW_ERRORS_CSV"]
    source_id: UUID
    source_version: int
    snapshot_sha256: str
    filename: str
    mime_type: str
    state: Literal["PENDING", "READY", "FAILED", "EXPIRED"]
    sha256: str | None
    size_bytes: int | None
    error_code: str | None
    expires_at: int
    created_at: int
    updated_at: int
    manifest: dict
    provenance: Literal["USER_PROVIDED", "SYNTHETIC_DEMO"]
    sources_current: bool
    job_id: UUID


class ArtifactResponse(StrictModel):
    data: ArtifactData
    meta: Meta


class CleanupData(StrictModel):
    expired_artifacts: int
    scope: Literal["EXPIRED_ARTIFACT_CONTENT_ONLY"]


class CleanupResponse(StrictModel):
    data: CleanupData
    meta: Meta


class ArtifactListData(StrictModel):
    artifacts: list[ArtifactData]
    next_cursor: UUID | None


class ArtifactListResponse(StrictModel):
    data: ArtifactListData
    meta: Meta
