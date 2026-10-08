"""Local HTTP foundation with private SQLite accounts and browser sessions."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from app.api.access import router
from app.api.actions import router as action_router
from app.api.command_center import router as command_center_router
from app.api.imports import router as import_router
from app.api.passports import router as passport_router
from app.api.product import router as product_router
from app.api.runs import router as run_router
from app.api.whatsapp import router as whatsapp_router
from app.api.workflows import router as workflow_router
from app.config import Settings, load_settings
from app.contracts.http import ErrorResponse, HealthResponse, error_payload
from app.errors import APIError, StorageError
from app.jobs.automation import ActionMonitor
from app.jobs.imports import ImportDispatcher
from app.jobs.whatsapp import WhatsAppWorker
from app.security.http import LocalHTTPBoundary
from app.services.access import AccessService
from app.services.actions import ActionService
from app.services.business import BusinessService
from app.services.cases import CaseService
from app.services.imports import ImportService
from app.services.passport_channels import PassportChannels
from app.services.passports import PassportService
from app.services.processes import ProcessService
from app.services.product_guidance import ProductGuidance
from app.services.proposals import ProposalService
from app.services.reports import ReportService
from app.services.runs import RunService
from app.services.whatsapp import WhatsAppService
from app.storage.local import LocalStore

logger = logging.getLogger("gstshield")


def create_app(settings: Settings | None = None) -> ASGIApp:
    settings = settings if settings is not None else load_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        store = LocalStore(settings)
        dispatcher = None
        monitor = None
        channel_worker = None
        try:
            store.acquire()
            store.initialize()
            application.state.store = store
            application.state.access = AccessService(store)
            application.state.imports = ImportService(application.state.access)
            application.state.runs = RunService(application.state.imports)
            application.state.cases = CaseService(application.state.runs)
            application.state.passports = PassportService(application.state.runs)
            application.state.passports.cases = application.state.cases
            application.state.business = BusinessService(application.state.passports)
            application.state.product_guidance = ProductGuidance(application.state.business)
            application.state.processes = ProcessService(application.state.product_guidance)
            application.state.actions = ActionService(
                application.state.runs, application.state.cases
            )
            application.state.proposals = ProposalService(
                application.state.runs, application.state.cases
            )
            application.state.reports = ReportService(
                application.state.runs, application.state.cases, application.state.proposals
            )
            dispatcher = ImportDispatcher(
                application.state.imports, application.state.runs, application.state.reports
            )
            application.state.reports.actions = application.state.actions
            dispatcher.start()
            application.state.dispatcher = dispatcher
            monitor = ActionMonitor(
                application.state.actions, application.state.passports, application.state.processes
            )
            application.state.action_monitor = monitor
            application.state.whatsapp = WhatsAppService(
                application.state.access,
                application.state.imports,
                application.state.runs,
                application.state.reports,
                application.state.actions,
            )
            invoice_channel = PassportChannels(
                application.state.passports, application.state.whatsapp
            )
            application.state.passports.channel = invoice_channel
            application.state.whatsapp.passport_channel = invoice_channel
            monitor.start()
            if settings.whatsapp_enabled:
                channel_worker = WhatsAppWorker(application.state.whatsapp)
                channel_worker.start()
            application.state.channel_worker = channel_worker
            application.state.ready = True
            yield
        finally:
            application.state.ready = False
            try:
                if channel_worker is not None:
                    channel_worker.close()
            finally:
                try:
                    if monitor is not None:
                        monitor.close()
                finally:
                    try:
                        if dispatcher is not None:
                            dispatcher.close()
                    finally:
                        # Never release the process lock while a worker can still touch storage.
                        workers = (channel_worker, monitor, dispatcher)
                        if all(
                            worker is None or not worker.thread.is_alive() for worker in workers
                        ):
                            store.close()

    application = FastAPI(
        title="GSTShield Local API",
        version="0.0.1",
        debug=False,
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env in {"local", "test"} else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_env in {"local", "test"} else None,
    )
    application.state.ready = False
    application.include_router(router)
    application.include_router(import_router)
    application.include_router(run_router)
    application.include_router(passport_router)
    application.include_router(command_center_router)
    application.include_router(product_router)
    application.include_router(workflow_router)
    application.include_router(action_router)
    application.include_router(whatsapp_router)

    @application.exception_handler(APIError)
    async def application_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            error_payload(
                request.state.request_id, exc.code, exc.message, retryable=exc.status in {429, 503}
            ),
            status_code=exc.status,
            headers={"Retry-After": str(exc.retry_after)} if exc.retry_after else None,
        )

    @application.exception_handler(StorageError)
    async def storage_error(request: Request, exc: StorageError) -> JSONResponse:
        categories = {
            "Private storage is unavailable.": "CAPACITY_SCAN",
            "Private storage directory cannot be inspected.": "CAPACITY_DIRECTORY",
            "Private storage quota reached; no changes were saved.": "QUOTA",
            "Insufficient free disk space; no changes were saved.": "DISK_RESERVE",
            "Private storage is not available.": "STORE_CLOSED",
            "Private storage path is outside its allowed directory.": "PATH_SCOPE",
            "Private storage must use ordinary local files and directories.": "PATH_TYPE",
            "Private storage cannot contain linked paths.": "PATH_LINK",
            "Private storage file count limit reached.": "FILE_LIMIT",
            "Private storage operation failed; retry after checking local storage.": "TRANSACTION",
        }
        cause = exc.__context__
        logger.warning(
            "Storage request failure request_id=%s category=%s cause_type=%s code=%s",
            request.state.request_id,
            categories.get(str(exc), "INTERNAL"),
            type(cause).__name__,
            getattr(cause, "sqlite_errorcode", getattr(cause, "errno", None)),
        )
        return JSONResponse(
            error_payload(
                request.state.request_id,
                "STORAGE_UNAVAILABLE",
                "Private local storage is unavailable; contact the local operator.",
                retryable=True,
            ),
            status_code=503,
            headers={"Retry-After": "2"},
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        messages = {
            400: ("BAD_REQUEST", "Request could not be accepted."),
            401: ("UNAUTHORIZED", "Authentication is required."),
            403: ("FORBIDDEN", "Request is not permitted."),
            404: ("NOT_FOUND", "Resource was not found."),
            405: ("METHOD_NOT_ALLOWED", "Method is not allowed."),
            409: ("CONFLICT", "Request conflicts with current state."),
            413: ("PAYLOAD_TOO_LARGE", "Request exceeds the allowed size."),
            429: ("RATE_LIMITED", "Request limit reached."),
            503: ("UNAVAILABLE", "Service is temporarily unavailable."),
        }
        code, message = messages.get(
            exc.status_code, ("HTTP_ERROR", "Request could not be accepted.")
        )
        # Do not echo arbitrary exception detail/headers containing private input.
        headers = {}
        if exc.status_code == 405 and exc.headers and "Allow" in exc.headers:
            headers["Allow"] = exc.headers["Allow"]
        return JSONResponse(
            error_payload(
                request.state.request_id,
                code,
                message,
                retryable=exc.status_code in {429, 503},
            ),
            status_code=exc.status_code,
            headers=headers,
        )

    @application.exception_handler(RecursionError)
    async def nested_json_error(request: Request, exc: RecursionError) -> JSONResponse:
        return JSONResponse(
            error_payload(
                request.state.request_id, "VALIDATION_ERROR", "Request nesting is excessive."
            ),
            status_code=422,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"])[:128],
                "row": None,
                "reason": "Invalid value.",
            }
            for error in exc.errors()[:20]
        ]
        return JSONResponse(
            error_payload(
                request.state.request_id,
                "VALIDATION_ERROR",
                "Request contains invalid fields.",
                details=details,
            ),
            status_code=422,
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Never log str(exc), body, authorization header or full request URL.
        logger.error(
            "Unhandled request error request_id=%s exception_type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        return JSONResponse(
            error_payload(
                request.state.request_id,
                "INTERNAL_ERROR",
                "An unexpected error occurred.",
                retryable=False,
            ),
            status_code=500,
        )

    @application.get("/health/live", response_model=HealthResponse)
    async def live(request: Request) -> dict:
        return {"data": {"status": "ok"}, "meta": {"request_id": request.state.request_id}}

    @application.get(
        "/health/ready",
        response_model=HealthResponse,
        responses={503: {"model": ErrorResponse}},
    )
    def ready(request: Request) -> dict | JSONResponse:
        if (
            not application.state.ready
            or not application.state.store.ready()
            or not application.state.dispatcher.thread.is_alive()
            or not application.state.action_monitor.thread.is_alive()
            or (
                application.state.channel_worker is not None
                and not application.state.channel_worker.thread.is_alive()
            )
        ):
            return JSONResponse(
                error_payload(
                    request.state.request_id,
                    "NOT_READY",
                    "Backend has not completed startup.",
                    retryable=True,
                ),
                status_code=503,
            )
        return {"data": {"status": "ready"}, "meta": {"request_id": request.state.request_id}}

    # Outer CORS also covers FastAPI's 500 handler, as required by Starlette.
    return LocalHTTPBoundary(
        CORSMiddleware(
            application,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
            expose_headers=[
                "X-Request-ID",
                "Retry-After",
                "X-GSTShield-Historical",
                "Content-Disposition",
            ],
            max_age=600,
        ),
        settings.cors_origins,
        testing=settings.app_env == "test",
        max_body_bytes=settings.max_api_body_bytes,
        receive_timeout_seconds=settings.max_api_receive_seconds,
        channel_origin=settings.whatsapp_public_url if settings.whatsapp_enabled else "",
    )
