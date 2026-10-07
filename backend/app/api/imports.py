"""Private uploads: authenticate before reading the larger multipart body."""

import asyncio
import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import ValidationError
from python_multipart.exceptions import MultipartParseError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import ClientDisconnect

from app.api.access import authenticated, envelope
from app.contracts.imports import (
    ImportConfirm,
    ImportListResponse,
    ImportResponse,
    JobResponse,
    MappingPatch,
    PreviewResponse,
    UploadMetadata,
)
from app.errors import APIError
from app.security.http import unique_json_object

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}")


def imports(request):
    return request.app.state.imports


def request_key(request):
    keys = request.headers.getlist("idempotency-key")
    try:
        if len(keys) != 1 or str(UUID(keys[0])) != keys[0]:
            raise ValueError
    except ValueError:
        raise APIError(400, "IDEMPOTENCY_KEY_REQUIRED", "Send one UUID Idempotency-Key.") from None
    return keys[0]


async def bounded_upload(request, settings):
    limit = settings.max_upload_bytes + 65536
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (
        lengths and (len(lengths[0]) > 20 or not lengths[0].isascii() or not lengths[0].isdigit())
    ):
        raise APIError(400, "BAD_REQUEST", "Request length is invalid.")
    if lengths and int(lengths[0]) > limit:
        raise APIError(413, "PAYLOAD_TOO_LARGE", "Upload request exceeds the allowed size.")
    body = bytearray()
    try:
        async with asyncio.timeout(settings.max_upload_receive_seconds):
            async for chunk in request.stream():
                if len(body) + len(chunk) > limit:
                    raise APIError(
                        413, "PAYLOAD_TOO_LARGE", "Upload request exceeds the allowed size."
                    )
                body.extend(chunk)
    except ClientDisconnect:
        raise APIError(400, "UPLOAD_DISCONNECTED", "Upload connection was interrupted.") from None
    except TimeoutError:
        raise APIError(
            408, "UPLOAD_TIMEOUT", "Upload did not finish within the allowed time."
        ) from None
    if lengths and len(body) != int(lengths[0]):
        raise APIError(400, "BAD_REQUEST", "Request length is invalid.")

    async def stream():
        yield bytes(body)

    parser = MultiPartParser(
        request.headers, stream(), max_files=1, max_fields=8, max_part_size=65536
    )
    # Keep the single bounded file in memory; never spool source data to shared temp storage.
    parser.spool_max_size = limit + 1
    try:
        return await parser.parse()
    except (MultiPartException, MultipartParseError, ValueError, UnicodeError):
        # Also close buffers on malformed multipart input.
        for file in parser._files_to_close_on_error:
            file.close()
        raise APIError(
            400, "INVALID_MULTIPART", "Send one file with supported import fields."
        ) from None


@router.post(
    "/imports",
    status_code=202,
    response_model=ImportResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": [
                            "file",
                            "kind",
                            "registration_id",
                            "period",
                            "adapter_version",
                        ],
                        "properties": {
                            "file": {"type": "string", "format": "binary"},
                            **{
                                key: {"type": "string"}
                                for key in (
                                    "kind",
                                    "registration_id",
                                    "period",
                                    "adapter_version",
                                    "sheet_name",
                                    "mapping",
                                    "supersedes_import_id",
                                )
                            },
                        },
                    }
                }
            },
        }
    },
)
async def upload(request: Request, workspace_id: UUID):
    identity = await run_in_threadpool(authenticated, request, mutation=True)
    service = imports(request)
    workspace = str(workspace_id)
    await run_in_threadpool(service.authorize, identity, workspace, mutation=True)
    key = request_key(request)
    if (
        len(request.headers.getlist("content-type")) != 1
        or request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "multipart/form-data"
    ):
        raise APIError(415, "MULTIPART_REQUIRED", "Send a multipart/form-data upload.")
    if not service.upload_slot.acquire(blocking=False):
        raise APIError(503, "UPLOAD_BUSY", "An upload is already being received.", retry_after=1)
    form = None
    try:
        form = await bounded_upload(request, service.settings)
        fields = form.multi_items()
        allowed = set(UploadMetadata.model_fields) | {"file"}
        if len({field for field, _ in fields}) != len(fields) or any(
            field not in allowed for field, _ in fields
        ):
            raise APIError(
                422, "UPLOAD_FIELDS_INVALID", "Upload fields are duplicated or unsupported."
            )
        file = form.get("file")
        if not isinstance(file, UploadFile) or any(
            isinstance(value, UploadFile) for field, value in fields if field != "file"
        ):
            raise APIError(422, "UPLOAD_FIELDS_INVALID", "Exactly one file is required.")
        filename = file.filename or ""
        if (
            not filename
            or len(filename) > 120
            or any(ord(c) < 32 or ord(c) == 127 for c in filename)
            or any(c in filename for c in "/\\:")
            or filename in {".", ".."}
        ):
            raise APIError(422, "FILENAME_INVALID", "Use a simple file name without paths.")
        values = {field: value for field, value in fields if field != "file"}
        if "mapping" in values:
            try:
                values["mapping"] = json.loads(
                    values["mapping"], object_pairs_hook=unique_json_object
                )
            except (ValueError, RecursionError):
                raise APIError(
                    422, "MAPPING_INVALID", "Mapping must be a JSON dictionary."
                ) from None
        try:
            metadata = UploadMetadata.model_validate(values).model_dump(mode="json")
        except ValidationError:
            raise APIError(
                422, "UPLOAD_FIELDS_INVALID", "Check import context, adapter and mapping fields."
            ) from None
        extensions = {"csv-v1": ".csv", "xlsx-v1": ".xlsx", "canonical-demo-v1": ".json"}
        if not filename.lower().endswith(extensions[metadata["adapter_version"]]):
            raise APIError(
                415, "FILE_TYPE_INVALID", "File extension must match the selected adapter."
            )
        content = await file.read(service.settings.max_upload_bytes + 1)
        if not content or len(content) > service.settings.max_upload_bytes:
            raise APIError(413, "UPLOAD_SIZE_INVALID", "File is empty or exceeds the allowed size.")
        result = await run_in_threadpool(
            service.upload,
            identity,
            workspace,
            metadata,
            content,
            filename,
            key,
            request.state.request_id,
        )
        return envelope(request, result)
    finally:
        if form is not None:
            await form.close()
        service.upload_slot.release()


@router.get("/imports", response_model=ImportListResponse)
def list_imports(
    request: Request,
    workspace_id: UUID,
    cursor: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    registration_id: UUID | None = None,
    kind: Literal["PURCHASE", "PORTAL_2B"] | None = None,
    period: str | None = Query(default=None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
):
    return envelope(
        request,
        imports(request).list_imports(
            authenticated(request),
            str(workspace_id),
            cursor=str(cursor) if cursor else None,
            limit=limit,
            registration=str(registration_id) if registration_id else None,
            kind=kind,
            period=period,
        ),
    )


@router.get("/imports/{import_id}", response_model=ImportResponse)
def detail(request: Request, workspace_id: UUID, import_id: UUID):
    return envelope(
        request, imports(request).detail(authenticated(request), str(workspace_id), str(import_id))
    )


@router.get("/imports/{import_id}/rows", response_model=PreviewResponse)
def rows(
    request: Request,
    workspace_id: UUID,
    import_id: UUID,
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    state: Literal["ALL", "ACCEPTED", "REJECTED"] = "ALL",
):
    return envelope(
        request,
        imports(request).rows(
            authenticated(request),
            str(workspace_id),
            str(import_id),
            cursor=cursor,
            limit=limit,
            state=state,
        ),
    )


@router.patch("/imports/{import_id}/mapping", status_code=202, response_model=ImportResponse)
def mapping(request: Request, workspace_id: UUID, import_id: UUID, payload: MappingPatch):
    identity = authenticated(request, mutation=True)
    return envelope(
        request,
        imports(request).remap(
            identity,
            str(workspace_id),
            str(import_id),
            payload.model_dump(mode="json"),
            request_key(request),
            request.state.request_id,
        ),
    )


@router.post("/imports/{import_id}/confirm", response_model=ImportResponse)
def confirm(request: Request, workspace_id: UUID, import_id: UUID, payload: ImportConfirm):
    identity = authenticated(request, mutation=True)
    result = imports(request).confirm(
        identity,
        str(workspace_id),
        str(import_id),
        payload.model_dump(mode="json"),
        request_key(request),
        request.state.request_id,
    )
    request.app.state.passports.compare_confirmed_sources(
        identity, str(workspace_id), result["registration_id"], result["period"]
    )
    return envelope(request, result)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def job(request: Request, workspace_id: UUID, job_id: UUID):
    return envelope(
        request, imports(request).job(authenticated(request), str(workspace_id), str(job_id))
    )
