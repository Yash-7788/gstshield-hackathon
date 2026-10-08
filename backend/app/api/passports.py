"""Authenticated invoice workbench; writes reuse origin, CSRF and workspace checks."""

import io
from html import escape
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import ValidationError
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.api.access import authenticated, envelope
from app.api.imports import bounded_upload, request_key
from app.contracts import passports as models
from app.errors import APIError

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/passports")


def service(request):
    return request.app.state.passports


@router.get("", response_model=models.PassportListResponse)
def listing(
    request: Request,
    workspace_id: UUID,
    registration_id: UUID,
    period: str = Query(pattern=r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])$"),
):
    return envelope(
        request,
        service(request).listing(
            authenticated(request), str(workspace_id), str(registration_id), period
        ),
    )


@router.post("/from-source", response_model=models.PassportResponse)
def from_source(request: Request, workspace_id: UUID, payload: models.PassportCreate):
    identity = authenticated(request, mutation=True)
    result = service(request).from_source(
        identity, str(workspace_id), payload.model_dump(mode="json"), request_key(request)
    )
    service(request).ensure_comparison(identity, str(workspace_id), result["id"])
    return envelope(request, result)


@router.post("/documents", response_model=models.PassportResponse)
async def upload(request: Request, workspace_id: UUID):
    identity = authenticated(request, mutation=True)
    svc, ws = service(request), str(workspace_id)
    svc.imports.authorize(identity, ws, mutation=True)
    key = request_key(request)
    if not svc.imports.upload_slot.acquire(blocking=False):
        raise APIError(503, "UPLOAD_BUSY", "An upload is already being received.", retry_after=1)
    form = None
    try:
        form = await bounded_upload(request, svc.settings)
        if (
            len(form.multi_items()) != 4
            or set(form.keys()) != {"file", "registration_id", "period", "consent"}
            or not isinstance(form["file"], UploadFile)
        ):
            raise APIError(
                422, "UPLOAD_FIELDS", "Choose an invoice, registration, period and AI consent."
            )
        try:
            meta = models.DocumentMetadata.model_validate(
                {
                    "registration_id": form["registration_id"],
                    "period": form["period"],
                    "consent": form["consent"] == "true",
                }
            )
        except ValidationError:
            raise APIError(
                422, "UPLOAD_FIELDS", "Check the selected registration and period."
            ) from None
        content = await form["file"].read(svc.settings.max_upload_bytes + 1)
        result = await run_in_threadpool(
            svc.upload,
            identity,
            ws,
            str(meta.registration_id),
            meta.period,
            content,
            form["file"].filename or "invoice",
            meta.consent,
            key,
        )
        return envelope(request, result)
    finally:
        if form is not None:
            await form.close()
        svc.imports.upload_slot.release()


@router.post("/intelligence", response_model=models.IntelligenceResponse)
def intelligence(request: Request, workspace_id: UUID, payload: models.CopilotQuery):
    return envelope(
        request,
        service(request).intelligence(
            authenticated(request, mutation=True),
            str(workspace_id),
            payload.model_dump(mode="json"),
        ),
    )


@router.get("/{passport_id}", response_model=models.PassportResponse)
def detail(request: Request, workspace_id: UUID, passport_id: UUID):
    return envelope(
        request,
        service(request).detail(authenticated(request), str(workspace_id), str(passport_id)),
    )


def command(request, workspace_id, passport_id, payload, method, kind=None):
    identity = authenticated(request, mutation=True)
    args = (
        identity,
        str(workspace_id),
        str(passport_id),
        payload.model_dump(mode="json"),
        request_key(request),
    )
    result = (
        getattr(service(request), method)(*args, kind=kind)
        if kind
        else getattr(service(request), method)(*args)
    )
    if method == "confirm":
        try:
            request.app.state.processes.create(
                identity,
                str(workspace_id),
                {"passport_id": str(passport_id), "batch_id": None},
                request_key(request),
            )
        except APIError as exc:
            # Confirmation is already saved. Preserve a recoverable automation status.
            with service(request).store.transaction() as con:
                service(request).authorize(con, identity, str(workspace_id))
                service(request).event(
                    con,
                    identity,
                    str(workspace_id),
                    str(passport_id),
                    "AUTO_PROCESS_DELAYED",
                    {"code": exc.code, "message": exc.message},
                )
    if method in {"confirm", "evidence", "simulate_fetch", "details"}:
        service(request).ensure_comparison(identity, str(workspace_id), str(passport_id))
    try:
        request.app.state.processes.sync_invoice(identity, str(workspace_id), str(passport_id))
    except APIError as exc:
        with service(request).store.transaction() as con:
            service(request).authorize(con, identity, str(workspace_id))
            service(request).event(
                con,
                identity,
                str(workspace_id),
                str(passport_id),
                "AUTO_PROCESS_DELAYED",
                {"code": exc.code, "message": exc.message},
            )
    return envelope(request, result)


@router.get("/{passport_id}/workflow", response_model=models.InvoiceWorkflowResponse)
def workflow(request: Request, workspace_id: UUID, passport_id: UUID):
    return envelope(
        request,
        service(request).workflow(
            authenticated(request), str(workspace_id), str(passport_id), request.app.state.proposals
        ),
    )


@router.post("/{passport_id}/confirm", response_model=models.PassportResponse)
def confirm(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.PassportConfirm
):
    return command(request, workspace_id, passport_id, payload, "confirm")


@router.post("/{passport_id}/evidence", response_model=models.PassportResponse)
def evidence(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.CommercialEvidence
):
    return command(request, workspace_id, passport_id, payload, "evidence")


@router.post("/{passport_id}/clocks", response_model=models.PassportResponse)
def clocks(request: Request, workspace_id: UUID, passport_id: UUID, payload: models.ClockEvidence):
    return command(request, workspace_id, passport_id, payload, "evidence", "CLOCKS")


@router.post("/{passport_id}/portal", response_model=models.PassportResponse)
def portal(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.PortalSelection
):
    return command(request, workspace_id, passport_id, payload, "evidence", "PORTAL")


@router.post("/{passport_id}/approve", response_model=models.PassportResponse)
def approve(request: Request, workspace_id: UUID, passport_id: UUID, payload: models.GateApproval):
    return command(request, workspace_id, passport_id, payload, "approve")


@router.post("/{passport_id}/resolution", response_model=models.PassportResponse)
def resolution(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.ResolutionCommand
):
    return command(request, workspace_id, passport_id, payload, "resolution")


@router.post("/{passport_id}/simulate-fetch", response_model=models.PassportResponse)
def simulate(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.FetchSimulation
):
    return command(request, workspace_id, passport_id, payload, "simulate_fetch")


@router.post("/{passport_id}/remove", response_model=models.PassportResponse)
def remove(request: Request, workspace_id: UUID, passport_id: UUID, payload: models.RemoveInvoice):
    return command(request, workspace_id, passport_id, payload, "remove")


@router.post("/{passport_id}/refresh", response_model=models.PassportResponse)
def refresh(request: Request, workspace_id: UUID, passport_id: UUID):
    request_key(request)
    identity = authenticated(request, mutation=True)
    result = service(request).refresh(identity, str(workspace_id), str(passport_id))
    service(request).ensure_comparison(identity, str(workspace_id), str(passport_id))
    return envelope(request, result)


@router.post("/{passport_id}/retry-extraction", response_model=models.PassportResponse)
def retry(request: Request, workspace_id: UUID, passport_id: UUID):
    request_key(request)
    return envelope(
        request,
        service(request).extract(
            authenticated(request, mutation=True), str(workspace_id), str(passport_id)
        ),
    )


@router.post("/{passport_id}/scenario", response_model=models.IntelligenceResponse)
def scenario(request: Request, workspace_id: UUID, passport_id: UUID, payload: models.Scenario):
    return envelope(
        request,
        service(request).scenario(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(passport_id),
            payload.model_dump(mode="json"),
        ),
    )


@router.get("/{passport_id}/notice-draft", response_model=models.IntelligenceResponse)
def notice(request: Request, workspace_id: UUID, passport_id: UUID):
    return envelope(
        request,
        service(request).notice(authenticated(request), str(workspace_id), str(passport_id)),
    )


@router.get("/{passport_id}/dossier")
def dossier(request: Request, workspace_id: UUID, passport_id: UUID):
    view = service(request).detail(authenticated(request), str(workspace_id), str(passport_id))
    target = io.BytesIO()
    styles = getSampleStyleSheet()
    story = [Paragraph("GSTShield Invoice History", styles["Title"])]
    values = {
        "Invoice": view["fields"].get("invoice_number", "Unconfirmed"),
        "Source": view["purchase_import_id"],
        "Evidence fingerprint": view["source_signature"],
        "Findings": view["findings"],
        "Payment decision": view["approval"],
        "Correction request": view["resolution"],
        "Supplier delivery history": view["supplier_channel"],
    }
    for label, value in values.items():
        # Strip < > before passing to ReportLab Paragraph — it interprets a subset of HTML tags.
        safe_text = escape(label + ": " + str(value)).replace("&lt;", "(").replace("&gt;", ")")
        story.extend(
            [Spacer(1, 8), Paragraph(safe_text, styles["BodyText"])]
        )
    for event in view["history"][-100:]:
        safe_event = escape(str(event)).replace("&lt;", "(").replace("&gt;", ")")
        story.extend([Spacer(1, 6), Paragraph(safe_event, styles["BodyText"])])
    SimpleDocTemplate(target).build(story)
    return Response(
        target.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="gstshield-passport_{passport_id}.pdf"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{passport_id}/watch", response_model=models.PassportResponse)
def watch(request: Request, workspace_id: UUID, passport_id: UUID, payload: models.WatchMode):
    return command(request, workspace_id, passport_id, payload, "watch_mode")


@router.post("/{passport_id}/notice-assistance", response_model=models.IntelligenceResponse)
def notice_assistance(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.NoticeAssistance
):
    return envelope(
        request,
        service(request).notice_assistance(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(passport_id),
            payload.model_dump(mode="json"),
        ),
    )


@router.post("/{passport_id}/details", response_model=models.PassportResponse)
def details(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.InvoiceDetails
):
    return command(request, workspace_id, passport_id, payload, "details")


@router.post("/{passport_id}/ims-review", response_model=models.PassportResponse)
def ims_review(request: Request, workspace_id: UUID, passport_id: UUID, payload: models.IMSReview):
    return command(request, workspace_id, passport_id, payload, "ims_review")


@router.post("/{passport_id}/supplier-invite", response_model=models.IntelligenceResponse)
def supplier_invite(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.SupplierInvite
):
    return envelope(
        request,
        service(request).channel.invite(
            authenticated(request, mutation=True),
            str(workspace_id),
            str(passport_id),
            payload.model_dump(mode="json"),
            request_key(request),
        ),
    )


@router.post("/{passport_id}/supplier-send", response_model=models.PassportResponse)
def supplier_send(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.SupplierSend
):
    svc = service(request)
    identity = authenticated(request, mutation=True)
    svc.channel.send(
        identity,
        str(workspace_id),
        str(passport_id),
        payload.model_dump(mode="json"),
        request_key(request),
    )
    return envelope(
        request, svc.detail(identity, str(workspace_id), str(passport_id))
    )


@router.post("/{passport_id}/demo-bank-payment", response_model=models.PassportResponse)
def demo_bank_payment(
    request: Request, workspace_id: UUID, passport_id: UUID, payload: models.DemoBankPayment
):
    return command(request, workspace_id, passport_id, payload, "demo_bank_payment")


@router.post("/{passport_id}/evidence-documents", response_model=models.IntelligenceResponse)
async def evidence_document(request: Request, workspace_id: UUID, passport_id: UUID):
    identity = authenticated(request, mutation=True)
    svc, ws = service(request), str(workspace_id)
    svc.imports.authorize(identity, ws, mutation=True)
    key = request_key(request)
    if not svc.imports.upload_slot.acquire(blocking=False):
        raise APIError(503, "UPLOAD_BUSY", "An upload is already being received.", retry_after=1)
    form = None
    try:
        form = await bounded_upload(request, svc.settings)
        if (
            len(form.multi_items()) != 3
            or set(form.keys()) != {"file", "kind", "consent"}
            or not isinstance(form["file"], UploadFile)
        ):
            raise APIError(
                422, "UPLOAD_FIELDS", "Choose a supporting file, its type and AI consent."
            )
        content = await form["file"].read(svc.settings.max_upload_bytes + 1)
        result = await run_in_threadpool(
            svc.extract_commercial_document,
            identity,
            ws,
            str(passport_id),
            str(form["kind"]),
            content,
            form["file"].filename or "supporting-record",
            form["consent"] == "true",
            key,
        )
        return envelope(request, result)
    finally:
        if form is not None:
            await form.close()
        svc.imports.upload_slot.release()
