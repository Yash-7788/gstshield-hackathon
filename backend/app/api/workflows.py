"""Private case, proposal and report commands, all within existing browser sessions."""

from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.api.access import authenticated, envelope, service
from app.api.imports import request_key
from app.contracts.workflows import (
    ArtifactCreate,
    ArtifactListResponse,
    ArtifactResponse,
    CaseCreate,
    CaseEvidence,
    CaseListResponse,
    CaseResponse,
    CaseTransition,
    CleanupCreate,
    CleanupResponse,
    ProposalCreate,
    ProposalListResponse,
    ProposalResponse,
    Reason,
)

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["Cases and reports"])


def workflow(request, name):
    service(request)
    return getattr(request.app.state, name)


def command(request, name, method, workspace, payload, identifier=None, **options):
    identity = authenticated(request, mutation=True)
    args = [identity, str(workspace)]
    if identifier is not None:
        args.append(str(identifier))
    args.extend([payload.model_dump(mode="json"), request_key(request)])
    if method != "cleanup":
        args.append(request.state.request_id)
    return envelope(request, getattr(workflow(request, name), method)(*args, **options))


@router.post("/cases", status_code=201, response_model=CaseResponse)
def create_case(request: Request, workspace_id: UUID, payload: CaseCreate):
    return command(request, "cases", "create", workspace_id, payload)


@router.get("/cases", response_model=CaseListResponse)
def list_cases(
    request: Request,
    workspace_id: UUID,
    registration_id: UUID | None = None,
    period: str | None = Query(default=None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=20),
):
    return envelope(
        request,
        workflow(request, "cases").list_cases(
            authenticated(request),
            str(workspace_id),
            str(cursor) if cursor else "",
            limit,
            str(registration_id) if registration_id else None,
            period,
        ),
    )


@router.get("/cases/{case_id}", response_model=CaseResponse)
def case_detail(request: Request, workspace_id: UUID, case_id: UUID):
    return envelope(
        request,
        workflow(request, "cases").detail(authenticated(request), str(workspace_id), str(case_id)),
    )


@router.post("/cases/{case_id}/evidence", response_model=CaseResponse)
def evidence(request: Request, workspace_id: UUID, case_id: UUID, payload: CaseEvidence):
    return command(request, "cases", "mutate", workspace_id, payload, case_id)


@router.post("/cases/{case_id}/transition", response_model=CaseResponse)
def transition(request: Request, workspace_id: UUID, case_id: UUID, payload: CaseTransition):
    return command(request, "cases", "mutate", workspace_id, payload, case_id, transition=True)


@router.post("/proposals", status_code=201, response_model=ProposalResponse)
def create_proposal(request: Request, workspace_id: UUID, payload: ProposalCreate):
    return command(request, "proposals", "create", workspace_id, payload)


@router.get("/proposals", response_model=ProposalListResponse)
def list_proposals(
    request: Request,
    workspace_id: UUID,
    registration_id: UUID | None = None,
    period: str | None = Query(default=None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=20),
):
    return envelope(
        request,
        workflow(request, "proposals").list_proposals(
            authenticated(request),
            str(workspace_id),
            str(cursor) if cursor else "",
            limit,
            str(registration_id) if registration_id else None,
            period,
        ),
    )


@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
def proposal_detail(request: Request, workspace_id: UUID, proposal_id: UUID):
    return envelope(
        request,
        workflow(request, "proposals").detail(
            authenticated(request), str(workspace_id), str(proposal_id)
        ),
    )


@router.post("/proposals/{proposal_id}/approve", response_model=ProposalResponse)
def approve(request: Request, workspace_id: UUID, proposal_id: UUID, payload: Reason):
    return command(request, "proposals", "approve", workspace_id, payload, proposal_id)


@router.post("/artifacts", status_code=202, response_model=ArtifactResponse)
def create_artifact(request: Request, workspace_id: UUID, payload: ArtifactCreate):
    return command(request, "reports", "create", workspace_id, payload)


@router.post("/artifacts/cleanup", response_model=CleanupResponse)
def cleanup(request: Request, workspace_id: UUID, payload: CleanupCreate):
    return command(request, "reports", "cleanup", workspace_id, payload)


@router.get("/artifacts", response_model=ArtifactListResponse)
def list_artifacts(
    request: Request,
    workspace_id: UUID,
    registration_id: UUID | None = None,
    period: str | None = Query(default=None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=20),
):
    return envelope(
        request,
        workflow(request, "reports").list_artifacts(
            authenticated(request),
            str(workspace_id),
            str(cursor) if cursor else "",
            limit,
            str(registration_id) if registration_id else None,
            period,
        ),
    )


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def artifact_detail(request: Request, workspace_id: UUID, artifact_id: UUID):
    return envelope(
        request,
        workflow(request, "reports").detail(
            authenticated(request), str(workspace_id), str(artifact_id)
        ),
    )


@router.get("/artifacts/{artifact_id}/download")
def download(request: Request, workspace_id: UUID, artifact_id: UUID, historical: bool = False):
    content, filename, mime, stale = workflow(request, "reports").download(
        authenticated(request), str(workspace_id), str(artifact_id), historical
    )
    return Response(
        content,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-GSTShield-Historical": "true" if stale else "false",
        },
    )
