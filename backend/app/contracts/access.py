"""Phase 2 website contracts. No credentials are returned in JSON."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from app.contracts.http import Meta
from app.services.access import password_value, username_value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    password: SecretStr
    portal: Literal["owner", "team"] | None = None

    @field_validator("username")
    @classmethod
    def username_check(cls, value: str) -> str:
        return username_value(value)

    @field_validator("password")
    @classmethod
    def password_check(cls, value: SecretStr) -> SecretStr:
        password_value(value.get_secret_value())
        return value


class SessionData(BaseModel):
    user_id: UUID
    username: str
    expires_at: datetime
    csrf_token: str
    portal: Literal["owner", "team"] | None = None


class SessionResponse(BaseModel):
    data: SessionData
    meta: Meta


class WorkspaceData(BaseModel):
    id: UUID
    name: str
    role: Literal["OWNER", "REVIEWER", "VIEWER"]
    created_at: datetime
    version: int


class WorkspaceResponse(BaseModel):
    data: list[WorkspaceData]
    meta: Meta


class RegistrationData(BaseModel):
    id: UUID
    workspace_id: UUID
    gstin: str
    display_name: str
    created_at: datetime
    version: int


class RegistrationResponse(BaseModel):
    data: list[RegistrationData]
    meta: Meta


class LogoutData(BaseModel):
    logged_out: Literal[True] = True


class LogoutResponse(BaseModel):
    data: LogoutData
    meta: Meta
