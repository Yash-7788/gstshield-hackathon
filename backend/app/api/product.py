"""Authenticated owner/team APIs. Entry choices do not change permissions."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.access import authenticated, envelope
from app.api.imports import request_key
from app.contracts import product as models
from app.contracts.command_center import KnowledgeResponse

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/product", tags=["Owner and team"])
PeriodQuery = Query(pattern=r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])$")


def svc(request):
    return request.app.state.business


@router.get("/portal", response_model=KnowledgeResponse)
def portal(request: Request, workspace_id: UUID):
    return envelope(request, svc(request).portal(authenticated(request), str(workspace_id)))


@router.get("/business", response_model=KnowledgeResponse)
def business(
    request: Request, workspace_id: UUID, registration_id: UUID, period: str = PeriodQuery
):
    return envelope(
        request,
        svc(request).business(
            authenticated(request), str(workspace_id), str(registration_id), period
        ),
    )


@router.post("/business", response_model=KnowledgeResponse)
def save_business(request: Request, workspace_id: UUID, payload: models.SaveBusiness):
    return envelope(
        request,
        svc(request).save_business(
            authenticated(request, mutation=True),
            str(workspace_id),
            payload.model_dump(mode="json"),
            request_key(request),
        ),
    )


@router.get("/owner-summary", response_model=KnowledgeResponse)
def owner_summary(
    request: Request, workspace_id: UUID, registration_id: UUID, period: str = PeriodQuery
):
    return envelope(
        request,
        svc(request).owner_summary(
            authenticated(request), str(workspace_id), str(registration_id), period
        ),
    )


@router.get("/team", response_model=KnowledgeResponse)
def team(request: Request, workspace_id: UUID):
    return envelope(request, svc(request).team(authenticated(request), str(workspace_id)))


@router.post("/team/members", response_model=KnowledgeResponse)
def create_member(request: Request, workspace_id: UUID, payload: models.CreateMember):
    data = payload.model_dump(mode="json")
    data["password"] = payload.password.get_secret_value()
    return envelope(
        request,
        svc(request).create_member(
            authenticated(request, mutation=True), str(workspace_id), data, request_key(request)
        ),
    )


@router.post("/team/setup", response_model=KnowledgeResponse)
def create_team(request: Request, workspace_id: UUID, payload: models.CreateTeam):
    data = payload.model_dump(mode="json")
    for member, supplied in zip(data["members"], payload.members, strict=True):
        member["password"] = supplied.password.get_secret_value()
    return envelope(
        request,
        svc(request).create_team(
            authenticated(request, mutation=True), str(workspace_id), data, request_key(request)
        ),
    )


@router.patch("/team/members/{user_id}", response_model=KnowledgeResponse)
def update_member(
    request: Request, workspace_id: UUID, user_id: UUID, payload: models.UpdateMember
):
    return envelope(
        request,
        svc(request).update_member(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(user_id),
            payload.model_dump(mode="json"),
            request_key(request),
        ),
    )


@router.post("/team/members/{user_id}/password", response_model=KnowledgeResponse)
def member_password(
    request: Request, workspace_id: UUID, user_id: UUID, payload: models.MemberPassword
):
    return envelope(
        request,
        svc(request).member_password(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(user_id),
            {
                "expected_version": payload.expected_version,
                "password": payload.password.get_secret_value(),
            },
            request_key(request),
        ),
    )


@router.get("/contributions", response_model=KnowledgeResponse)
def contributions(
    request: Request, workspace_id: UUID, registration_id: UUID, period: str = PeriodQuery
):
    return envelope(
        request,
        {
            "updates": svc(request).contributions(
                authenticated(request), str(workspace_id), str(registration_id), period
            )
        },
    )


@router.post("/contributions", response_model=KnowledgeResponse)
def contribute(request: Request, workspace_id: UUID, payload: models.Contribution):
    return envelope(
        request,
        svc(request).contribute(
            authenticated(request, mutation=True),
            str(workspace_id),
            payload.model_dump(mode="json"),
            request_key(request),
        ),
    )


@router.get("/invoices/{passport_id}/review-facts", response_model=KnowledgeResponse)
def review_facts(request: Request, workspace_id: UUID, passport_id: UUID):
    return envelope(
        request,
        request.app.state.product_guidance.facts(
            authenticated(request), str(workspace_id), str(passport_id)
        ),
    )


@router.post("/invoices/{passport_id}/review-facts", response_model=KnowledgeResponse)
def save_review_facts(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.ReviewFacts
):
    return envelope(
        request,
        request.app.state.product_guidance.save_facts(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(passport_id),
            payload.model_dump(mode="json"),
            request_key(request),
        ),
    )


@router.get("/invoices/{passport_id}/traps", response_model=KnowledgeResponse)
def traps(request: Request, workspace_id: UUID, passport_id: UUID):
    return envelope(
        request,
        request.app.state.product_guidance.traps(
            authenticated(request), str(workspace_id), str(passport_id)
        ),
    )


@router.get("/invoices/{passport_id}/tax-suggestions", response_model=KnowledgeResponse)
def tax_suggestions(request: Request, workspace_id: UUID, passport_id: UUID):
    return envelope(
        request,
        request.app.state.product_guidance.tax(
            authenticated(request), str(workspace_id), str(passport_id)
        ),
    )


@router.post("/tax-suggestions/review", response_model=KnowledgeResponse)
def tax_review(request: Request, workspace_id: UUID, payload: models.SuggestionReview):
    identity = authenticated(request, mutation=True)
    ws = str(workspace_id)
    result = request.app.state.product_guidance.review(
        identity, ws, payload.model_dump(mode="json"), request_key(request)
    )
    request.app.state.processes.sync_invoice(identity, ws, str(payload.passport_id))
    return envelope(request, result)


@router.get("/schemes", response_model=KnowledgeResponse)
def schemes(request: Request, workspace_id: UUID, registration_id: UUID, period: str = PeriodQuery):
    return envelope(
        request,
        request.app.state.product_guidance.directory(
            authenticated(request), str(workspace_id), "schemes", str(registration_id), period
        ),
    )


@router.get("/competitors", response_model=KnowledgeResponse)
def competitors(request: Request, workspace_id: UUID):
    return envelope(
        request,
        request.app.state.product_guidance.directory(
            authenticated(request), str(workspace_id), "competitor_comparison"
        ),
    )


@router.post("/assistants/{role}", response_model=KnowledgeResponse)
def assistant(request: Request, workspace_id: UUID, role: str, payload: models.AssistantQuestion):
    return envelope(
        request,
        request.app.state.product_guidance.assistant(
            authenticated(request, mutation=True),
            str(workspace_id),
            role,
            payload.model_dump(mode="json"),
        ),
    )


@router.get("/workflows", response_model=KnowledgeResponse)
def processes(
    request: Request, workspace_id: UUID, registration_id: UUID, period: str = PeriodQuery
):
    return envelope(
        request,
        request.app.state.processes.listing(
            authenticated(request), str(workspace_id), str(registration_id), period
        ),
    )


@router.post("/workflows", response_model=KnowledgeResponse)
def create_process(request: Request, workspace_id: UUID, payload: models.CreateProcess):
    return envelope(
        request,
        request.app.state.processes.create(
            authenticated(request, mutation=True),
            str(workspace_id),
            payload.model_dump(mode="json"),
            request_key(request),
        ),
    )


@router.get("/workflows/{run_id}", response_model=KnowledgeResponse)
def process_detail(request: Request, workspace_id: UUID, run_id: UUID):
    return envelope(
        request,
        request.app.state.processes.detail(authenticated(request), str(workspace_id), str(run_id)),
    )


@router.post("/workflows/{run_id}/refresh", response_model=KnowledgeResponse)
def refresh_process(request: Request, workspace_id: UUID, run_id: UUID):
    return envelope(
        request,
        request.app.state.processes.refresh(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(run_id),
            request_key(request),
        ),
    )


@router.post("/nodes/{node_id}/assign", response_model=KnowledgeResponse)
def assign_node(request: Request, workspace_id: UUID, node_id: UUID, payload: models.AssignNode):
    return envelope(
        request,
        request.app.state.processes.assign(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(node_id),
            payload.model_dump(mode="json"),
            request_key(request),
        ),
    )


@router.post("/nodes/{node_id}/transition", response_model=KnowledgeResponse)
def transition_node(
    request: Request, workspace_id: UUID, node_id: UUID, payload: models.TransitionNode
):
    return envelope(
        request,
        request.app.state.processes.transition(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(node_id),
            payload.model_dump(mode="json"),
            request_key(request),
        ),
    )


@router.get("/notifications", response_model=KnowledgeResponse)
def notifications(request: Request, workspace_id: UUID):
    return envelope(
        request,
        request.app.state.processes.notifications(authenticated(request), str(workspace_id)),
    )


@router.post("/notifications/{notification_id}/read", response_model=KnowledgeResponse)
def read_notification(request: Request, workspace_id: UUID, notification_id: UUID):
    return envelope(
        request,
        request.app.state.processes.read_notification(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(notification_id),
            request_key(request),
        ),
    )


@router.post("/gst-statement", response_model=KnowledgeResponse)
def choose_statement(request: Request, workspace_id: UUID, payload: models.ChooseStatement):
    identity = authenticated(request, mutation=True)
    ws = str(workspace_id)
    service = svc(request)
    data = payload.model_dump(mode="json")
    key = request_key(request)
    with service.store.transaction() as con:
        from app.security.roles import require_role

        require_role(service.access, con, identity, ws, {"CA"})
        source = service.passports.imports.scoped(
            con, identity, ws, data["import_id"], mutation=True
        )
        if (
            source["kind"] != "PORTAL_2B"
            or source["state"] != "READY"
            or source["registration_id"] != data["registration_id"]
            or source["period"] != data["period"]
        ):
            from app.errors import APIError

            raise APIError(
                409,
                "SOURCE_NOT_READY",
                "Choose a confirmed GST statement for this company and month.",
            )
        previous = service.operation(con, identity, ws, "gst-statement", key, data)
        if previous:
            result = previous
        else:
            service.audit(con, identity, ws, "GST_STATEMENT_SELECTED", data)
            result = {"saved": True, **data}
            service.record(con, identity, ws, "gst-statement", key, data, result)
    service.passports.compare_confirmed_sources(
        identity, ws, data["registration_id"], data["period"]
    )
    with service.store.transaction(write=False) as con:
        service.authorize(con, identity, ws)
        affected = con.execute(
            "SELECT DISTINCT passport_id FROM workflow_run WHERE workspace_id=? "
            "AND registration_id=? AND period=? AND passport_id IS NOT NULL",
            (ws, data["registration_id"], data["period"]),
        ).fetchall()
    for row in affected:
        request.app.state.processes.sync_invoice(identity, ws, row[0])
    return envelope(request, result)
