"""Invoice intake and gate contracts: unknown evidence stays explicit."""

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from app.contracts.http import Meta
from app.contracts.runs import ResultData, RunData
from app.contracts.workflows import CaseData, ProposalData

Money = Annotated[str, Field(pattern=r"^[0-9]{1,14}(\.[0-9]{1,2})?$", max_length=17)]
Quantity = Annotated[str, Field(pattern=r"^[0-9]{1,9}(\.[0-9]{1,4})?$", max_length=14)]
Period = Annotated[str, Field(pattern=r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])$")]
BoundedStr = Annotated[str, Field(max_length=500)]
QuoteKey = Annotated[str, Field(max_length=100)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LineItem(Input):
    description: str = Field(min_length=1, max_length=200)
    sku: str = Field(default="", max_length=64)
    unit: str = Field(default="", max_length=24)
    quantity: Quantity
    taxable_value: Money

    @model_validator(mode="after")
    def positive_quantity(self):
        from decimal import Decimal

        if Decimal(self.quantity) <= 0 or not self.description.strip():
            raise ValueError("Provide an item name and positive quantity")
        return self


class ExtractedLineItem(Input):
    description: str | None = Field(default=None, max_length=200)
    sku: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=24)
    quantity: str | None = Field(default=None, max_length=32)
    taxable_value: str | None = Field(default=None, max_length=32)


class InvoiceFields(Input):
    supplier_gstin: str = Field(pattern=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
    invoice_number: str = Field(min_length=1, max_length=128)
    invoice_date: date
    supplier_name: str = Field(default="", max_length=200)
    taxable_value: Money
    igst: Money | None = None
    cgst: Money | None = None
    sgst: Money | None = None
    cess: Money | None = None
    other_charges: Money = "0.00"
    round_off: str = Field(default="0.00", pattern=r"^[+-]?[0-9]{1,14}(\.[0-9]{1,2})?$")
    gross_total: Money
    irn: str = Field(default="", max_length=128)
    quantity: Quantity | None = None
    items: list[LineItem] = Field(default_factory=list, max_length=100)
    supplier_bank_account: str | None = Field(default=None, pattern=r"^[A-Za-z0-9]{6,34}$")
    irn_required: StrictBool | None = None
    payment_dispute: StrictBool | None = None

    @model_validator(mode="after")
    def item_totals(self):
        from decimal import Decimal

        if self.items and sum(Decimal(item.taxable_value) for item in self.items) != Decimal(
            self.taxable_value
        ):
            raise ValueError("Item values must add up to the invoice goods value")
        return self


class ExtractedInvoice(Input):
    supplier_gstin: str | None = Field(default=None, max_length=32)
    invoice_number: str | None = Field(default=None, max_length=128)
    invoice_date: str | None = Field(default=None, max_length=32)
    supplier_name: str | None = Field(default=None, max_length=200)
    taxable_value: str | None = Field(default=None, max_length=32)
    igst: str | None = Field(default=None, max_length=32)
    cgst: str | None = Field(default=None, max_length=32)
    sgst: str | None = Field(default=None, max_length=32)
    cess: str | None = Field(default=None, max_length=32)
    other_charges: str | None = Field(default=None, max_length=32)
    round_off: str | None = Field(default=None, max_length=32)
    gross_total: str | None = Field(default=None, max_length=32)
    irn: str | None = Field(default=None, max_length=128)
    quantity: str | None = Field(default=None, max_length=32)
    invoice_count: StrictInt | None = Field(default=None, ge=1, le=20)
    items: list[ExtractedLineItem] = Field(default_factory=list, max_length=100)
    supplier_bank_account: str | None = Field(default=None, max_length=64)
    uncertainties: list[BoundedStr] = Field(default_factory=list, max_length=20)
    evidence_quotes: dict[QuoteKey, BoundedStr] = Field(default_factory=dict, max_length=20)


class PassportCreate(Input):
    registration_id: UUID
    period: Period
    purchase_import_id: UUID
    row_number: int = Field(ge=1, le=2000)


class PassportConfirm(Input):
    expected_version: StrictInt = Field(ge=1)
    fields: InvoiceFields


class CommercialLineItem(LineItem):
    taxable_value: Money | None = None


class CommercialEvidence(Input):
    document_proposal_id: UUID | None = None
    expected_version: StrictInt = Field(ge=1)
    kind: Literal["PO", "RECEIPT"]
    reference: str = Field(min_length=1, max_length=128)
    taxable_value: Money | None = None
    quantity: Quantity | None = None
    observed_on: date
    note: str = Field(default="", max_length=1000)
    items: list[CommercialLineItem] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def item_totals(self):
        from decimal import Decimal

        if self.kind == "PO" and (
            self.taxable_value is None or any(i.taxable_value is None for i in self.items)
        ):
            raise ValueError("Purchase order goods values are required")
        if (
            self.taxable_value is not None
            and self.items
            and all(i.taxable_value is not None for i in self.items)
            and sum(Decimal(item.taxable_value) for item in self.items)
            != Decimal(self.taxable_value)
        ):
            raise ValueError("Item values must add up to the recorded goods value")
        return self


class ClockEvidence(Input):
    expected_version: StrictInt = Field(ge=1)
    msme_covered: StrictBool | None = None
    accepted_on: date | None = None
    agreed_days: int | None = Field(default=None, ge=1, le=45)
    claimed_on: date | None = None
    supplier_3b_due_on: date | None = None
    amount_paid: Money | None = None
    payment_observed_on: date | None = None

    @model_validator(mode="after")
    def observed_payment_date(self):
        if self.payment_observed_on and self.payment_observed_on > date.today():
            raise ValueError("Payment observation cannot be in the future")
        return self

    note: str = Field(default="", max_length=1000)


class PortalSelection(Input):
    expected_version: StrictInt = Field(ge=1)
    import_id: UUID


class RemoveInvoice(Input):
    expected_version: StrictInt = Field(ge=1)
    target: Literal["ORIGINAL_FILE", "INVOICE"]


class GateApproval(Input):
    expected_version: StrictInt = Field(ge=1)
    source_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["PAY", "PARTIAL_CONTROLLED_PAYMENT", "HOLD", "ESCALATE"]
    amount: Money
    reason: str = Field(min_length=10, max_length=1000)


class ResolutionCommand(Input):
    expected_version: StrictInt = Field(ge=1)
    action: Literal["DRAFT", "ACKNOWLEDGED", "PROMISED", "RESOLVED", "ESCALATED"]
    promised_on: date | None = None
    note: str = Field(default="", max_length=1000)


class Scenario(Input):
    expected_version: StrictInt = Field(ge=1)
    cash_available: Money
    proposed_payment: Money


class CopilotQuery(Input):
    registration_id: UUID
    period: Period
    question: str = Field(min_length=3, max_length=1000)
    use_ai: StrictBool = False


class PassportData(BaseModel):
    id: UUID
    workspace_id: UUID
    registration_id: UUID
    period: str
    version: int
    confirmed: bool
    removed: bool = False
    original_available: bool = False
    filename: str
    fields: dict[str, Any]
    extraction: dict[str, Any]
    purchase_import_id: UUID | None
    source_signature: str
    findings: dict[str, Any]
    gate: dict[str, Any]
    clocks: dict[str, Any]
    approval: dict[str, Any] | None
    resolution: dict[str, Any]
    supplier_channel: dict[str, Any] = Field(default_factory=dict)
    demo_bank: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]]


class InvoiceWorkflowData(BaseModel):
    automation: dict[str, Any] = Field(default_factory=dict)
    passport_id: UUID
    registration_id: UUID
    period: str
    invoice_number: str
    confirmed: bool
    purchase_import_id: UUID | None
    portal_import_id: UUID | None
    purchase_document_id: UUID | None
    run: RunData | None
    result: ResultData | None
    cases: list[CaseData]
    proposals: list[ProposalData]


class InvoiceWorkflowResponse(BaseModel):
    data: InvoiceWorkflowData
    meta: Meta


class PassportResponse(BaseModel):
    data: PassportData
    meta: Meta


class PassportListData(BaseModel):
    passports: list[PassportData]
    metrics: dict[str, Any]
    vendors: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    provider: dict[str, Any]


class PassportListResponse(BaseModel):
    data: PassportListData
    meta: Meta


class IntelligenceResponse(BaseModel):
    data: dict[str, Any]
    meta: Meta


class DocumentMetadata(Input):
    registration_id: UUID
    period: Period
    consent: StrictBool


class FetchSimulation(Input):
    expected_version: StrictInt = Field(ge=1)
    status: Literal["MISSING", "MATCHED"]


class WatchMode(Input):
    expected_version: StrictInt = Field(ge=1)
    enabled: StrictBool


class NoticeAssistance(Input):
    case_id: UUID | None = None
    notice_text: str = Field(min_length=20, max_length=8000)
    use_ai: StrictBool = False


class InvoiceDetails(Input):
    expected_version: StrictInt = Field(ge=1)
    items: list[LineItem] = Field(max_length=100)
    supplier_bank_account: str | None = Field(default=None, pattern=r"^[A-Za-z0-9]{6,34}$")
    irn_required: StrictBool | None = None
    payment_dispute: StrictBool | None = None


class IMSReview(Input):
    expected_version: StrictInt = Field(ge=1)
    source_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    action: Literal["ACCEPT", "REJECT", "PENDING", "HUMAN_REVIEW"]
    reason: str = Field(min_length=10, max_length=1000)
    confirm_rejection: StrictBool = False


class SupplierInvite(Input):
    expected_version: StrictInt = Field(ge=1)
    phone: str = Field(pattern=r"^\+?[1-9][0-9]{6,14}$")


class SupplierSend(Input):
    expected_version: StrictInt = Field(ge=1)


class DemoBankPayment(Input):
    expected_version: StrictInt = Field(ge=1)
    source_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    amount: Money


class ExtractedCommercial(Input):
    document_kind: Literal["PO", "RECEIPT", "OTHER"]
    reference: str | None = Field(default=None, max_length=128)
    observed_on: str | None = Field(default=None, max_length=32)
    taxable_value: str | None = Field(default=None, max_length=32)
    quantity: str | None = Field(default=None, max_length=32)
    items: list[ExtractedLineItem] = Field(default_factory=list, max_length=100)
    uncertainties: list[BoundedStr] = Field(default_factory=list, max_length=20)
