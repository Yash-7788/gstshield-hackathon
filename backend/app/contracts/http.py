"""Small stable HTTP contract, shared by successful and failed JSON responses."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class Meta(BaseModel):
    request_id: str


class HealthData(BaseModel):
    status: str


class HealthResponse(BaseModel):
    data: HealthData
    meta: Meta


class ErrorDetail(BaseModel):
    field: str
    row: int | None = None
    reason: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail]
    retryable: bool


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorBody
    meta: Meta


def error_payload(
    request_id: str,
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "retryable": retryable,
        },
        "meta": {"request_id": request_id},
    }
