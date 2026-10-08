"""Signed provider callbacks plus separately authenticated website controls."""

import hashlib
import hmac
import json
import re
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response
from starlette.concurrency import run_in_threadpool

from app.api.access import authenticated, envelope
from app.api.imports import request_key
from app.contracts.whatsapp import (
    ChannelResponse,
    ConsentCodeResponse,
    LinkCodeResponse,
    LinkContext,
    LinkRevoke,
    LinkUpdate,
    SupplierConsentRequest,
    SupplierRecipientsResponse,
    SupplierSendRequest,
    SupplierSendResponse,
)
from app.errors import APIError
from app.security.http import unique_json_object
from app.services.whatsapp_followups import WhatsAppFollowups

router = APIRouter()


def channel(request):
    if not request.app.state.ready:
        raise APIError(503, "NOT_READY", "Backend has not completed startup.", retry_after=1)
    return request.app.state.whatsapp


@router.get("/webhooks/whatsapp", include_in_schema=False)
def verify(request: Request):
    service = channel(request)
    service.enabled()
    params = request.query_params
    if (
        any(
            len(params.getlist(name)) != 1
            for name in ("hub.mode", "hub.verify_token", "hub.challenge")
        )
        or params.get("hub.mode") != "subscribe"
        or not hmac.compare_digest(
            params.get("hub.verify_token", "").encode(),
            service.settings.meta_verify_token.get_secret_value().encode(),
        )
        or not re.fullmatch(r"[0-9]{1,128}", params.get("hub.challenge", ""))
    ):
        raise APIError(403, "WEBHOOK_VERIFICATION", "Callback verification is not permitted.")
    return PlainTextResponse(params["hub.challenge"])


@router.post("/webhooks/whatsapp", include_in_schema=False)
async def receive(request: Request):
    service = channel(request)
    service.enabled()
    signatures = request.headers.getlist("x-hub-signature-256")
    raw = (
        await request.body()
    )  # Outer boundary has already bounded raw bytes and total receive time.
    expected = (
        "sha256="
        + hmac.new(
            service.settings.meta_app_secret.get_secret_value().encode(), raw, hashlib.sha256
        ).hexdigest()
    )
    if (
        len(signatures) != 1
        or not re.fullmatch(r"sha256=[0-9a-f]{64}", signatures[0])
        or not hmac.compare_digest(signatures[0], expected)
    ):
        raise APIError(401, "WEBHOOK_SIGNATURE", "Callback signature is invalid.")
    content_types = request.headers.getlist("content-type")
    if len(content_types) != 1 or content_types[0].split(";", 1)[0].lower() != "application/json":
        raise APIError(415, "JSON_REQUIRED", "Send an application/json callback.")
    try:
        payload = json.loads(
            raw,
            object_pairs_hook=unique_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError()),
        )
        pending = [(payload, 0)]
        while pending:
            node, depth = pending.pop()
            if depth > service.settings.max_json_depth:
                raise ValueError
            if isinstance(node, dict):
                pending.extend((value, depth + 1) for value in node.values())
            elif isinstance(node, list):
                pending.extend((value, depth + 1) for value in node)
    except (ValueError, RecursionError, UnicodeError):
        raise APIError(400, "WEBHOOK_INVALID", "Callback JSON is invalid.") from None
    return await run_in_threadpool(service.ingest, payload)


@router.get("/api/v1/workspaces/{workspace_id}/whatsapp", response_model=ChannelResponse)
def status(request: Request, workspace_id: UUID):
    return envelope(request, channel(request).status(authenticated(request), str(workspace_id)))


@router.post(
    "/api/v1/workspaces/{workspace_id}/whatsapp/link-code", response_model=LinkCodeResponse
)
def link_code(request: Request, workspace_id: UUID, payload: LinkContext):
    identity = authenticated(request, mutation=True)
    request_key(request)
    return envelope(
        request, channel(request).code(identity, str(workspace_id), payload.model_dump(mode="json"))
    )


@router.post("/api/v1/workspaces/{workspace_id}/whatsapp/context", response_model=ChannelResponse)
def context(request: Request, workspace_id: UUID, payload: LinkUpdate):
    identity = authenticated(request, mutation=True)
    request_key(request)
    return envelope(
        request,
        channel(request).update(identity, str(workspace_id), payload.model_dump(mode="json")),
    )


@router.post("/api/v1/workspaces/{workspace_id}/whatsapp/unlink", response_model=ChannelResponse)
def unlink(request: Request, workspace_id: UUID, payload: LinkRevoke):
    identity = authenticated(request, mutation=True)
    request_key(request)
    return envelope(
        request,
        channel(request).update(
            identity, str(workspace_id), payload.model_dump(mode="json"), revoke=True
        ),
    )


@router.get("/wa/reports/{token}", include_in_schema=False)
def report(request: Request, token: str):
    content, filename = channel(request).download(token)
    safe_filename = "".join(
        c for c in filename if c not in {'"', "\\", "\r", "\n", "\x00"}
    )
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/api/v1/workspaces/{workspace_id}/whatsapp/supplier-consent-code",
    response_model=ConsentCodeResponse,
)
def supplier_code(request: Request, workspace_id: UUID, payload: SupplierConsentRequest):
    identity = authenticated(request, mutation=True)
    request_key(request)
    return envelope(
        request,
        WhatsAppFollowups(channel(request)).code(
            identity, str(workspace_id), payload.model_dump(mode="json")
        ),
    )


@router.get(
    "/api/v1/workspaces/{workspace_id}/whatsapp/supplier-recipients",
    response_model=SupplierRecipientsResponse,
)
def supplier_recipients(request: Request, workspace_id: UUID):
    return envelope(
        request,
        WhatsAppFollowups(channel(request)).recipients(authenticated(request), str(workspace_id)),
    )


@router.post(
    "/api/v1/workspaces/{workspace_id}/whatsapp/supplier-followups",
    response_model=SupplierSendResponse,
)
def supplier_send(request: Request, workspace_id: UUID, payload: SupplierSendRequest):
    identity = authenticated(request, mutation=True)
    request_key(request)
    return envelope(
        request,
        WhatsAppFollowups(channel(request)).send(
            identity, str(workspace_id), payload.model_dump(mode="json")
        ),
    )
