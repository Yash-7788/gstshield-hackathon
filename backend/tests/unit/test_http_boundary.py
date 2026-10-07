import asyncio
import json

import pytest

from app.security.http import LocalHTTPBoundary


def scope():
    return {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"host", b"localhost:8000"), (b"origin", b"http://localhost:3000")],
    }


async def receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def test_middleware_failure_before_response_still_has_safe_json_and_cors(caplog):
    async def failing_app(scope, receive, send):
        raise RuntimeError("private-adapter-content")

    messages = []

    async def send(message):
        messages.append(message)

    boundary = LocalHTTPBoundary(failing_app, ["http://localhost:3000"])
    asyncio.run(boundary(scope(), receive, send))
    assert messages[0]["status"] == 500
    headers = dict(messages[0]["headers"])
    assert headers[b"access-control-allow-origin"] == b"http://localhost:3000"
    assert headers[b"x-content-type-options"] == b"nosniff"
    payload = json.loads(messages[1]["body"])
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert "private-adapter-content" not in str(messages)
    assert "private-adapter-content" not in caplog.text


def test_partial_response_error_aborts_without_appending_a_second_response(caplog):
    async def streaming_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"partial", "more_body": True})
        raise RuntimeError("private-stream-content")

    messages = []

    async def send(message):
        messages.append(message)

    boundary = LocalHTTPBoundary(streaming_app, ["http://localhost:3000"])
    with pytest.raises(RuntimeError, match="Response interrupted") as raised:
        asyncio.run(boundary(scope(), receive, send))
    assert len(messages) == 2
    assert raised.value.__suppress_context__
    assert "private-stream-content" not in str(raised.value)
    assert "private-stream-content" not in caplog.text


@pytest.mark.parametrize(
    ("body", "extra", "status", "code"),
    [
        (b'{"count":1}', [(b"content-length", b"1")], 400, "BAD_REQUEST"),
        (b'{"count":1}', [(b"content-length", b"40")], 400, "BAD_REQUEST"),
        (b'{"count":1,"count":2}', [], 422, "VALIDATION_ERROR"),
        (b'{"facts":{"amount":"1","amount":"2"}}', [], 422, "VALIDATION_ERROR"),
        (b'{"name":1,"n\\u0061me":2}', [], 422, "VALIDATION_ERROR"),
        (b'{"count":NaN}', [], 422, "VALIDATION_ERROR"),
        (b'{"count":Infinity}', [], 422, "VALIDATION_ERROR"),
        (b'{"count":-Infinity}', [], 422, "VALIDATION_ERROR"),
        (b'{"count":"private-payload"', [], 422, "VALIDATION_ERROR"),
        (b"\xff", [], 422, "VALIDATION_ERROR"),
        (
            b"{}",
            [(b"content-type", b"text/plain"), (b"content-type", b"application/json")],
            400,
            "BAD_REQUEST",
        ),
    ],
)
def test_ambiguous_or_invalid_body_is_denied_before_downstream(body, extra, status, code, caplog):
    called = []
    messages = []

    async def downstream(scope, receive, send):
        called.append(True)

    async def incoming():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    request = scope() | {"method": "POST", "headers": scope()["headers"] + extra}
    asyncio.run(LocalHTTPBoundary(downstream, ["http://localhost:3000"])(request, incoming, send))
    assert not called
    assert messages[0]["status"] == status
    headers = dict(messages[0]["headers"])
    assert headers[b"access-control-allow-origin"] == b"http://localhost:3000"
    assert headers[b"cache-control"] == b"no-store"
    assert json.loads(messages[1]["body"])["error"]["code"] == code
    assert "private-payload" not in str(messages) + caplog.text


def test_slow_mutation_is_cancelled_with_one_wall_clock_budget():
    messages = []
    cancelled = []

    async def downstream(scope, receive, send):
        raise AssertionError("A stalled body must not reach the route")

    async def incoming():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    async def send(message):
        messages.append(message)

    boundary = LocalHTTPBoundary(
        downstream, ["http://localhost:3000"], receive_timeout_seconds=0.02
    )
    asyncio.run(asyncio.wait_for(boundary(scope() | {"method": "POST"}, incoming, send), 1))
    assert cancelled == [True]
    assert messages[0]["status"] == 408
    assert json.loads(messages[1]["body"])["error"]["code"] == "REQUEST_TIMEOUT"


def test_valid_streamed_json_is_unchanged_and_response_sending_is_outside_receive_deadline():
    body = json.dumps({"name": 'braces { and "quotes"', "amount": "0.10"}).encode()
    chunks = iter([body[:9], body[9:]])
    seen = []

    async def incoming():
        chunk = next(chunks)
        return {"type": "http.request", "body": chunk, "more_body": len(chunk) == 9}

    async def downstream(scope, receive, send):
        seen.append((await receive())["body"])

    async def slow_send(message):
        await asyncio.sleep(0.04)
        seen.append(message)

    boundary = LocalHTTPBoundary(
        downstream, ["http://localhost:3000"], receive_timeout_seconds=0.02
    )
    asyncio.run(boundary(scope() | {"method": "POST"}, incoming, slow_send))
    assert seen == [body]
    # The same deadline must not cancel a denial after response.start has been sent.
    seen.clear()

    async def oversized():
        return {"type": "http.request", "body": b"x" * 11, "more_body": False}

    boundary.max_body_bytes = 10
    asyncio.run(boundary(scope() | {"method": "POST"}, oversized, slow_send))
    assert len(seen) == 2 and seen[0]["status"] == 413


def test_receive_failure_is_redacted_and_disconnect_has_no_business_effect(caplog):
    async def downstream(scope, receive, send):
        raise AssertionError("No completed body")

    async def failure():
        raise RuntimeError("private-receive-secret")

    messages = []

    async def send(message):
        messages.append(message)

    boundary = LocalHTTPBoundary(downstream, ["http://localhost:3000"])
    asyncio.run(boundary(scope() | {"method": "POST"}, failure, send))
    assert messages[0]["status"] == 400
    assert "private-receive-secret" not in str(messages) + caplog.text
    messages.clear()

    async def disconnected():
        return {"type": "http.disconnect"}

    asyncio.run(boundary(scope() | {"method": "POST"}, disconnected, send))
    assert not messages
