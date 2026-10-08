"""Local HTTP boundary. CORS is not authentication for future private routes."""

import asyncio
import json
import logging
import re
from urllib.parse import urlsplit
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.contracts.http import error_payload

logger = logging.getLogger("gstshield")


def unique_json_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate JSON field")
    return result


class LocalHTTPBoundary:
    def __init__(
        self,
        app: ASGIApp,
        origins: list[str],
        *,
        testing: bool = False,
        max_body_bytes: int = 65536,
        receive_timeout_seconds: float = 20,
        channel_origin: str = "",
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.receive_timeout_seconds = receive_timeout_seconds
        self.origins = frozenset(origins)
        self.channel_host = urlsplit(channel_origin).hostname if channel_origin else None
        self.allowed_hosts = {"localhost", "127.0.0.1", "::1"}
        if testing:
            self.allowed_hosts.add("testserver")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        response_started = False
        response_complete = False

        async def send_with_headers(message: Message) -> None:
            nonlocal response_started, response_complete
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                protected = {
                    b"x-request-id": request_id.encode("ascii"),
                    b"cache-control": b"no-store",
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"no-referrer",
                    b"content-security-policy": b"frame-ancestors 'none'",
                }
                headers = [(key, value) for key, value in headers if key.lower() not in protected]
                headers.extend(protected.items())
                message = {**message, "headers": headers}
            await send(message)
            if message["type"] == "http.response.start":
                response_started = True
            elif message["type"] == "http.response.body" and not message.get("more_body", False):
                response_complete = True

        headers = scope.get("headers", [])
        hosts = [value.decode("latin-1") for key, value in headers if key.lower() == b"host"]
        origins = [value.decode("latin-1") for key, value in headers if key.lower() == b"origin"]
        try:
            host = urlsplit("http://" + hosts[0]) if len(hosts) == 1 else None
            valid_host = (
                host is not None
                and (
                    host.hostname in self.allowed_hosts
                    or (
                        host.hostname == self.channel_host
                        and (
                            scope.get("path") == "/webhooks/whatsapp"
                            or re.fullmatch(r"/wa/reports/[A-Za-z0-9_-]{43}", scope.get("path", ""))
                        )
                    )
                )
                and host.username is None
                and host.password is None
                and not host.path
                and not host.query
                and not host.fragment
                and not any(character.isspace() for character in hosts[0])
                and not hosts[0].endswith((":", "?", "#"))
                and (host.port is None or 1 <= host.port <= 65535)
            )
        except ValueError:
            valid_host = False
        if not valid_host:
            response = JSONResponse(
                error_payload(request_id, "INVALID_HOST", "Use the local backend address."),
                status_code=400,
            )
            await response(scope, receive, send_with_headers)
            return
        if origins and (len(origins) != 1 or origins[0] not in self.origins):
            response = JSONResponse(
                error_payload(request_id, "ORIGIN_NOT_ALLOWED", "Website origin is not allowed."),
                status_code=403,
            )
            await response(scope, receive, send_with_headers)
            return
        private_upload = scope["method"] == "POST" and re.fullmatch(
            r"/api/v1/workspaces/[0-9a-fA-F-]{36}/(?:imports|passports/documents|passports/[0-9a-fA-F-]{36}/evidence-documents)",
            scope.get("path", ""),
        )
        # Upload route authenticates before receiving its separately bounded body.
        if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"} and not private_upload:
            lengths = [value for key, value in headers if key.lower() == b"content-length"]
            invalid_length = len(lengths) > 1 or bool(
                lengths and (len(lengths[0]) > 20 or not lengths[0].isdigit())
            )
            too_large = bool(
                lengths and not invalid_length and int(lengths[0]) > self.max_body_bytes
            )

            async def reject(status, code, message):
                response = JSONResponse(
                    error_payload(request_id, code, message),
                    status_code=status,
                    headers={
                        "Access-Control-Allow-Origin": origins[0],
                        "Access-Control-Allow-Credentials": "true",
                        "Vary": "Origin",
                    }
                    if origins
                    else None,
                )
                await response(scope, receive, send_with_headers)

            if invalid_length or too_large:
                await reject(
                    400 if invalid_length else 413,
                    "BAD_REQUEST" if invalid_length else "PAYLOAD_TOO_LARGE",
                    "Request length is invalid."
                    if invalid_length
                    else "Request exceeds the allowed size.",
                )
                return
            body = bytearray()
            try:
                # One wall-clock budget covers every chunk, including a peer that stalls.
                async with asyncio.timeout(self.receive_timeout_seconds):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        chunk = message.get("body", b"")
                        if len(body) + len(chunk) > self.max_body_bytes:
                            too_large = True
                            break
                        body.extend(chunk)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                await reject(
                    408, "REQUEST_TIMEOUT", "Request body did not finish within the allowed time."
                )
                return
            except Exception as exc:
                logger.error(
                    "Request body failure request_id=%s exception_type=%s",
                    request_id,
                    type(exc).__name__,
                )
                await reject(400, "BAD_REQUEST", "Request body could not be received.")
                return
            if too_large:
                await reject(413, "PAYLOAD_TOO_LARGE", "Request exceeds the allowed size.")
                return
            if lengths and len(body) != int(lengths[0]):
                await reject(400, "BAD_REQUEST", "Request length is invalid.")
                return
            content_types = [
                value.decode("latin-1") for key, value in headers if key.lower() == b"content-type"
            ]
            if len(content_types) > 1:
                await reject(400, "BAD_REQUEST", "Request content type is ambiguous.")
                return
            media_type = (
                content_types[0].split(";", 1)[0].strip().lower()
                if content_types
                else "application/json"
            )
            if (
                scope.get("path") != "/webhooks/whatsapp"
                and body
                and (
                    media_type == "application/json"
                    or (media_type.startswith("application/") and media_type.endswith("+json"))
                )
            ):
                try:
                    # FastAPI otherwise silently accepts repeated keys and non-standard constants.
                    json.loads(
                        body,
                        object_pairs_hook=unique_json_object,
                        parse_constant=lambda value: (_ for _ in ()).throw(
                            ValueError("Invalid JSON constant")
                        ),
                    )
                except (ValueError, UnicodeError, RecursionError):
                    await reject(422, "VALIDATION_ERROR", "Request JSON is invalid or ambiguous.")
                    return
            original_receive = receive
            delivered = False

            async def bounded_receive() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await original_receive()

            receive = bounded_receive
        try:
            await self.app(scope, receive, send_with_headers)
        except Exception as exc:
            if response_complete:
                # Starlette re-raises after its sanitized 500 response. Suppress that
                # completed error so Uvicorn cannot log the private exception text.
                return
            logger.error(
                "HTTP boundary failure request_id=%s exception_type=%s",
                request_id,
                type(exc).__name__,
            )
            if response_started:
                # A partial streamed response must fail, rather than append another response.
                raise RuntimeError(f"Response interrupted; request_id={request_id}") from None
            response = JSONResponse(
                error_payload(request_id, "INTERNAL_ERROR", "An unexpected error occurred."),
                status_code=500,
                headers={
                    "Access-Control-Allow-Origin": origins[0],
                    "Access-Control-Allow-Credentials": "true",
                    "Vary": "Origin",
                }
                if origins
                else None,
            )
            await response(scope, receive, send_with_headers)
