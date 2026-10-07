"""Browser access routes; local origin checks complement authentication and CSRF."""

import hmac
from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.contracts.access import (
    LoginRequest,
    LogoutResponse,
    RegistrationResponse,
    SessionResponse,
    WorkspaceResponse,
)
from app.errors import APIError
from app.services.access import AccessService, Identity

COOKIE = "gstshield_session"
COOKIE_PATH = "/api/v1"
router = APIRouter(prefix="/api/v1")


def service(request: Request) -> AccessService:
    if not request.app.state.ready:
        raise APIError(503, "NOT_READY", "Backend has not completed startup.", retry_after=1)
    return request.app.state.access


def allowed_origin(request: Request) -> None:
    origins = request.headers.getlist("origin")
    if len(origins) != 1 or origins[0] not in service(request).settings.cors_origins:
        raise APIError(403, "ORIGIN_REQUIRED", "Use the configured website origin.")


def authenticated(request: Request, *, mutation: bool = False) -> Identity:
    cookies = request.headers.getlist("cookie")
    if len(cookies) != 1:
        raise APIError(401, "AUTH_REQUIRED", "Sign-in is required.")
    occurrences = [
        part for part in cookies[0].split(";") if part.strip().split("=", 1)[0] == COOKIE
    ]
    if len(occurrences) != 1:
        raise APIError(401, "AUTH_REQUIRED", "Sign-in is required.")
    if mutation:
        allowed_origin(request)
    identity = service(request).identity(request.cookies.get(COOKIE, ""), mutation=mutation)
    if mutation:
        headers = request.headers.getlist("x-csrf-token")
        if len(headers) != 1 or not hmac.compare_digest(
            headers[0].encode(), identity.csrf_token.encode()
        ):
            raise APIError(403, "CSRF_INVALID", "Refresh the website session and retry.")
    return identity


def envelope(request: Request, data: object) -> dict:
    return {"data": data, "meta": {"request_id": request.state.request_id}}


def session_data(identity: Identity) -> dict:
    return {
        "user_id": identity.user_id,
        "username": identity.username,
        "expires_at": identity.expires_at,
        "csrf_token": identity.csrf_token,
    }


@router.post("/auth/login", response_model=SessionResponse)
def login(request: Request, payload: LoginRequest, response: Response) -> dict:
    allowed_origin(request)
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise APIError(415, "JSON_REQUIRED", "Send an application/json request.")
    token, identity = service(request).login(payload.username, payload.password.get_secret_value())
    response.set_cookie(
        COOKIE,
        token,
        max_age=service(request).settings.session_ttl_seconds,
        httponly=True,
        samesite="strict",
        secure=False,
        path=COOKIE_PATH,
    )
    return envelope(request, session_data(identity))


@router.get("/auth/session", response_model=SessionResponse)
def session(request: Request) -> dict:
    return envelope(request, session_data(authenticated(request)))


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response) -> dict:
    service(request).logout(authenticated(request, mutation=True))
    response.delete_cookie(COOKIE, path=COOKIE_PATH, httponly=True, samesite="strict")
    return envelope(request, {"logged_out": True})


@router.get("/workspaces", response_model=WorkspaceResponse)
def workspaces(request: Request) -> dict:
    return envelope(request, service(request).workspaces(authenticated(request)))


@router.get("/workspaces/{workspace_id}/registrations", response_model=RegistrationResponse)
def registrations(request: Request, workspace_id: UUID) -> dict:
    return envelope(
        request, service(request).registrations(authenticated(request), str(workspace_id))
    )
