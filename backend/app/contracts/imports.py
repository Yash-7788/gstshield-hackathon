"""Website import inputs and typed private preview/job responses."""

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from app.contracts.http import ErrorDetail, Meta
from app.domain.imports import FIELDS


class UploadMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["PURCHASE", "PORTAL_2B"]
    registration_id: UUID
    period: str
    adapter_version: Literal["csv-v1", "xlsx-v1", "canonical-demo-v1"]
    sheet_name: str | None = Field(default=None, max_length=128)
    mapping: dict[str, str] = Field(default_factory=dict, max_length=50)
    supersedes_import_id: UUID | None = None

    @field_validator("period")
    @classmethod
    def period_check(cls, value):
        if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value) or value.startswith("0000"):
            raise ValueError("Expected calendar month")
        return value

    @field_validator("mapping")
    @classmethod
    def mapping_check(cls, value):
        if (
            not set(value) <= FIELDS
            or len(set(value.values())) != len(value)
            or any(
                not header or len(header) > 128 or any(ord(c) < 32 or ord(c) == 127 for c in header)
                for header in value.values()
            )
        ):
            raise ValueError("Invalid or ambiguous mapping")
        return value

    @model_validator(mode="after")
    def adapter_check(self):
        if self.adapter_version == "canonical-demo-v1" and (
            self.kind != "PORTAL_2B" or self.mapping
        ):
            raise ValueError("Demo JSON is a fixed portal adapter")
        if self.adapter_version != "xlsx-v1" and self.sheet_name is not None:
            raise ValueError("Only XLSX accepts sheet selection")
        if self.sheet_name is not None and (
            not self.sheet_name or any(ord(c) < 32 for c in self.sheet_name)
        ):
            raise ValueError("Invalid sheet selection")
        return self


class MappingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: StrictInt = Field(gt=0)
    sheet_name: str | None = Field(default=None, max_length=128)
    mapping: dict[str, str] = Field(max_length=50)
    mapping_check = field_validator("mapping")(classmethod(UploadMetadata.mapping_check.__func__))

    @field_validator("sheet_name")
    @classmethod
    def sheet_check(cls, value):
        if value is not None and (not value or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ValueError("Invalid sheet selection")
        return value


class ImportConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: StrictInt = Field(gt=0)
    allow_rejected_rows: StrictBool = False
    confirmed_supersession: StrictBool = False


class ImportData(BaseModel):
    id: UUID
    workspace_id: UUID
    registration_id: UUID
    job_id: UUID
    file_sha256: str
    kind: Literal["PURCHASE", "PORTAL_2B"]
    period: str
    adapter_version: str
    sheet_name: str | None
    mapping: dict[str, str]
    columns: list[str]
    provenance: Literal["USER_PROVIDED", "SYNTHETIC_DEMO"]
    state: Literal["RECEIVED", "PARSING", "AWAITING_CONFIRMATION", "READY", "FAILED", "SUPERSEDED"]
    version: int
    accepted_rows: int
    rejected_rows: int
    duplicate_rows: int
    errors: list[ErrorDetail]
    generated_at: datetime | None
    supersedes_import_id: UUID | None
    derived_from_import_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ImportResponse(BaseModel):
    data: ImportData
    meta: Meta


class ImportListData(BaseModel):
    imports: list[ImportData]
    next_cursor: UUID | None


class ImportListResponse(BaseModel):
    data: ImportListData
    meta: Meta


class PreviewRow(BaseModel):
    row_number: int
    original: dict[str, str | int | float | None]
    canonical: dict
    errors: list[ErrorDetail]
    accepted: bool
    duplicate: bool


class PreviewData(BaseModel):
    rows: list[PreviewRow]
    next_cursor: int | None


class PreviewResponse(BaseModel):
    data: PreviewData
    meta: Meta


class JobData(BaseModel):
    id: UUID
    workspace_id: UUID
    import_id: UUID | None = None
    run_id: UUID | None = None
    artifact_id: UUID | None = None
    kind: Literal["IMPORT", "RUN", "ARTIFACT"]
    state: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class JobResponse(BaseModel):
    data: JobData
    meta: Meta
