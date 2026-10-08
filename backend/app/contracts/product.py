"""Validated product inputs; role labels never grant membership."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, SecretStr, StrictBool, StrictInt, field_validator, model_validator

from app.contracts.passports import Input, Money, Period
from app.services.access import name_value, password_value, username_value

StaffRole = Literal[
    "OWNER", "CFO", "CMO", "CMA", "CA", "CEO", "COO", "CTO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"
]
Note = Annotated[str, Field(min_length=3, max_length=2000)]


class Employee(Input):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    monthly_salary: Money | None = None


class Profile(Input):
    business_name: str = Field(min_length=1, max_length=100)
    business_type: Literal["MANUFACTURING", "TRADING", "SERVICES", "OTHER", "UNKNOWN"] = "UNKNOWN"
    workforce_count: StrictInt | None = Field(default=None, ge=0, le=10000)
    employees: list[Employee] = Field(default_factory=list, max_length=500)
    monthly_revenue: Money | None = None
    monthly_profit: str | None = Field(default=None, pattern=r"^-?[0-9]{1,14}(\.[0-9]{1,2})?$")
    monthly_operating_cost: Money | None = None
    tax_paid: dict[Literal["GST", "INCOME_TAX", "PAYROLL", "OTHER"], Money | None] = Field(
        default_factory=dict
    )
    msme_status: Literal["MICRO", "SMALL", "MEDIUM", "NOT_MSME", "UNKNOWN"] = "UNKNOWN"
    annual_turnover: Money | None = None
    loan_needed: Money | None = None
    prior_tarun_repaid: StrictBool | None = None
    marketing_spend: Money | None = None
    attributed_sales: Money | None = None
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def counts(self):
        if self.workforce_count is not None and len(self.employees) > self.workforce_count:
            raise ValueError("Employee list exceeds reported workforce count")
        name_value(self.business_name)
        return self


class SaveBusiness(Input):
    registration_id: UUID
    period: Period
    expected_version: StrictInt = Field(ge=0)
    profile: Profile


class CreateMember(Input):
    username: str
    password: SecretStr
    display_name: str
    roles: list[StaffRole] = Field(min_length=1, max_length=1)

    @field_validator("username")
    @classmethod
    def user_check(cls, value):
        return username_value(value)

    @field_validator("password")
    @classmethod
    def password_check(cls, value):
        password_value(value.get_secret_value())
        return value

    @field_validator("display_name")
    @classmethod
    def name_check(cls, value):
        return name_value(value)

    @field_validator("roles")
    @classmethod
    def roles_check(cls, value):
        if len(value) != 1 or "OWNER" in value:
            raise ValueError(
                "Assign exactly one preset team role; owner membership is operator-managed"
            )
        return value


class CreateTeam(Input):
    members: list[CreateMember] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def distinct_accounts(self):
        names = [member.username for member in self.members]
        if len(set(names)) != len(names):
            raise ValueError("Each person needs a different username")
        return self


class MemberPassword(Input):
    expected_version: StrictInt = Field(ge=1)
    password: SecretStr

    @field_validator("password")
    @classmethod
    def password_check(cls, value):
        password_value(value.get_secret_value())
        return value


class UpdateMember(Input):
    expected_version: StrictInt = Field(ge=1)
    roles: list[StaffRole] = Field(min_length=1, max_length=1)
    active: StrictBool

    @field_validator("roles")
    @classmethod
    def roles_check(cls, value):
        return CreateMember.roles_check(value)


class Contribution(Input):
    registration_id: UUID
    period: Period
    role: StaffRole
    note: Note


class AssistantQuestion(Input):
    registration_id: UUID
    period: Period
    question: str = Field(min_length=3, max_length=1000)
    use_ai: StrictBool = False


class ReviewFacts(Input):
    expected_version: StrictInt = Field(ge=0)
    source_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    credit_claimed: StrictBool | None = None
    reversed_on: date | None = None
    reversed_tax: Money | None = None
    supplier_3b_filed_on: date | None = None
    supplier_3b_unfiled_as_of: date | None = None
    notice_reference: str = Field(default="", max_length=128)
    notice_response_due_on: date | None = None
    notice_response_recorded: StrictBool | None = None
    credit_review_due_on: date | None = None
    note: Note

    @model_validator(mode="after")
    def recorded_facts(self):
        for value in (self.reversed_on, self.supplier_3b_filed_on, self.supplier_3b_unfiled_as_of):
            if value and value > date.today():
                raise ValueError("Recorded events cannot be in the future")
        if self.reversed_tax is not None and self.reversed_on is None:
            raise ValueError("A reversal amount needs its recorded reversal date")
        if self.notice_response_due_on and not self.notice_reference.strip():
            raise ValueError("A notice deadline needs its notice reference")
        return self


class CreateProcess(Input):
    passport_id: UUID | None = None
    batch_id: UUID | None = None

    @model_validator(mode="after")
    def one_source(self):
        if (self.passport_id is None) == (self.batch_id is None):
            raise ValueError("Select exactly one invoice or batch")
        return self


class AssignNode(Input):
    expected_version: StrictInt = Field(ge=1)
    user_id: UUID
    due_on: date | None = None
    note: Note


class TransitionNode(Input):
    expected_version: StrictInt = Field(ge=1)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: Literal["IN_PROGRESS", "BLOCKED", "DONE"]
    note: Note


class SuggestionReview(Input):
    passport_id: UUID
    suggestion_id: str = Field(pattern=r"^[a-z0-9_-]{1,80}$")
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    conclusion: Literal["ACTION_REVIEWED", "NOT_APPLICABLE", "MORE_EVIDENCE"]
    note: Note


class ChooseStatement(Input):
    registration_id: UUID
    period: Period
    import_id: UUID
