"""Private runs, result pagination and explicit human review commands."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.access import authenticated, envelope, service
from app.api.imports import request_key
from app.contracts.runs import (
    ResultListResponse,
    ResultResponse,
    ResultStatus,
    ReviewCreate,
    RunCreate,
    RunListResponse,
    RunResponse,
)

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["Reconciliation"])


def runs(request):
    service(request)
    return request.app.state.runs


@router.post("/runs", status_code=202, response_model=RunResponse)
def create(request: Request, workspace_id: UUID, payload: RunCreate):
    identity = authenticated(request, mutation=True)
    return envelope(
        request,
        runs(request).create(
            identity,
            str(workspace_id),
            payload.model_dump(mode="json"),
            request_key(request),
            request.state.request_id,
        ),
    )


@router.get("/runs", response_model=RunListResponse)
def list_runs(
    request: Request,
    workspace_id: UUID,
    registration_id: UUID | None = None,
    period: str | None = Query(default=None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    return envelope(
        request,
        runs(request).list_runs(
            authenticated(request),
            str(workspace_id),
            str(cursor) if cursor else None,
            limit,
            str(registration_id) if registration_id else None,
            period,
        ),
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
def detail(request: Request, workspace_id: UUID, run_id: UUID):
    return envelope(
        request, runs(request).detail(authenticated(request), str(workspace_id), str(run_id))
    )


@router.get("/runs/{run_id}/results", response_model=ResultListResponse)
def results(
    request: Request,
    workspace_id: UUID,
    run_id: UUID,
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    status: ResultStatus | None = None,
):
    return envelope(
        request,
        runs(request).results(
            authenticated(request), str(workspace_id), str(run_id), cursor, limit, status
        ),
    )


@router.get("/results/{result_id}", response_model=ResultResponse)
def result_detail(request: Request, workspace_id: UUID, result_id: UUID):
    return envelope(
        request,
        runs(request).result_detail(authenticated(request), str(workspace_id), str(result_id)),
    )


@router.post("/results/{result_id}/review", response_model=ResultResponse)
def review(request: Request, workspace_id: UUID, result_id: UUID, payload: ReviewCreate):
    identity = authenticated(request, mutation=True)
    return envelope(
        request,
        runs(request).review(
            identity,
            str(workspace_id),
            str(result_id),
            payload.model_dump(mode="json"),
            request_key(request),
            request.state.request_id,
        ),
    )
