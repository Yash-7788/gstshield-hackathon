"""Direct Meta HTTPS adapter: pinned public destinations, no redirects, bounded bytes/time.

No provider request is retried here. Send ambiguity belongs to the durable outbox.
"""

import base64
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import threading
from contextlib import suppress
from urllib.parse import urlsplit


class ProviderError(Exception):
    def __init__(self, code="PROVIDER_UNAVAILABLE", *, uncertain=False):
        super().__init__(code)
        self.code = code
        self.uncertain = uncertain


class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
            raise ProviderError("PROVIDER_DESTINATION")
        # Connect to the validated address, keeping the real hostname for TLS certificate/SNI.
        self.sock = socket.create_connection(addresses[0][4], timeout=self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class MetaProvider:
    media_hosts = frozenset({"lookaside.fbsbx.com", "lookaside.facebook.com", "graph.facebook.com"})

    def __init__(self, settings):
        self.settings = settings

    def request(self, url, *, method="GET", payload=None, limit=65536):
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except (TypeError, ValueError):
            raise ProviderError("PROVIDER_DESTINATION") from None
        allowed = {"graph.facebook.com"} if payload is not None else self.media_hosts
        if (
            parsed.scheme != "https"
            or parsed.hostname not in allowed
            or parsed.username
            or parsed.password
            or port not in {None, 443}
            or parsed.fragment
            or any(ord(c) < 33 or ord(c) == 127 for c in url)
        ):
            raise ProviderError("PROVIDER_DESTINATION")
        connection = PinnedHTTPS(
            parsed.hostname,
            timeout=float(self.settings.http_connect_timeout_seconds),
            context=ssl.create_default_context(),
        )
        timed_out = threading.Event()

        def expire():
            timed_out.set()
            if connection.sock is not None:
                with suppress(OSError):
                    connection.sock.shutdown(socket.SHUT_RDWR)
            connection.close()

        deadline = float(
            self.settings.http_connect_timeout_seconds
            + self.settings.http_read_timeout_seconds
            + self.settings.http_write_timeout_seconds
        )
        timer = threading.Timer(deadline, expire)
        timer.daemon = True
        timer.start()
        try:
            body = (
                json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
            )
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            connection.connect()
            if timed_out.is_set():
                raise ProviderError("PROVIDER_INTERRUPTED")
            connection.sock.settimeout(float(self.settings.http_write_timeout_seconds))
            connection.request(
                method,
                path,
                body=body,
                headers={
                    "Authorization": "Bearer " + self.settings.meta_access_token.get_secret_value(),
                    "Content-Type": "application/json",
                    "Accept-Encoding": "identity",
                },
            )
            connection.sock.settimeout(float(self.settings.http_read_timeout_seconds))
            response = connection.getresponse()
            if response.status != 200:
                raise ProviderError(
                    "PROVIDER_REJECTED", uncertain=method == "POST" and response.status >= 500
                )
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ProviderError("PROVIDER_ENCODING", uncertain=method == "POST")
            size = response.getheader("Content-Length")
            if size and (not size.isdigit() or int(size) > limit):
                raise ProviderError("PROVIDER_SIZE", uncertain=method == "POST")
            content = bytearray()
            while not timed_out.is_set():
                block = response.read1(min(65536, limit + 1 - len(content)))
                if not block:
                    break
                content.extend(block)
                if len(content) > limit:
                    raise ProviderError("PROVIDER_SIZE", uncertain=method == "POST")
            if timed_out.is_set() or (size and len(content) != int(size)):
                raise ProviderError("PROVIDER_INTERRUPTED", uncertain=method == "POST")
            return bytes(content), response.getheader("Content-Type", "").split(";", 1)[0].lower()
        except ProviderError:
            raise
        except (OSError, ValueError, http.client.HTTPException):
            raise ProviderError("PROVIDER_UNAVAILABLE", uncertain=method == "POST") from None
        finally:
            timer.cancel()
            connection.close()

    def graph(self, resource, *, payload=None):
        content, mime = self.request(
            f"https://graph.facebook.com/{self.settings.meta_graph_version}/{resource}",
            method="POST" if payload is not None else "GET",
            payload=payload,
        )
        try:
            result = json.loads(content)
            if mime != "application/json" or not isinstance(result, dict):
                raise ValueError
            return result
        except (ValueError, RecursionError):
            raise ProviderError("PROVIDER_RESPONSE", uncertain=payload is not None) from None

    def media(self, identifier, expected_mime):
        if not identifier.isdigit() or len(identifier) > 40:
            raise ProviderError("MEDIA_ID")
        metadata = self.graph(identifier)
        size = metadata.get("file_size")
        if type(size) is not int or not 0 < size <= self.settings.max_upload_bytes:
            raise ProviderError("MEDIA_SIZE")
        if metadata.get("mime_type") != expected_mime or not isinstance(metadata.get("url"), str):
            raise ProviderError("MEDIA_TYPE")
        content, mime = self.request(metadata["url"], limit=self.settings.max_upload_bytes)
        if mime != expected_mime or len(content) != size:
            raise ProviderError("MEDIA_TYPE")
        expected = metadata.get("sha256")
        try:
            digest = (
                bytes.fromhex(expected)
                if isinstance(expected, str) and len(expected) == 64
                else base64.b64decode(expected, validate=True)
            )
        except (TypeError, ValueError):
            raise ProviderError("MEDIA_HASH") from None
        if len(digest) != 32 or hashlib.sha256(content).digest() != digest:
            raise ProviderError("MEDIA_HASH")
        return content

    def send(self, phone, body, logical_id):
        result = self.graph(
            self.settings.meta_phone_number_id + "/messages",
            payload={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone,
                "type": "text",
                "text": {"preview_url": False, "body": body},
                "biz_opaque_callback_data": logical_id,
            },
        )
        messages = result.get("messages")
        if not isinstance(messages, list) or len(messages) != 1:
            raise ProviderError("PROVIDER_RESPONSE", uncertain=True)
        identifier = messages[0].get("id") if isinstance(messages[0], dict) else None
        if not isinstance(identifier, str) or not identifier or len(identifier) > 256:
            raise ProviderError("PROVIDER_RESPONSE", uncertain=True)
        return identifier
