"""Bounded transport checks against local fakes; no external provider calls."""

import base64
import hashlib
import json

import pytest

from app.adapters import whatsapp
from app.adapters.whatsapp import MetaProvider, PinnedHTTPS, ProviderError
from app.config import Settings


class Response:
    def __init__(self, content=b"ok", *, status=200, headers=None):
        self.content, self.status = content, status
        self.headers = headers or {}

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read1(self, size):
        result, self.content = self.content[:size], self.content[size:]
        return result


class Connection:
    response = None
    calls = []
    error = None

    def __init__(self, *args, **kwargs):
        self.sock = self

    def settimeout(self, value):
        pass

    def connect(self):
        pass

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if self.error:
            raise self.error

    def getresponse(self):
        return self.response

    def close(self):
        pass


@pytest.fixture
def transport(monkeypatch):
    Connection.calls = []
    Connection.error = None
    monkeypatch.setattr(whatsapp, "PinnedHTTPS", Connection)
    return MetaProvider(Settings(meta_graph_version="v25.0", meta_access_token="synthetic-token"))


@pytest.mark.parametrize(
    "url",
    [
        "http://graph.facebook.com/x",
        "https://127.0.0.1/x",
        "https://evil.example/x",
        "https://graph.facebook.com.evil.example/x",
        "https://user@graph.facebook.com/x",
        "https://graph.facebook.com:444/x",
        "https://graph.facebook.com:bad/x",
        "https://[invalid/x",
        "https://graph.facebook.com/x#fragment",
        "https://lookaside.fbsbx.com/\r\nunsafe",
    ],
)
def test_forbidden_destinations_never_open_a_connection(transport, url):
    with pytest.raises(ProviderError, match="PROVIDER_DESTINATION"):
        transport.request(url)
    assert Connection.calls == []


def test_dns_private_resolution_rejected_before_connect(monkeypatch):
    monkeypatch.setattr(
        whatsapp.socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))]
    )
    connection = PinnedHTTPS("graph.facebook.com")
    with pytest.raises(ProviderError, match="PROVIDER_DESTINATION"):
        connection.connect()
    assert connection.sock is None


@pytest.mark.parametrize(
    "response,code",
    [
        (
            Response(b"", status=302, headers={"Location": "http://127.0.0.1/private"}),
            "PROVIDER_REJECTED",
        ),
        (Response(b"abcdef", headers={"Content-Length": "100"}), "PROVIDER_SIZE"),
        (Response(b"abcdef"), "PROVIDER_SIZE"),
        (Response(b"a", headers={"Content-Encoding": "gzip"}), "PROVIDER_ENCODING"),
        (Response(b"ab", headers={"Content-Length": "3"}), "PROVIDER_INTERRUPTED"),
    ],
)
def test_redirects_size_encoding_and_partial_response(transport, response, code):
    Connection.response = response
    with pytest.raises(ProviderError, match=code):
        transport.request("https://graph.facebook.com/test", limit=5)
    assert len(Connection.calls) == 1


def test_ambiguous_send_is_not_retried_and_credentials_stay_in_header(transport):
    Connection.response = Response(b"", status=503)
    with pytest.raises(ProviderError) as raised:
        transport.send("919876543210", "synthetic response", "logical-id")
    assert raised.value.uncertain
    assert len(Connection.calls) == 1
    method, path, args = Connection.calls[0]
    assert method == "POST" and "synthetic-token" not in path
    assert args["headers"]["Authorization"] == "Bearer synthetic-token"
    assert json.loads(args["body"])["biz_opaque_callback_data"] == "logical-id"


def test_media_mime_size_hash_and_provider_path_validation(transport, monkeypatch):
    content = b"invoice_number,amount\nA1,10.00\n"
    metadata = {
        "file_size": len(content),
        "mime_type": "text/csv",
        "sha256": hashlib.sha256(content).hexdigest(),
        "url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?id=123",
    }
    monkeypatch.setattr(transport, "graph", lambda identifier: metadata)
    Connection.response = Response(
        content, headers={"Content-Type": "text/csv", "Content-Length": str(len(content))}
    )
    assert transport.media("123", "text/csv") == content
    metadata["sha256"] = base64.b64encode(hashlib.sha256(content).digest()).decode()
    Connection.response = Response(content, headers={"Content-Type": "text/csv"})
    assert transport.media("123", "text/csv") == content
    metadata["url"] = "https://evil.example/private"
    with pytest.raises(ProviderError, match="PROVIDER_DESTINATION"):
        transport.media("123", "text/csv")
    metadata["url"] = "https://lookaside.fbsbx.com/file"
    metadata["sha256"] = "0" * 64
    Connection.response = Response(content, headers={"Content-Type": "text/csv"})
    with pytest.raises(ProviderError, match="MEDIA_HASH"):
        transport.media("123", "text/csv")
