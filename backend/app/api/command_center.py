"""Authenticated guidance; no page read creates approvals or financial facts."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.access import authenticated, envelope
from app.contracts.command_center import KnowledgeResponse
from app.domain.knowledge import GLOSSARY, guide

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/command-center", tags=["Guidance"])


@router.get("/glossary", response_model=KnowledgeResponse)
def glossary(request: Request, workspace_id: UUID):
    identity = authenticated(request)
    service = request.app.state.passports
    with service.store.transaction(write=False) as con:
        service.authorize(con, identity, str(workspace_id))
    return envelope(
        request,
        {
            "terms": GLOSSARY,
            ("example"): (
                "Goods INR 100000 + recorded GST INR 18000 = invoice I"
                "NR 118000. The bill does not prove delivery, filing o"
                "r payment."
            ),
        },
    )


@router.get("/invoices/{passport_id}/guide", response_model=KnowledgeResponse)
def invoice_guide(request: Request, workspace_id: UUID, passport_id: UUID):
    identity = authenticated(request)
    service = request.app.state.passports
    with service.store.transaction(write=False) as con:
        service.authorize(con, identity, str(workspace_id))
        role = service.access.require_membership(
            con, identity, str(workspace_id), roles={"OWNER", "REVIEWER", "VIEWER"}
        )
        view = service.project(con, service.row(con, str(workspace_id), str(passport_id)))
    return envelope(request, guide(view, role != "VIEWER"))
