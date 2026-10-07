"""Shared private work-queue operations for the eventual browser and phone adapters."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.access import authenticated, envelope
from app.api.workflows import command, workflow
from app.contracts.actions import (
    ActionListResponse,
    ActionOutcome,
    ActionResponse,
    ActionState,
    ActionUpdate,
    Followup,
    WorksheetResponse,
)

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["Business actions"])


@router.get("/actions", response_model=ActionListResponse)
def actions(
    request: Request,
    workspace_id: UUID,
    registration_id: UUID | None = None,
    period: str | None = Query(default=None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=20),
    state: ActionState | None = None,
    due_only: bool = False,
):
    return envelope(
        request,
        workflow(request, "actions").list_actions(
            authenticated(request),
            str(workspace_id),
            str(cursor) if cursor else "",
            limit,
            state,
            due_only,
            str(registration_id) if registration_id else None,
            period,
        ),
    )


@router.get("/actions/{action_id}", response_model=ActionResponse)
def detail(request: Request, workspace_id: UUID, action_id: UUID):
    return envelope(
        request,
        workflow(request, "actions").detail(
            authenticated(request),
            str(workspace_id),
            str(action_id),
        ),
    )


@router.post("/actions/{action_id}/update", response_model=ActionResponse)
def update(request: Request, workspace_id: UUID, action_id: UUID, payload: ActionUpdate):
    return command(request, "actions", "mutate", workspace_id, payload, action_id, kind="update")


@router.post("/actions/{action_id}/followups", response_model=ActionResponse)
def followup(request: Request, workspace_id: UUID, action_id: UUID, payload: Followup):
    return command(request, "actions", "mutate", workspace_id, payload, action_id, kind="followups")


@router.post("/actions/{action_id}/outcomes", response_model=ActionResponse)
def outcome(request: Request, workspace_id: UUID, action_id: UUID, payload: ActionOutcome):
    return command(request, "actions", "mutate", workspace_id, payload, action_id, kind="outcomes")


@router.get("/actions/{action_id}/worksheet", response_model=WorksheetResponse)
def worksheet(request: Request, workspace_id: UUID, action_id: UUID):
    return envelope(
        request,
        workflow(request, "actions").worksheet(
            authenticated(request),
            str(workspace_id),
            str(action_id),
        ),
    )
