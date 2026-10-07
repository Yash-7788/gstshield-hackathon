"""Actual stream bounds, child cancellation and resource baselines."""

import asyncio
import subprocess
import sys
import time
from uuid import uuid4

import psutil
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.imports import bounded_upload
from app.config import Settings
from app.errors import APIError
from app.jobs.imports import ImportDispatcher
from app.main import create_app
from app.services.access import AccessService
from app.services.imports import ImportService
from app.storage.local import LocalStore
from tests.integration.test_imports import account as account
from tests.integration.test_imports import completed, signed_in, upload
from tests.unit.test_import_parsers import ROW, csv_content, xlsx_content


def request_for(chunks, headers=()):
    iterator = iter(chunks)

    async def receive():
        return next(iterator)

    return Request(
        {"type": "http", "method": "POST", "path": "/", "headers": list(headers)}, receive
    )


def test_upload_counts_actual_streamed_bytes_and_length_mismatch():
    request = request_for(
        [
            {"type": "http.request", "body": b"a" * 40000, "more_body": True},
            {"type": "http.request", "body": b"a" * 30000, "more_body": False},
        ]
    )
    with pytest.raises(APIError) as error:
        asyncio.run(bounded_upload(request, Settings(max_upload_bytes=100)))
    assert error.value.status == 413
    request = request_for(
        [{"type": "http.request", "body": b"abc", "more_body": False}], [(b"content-length", b"5")]
    )
    with pytest.raises(APIError) as error:
        asyncio.run(bounded_upload(request, Settings()))
    assert error.value.status == 400


def test_upload_duplicate_length_and_deadline_before_parsing():
    request = request_for([], [(b"content-length", b"1"), (b"content-length", b"1")])
    with pytest.raises(APIError) as error:
        asyncio.run(bounded_upload(request, Settings()))
    assert error.value.status == 400

    async def stalled():
        await asyncio.sleep(30)
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []}, stalled)
    started = time.monotonic()
    with pytest.raises(APIError) as error:
        asyncio.run(bounded_upload(request, Settings(max_upload_receive_seconds=1)))
    assert error.value.status == 408 and time.monotonic() - started < 3


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"processing_timeout_seconds": 1}, "PROCESSING_TIMEOUT"),
        ({"max_parser_rss_bytes": 1}, "PARSER_MEMORY_LIMIT"),
    ],
)
def test_running_child_is_really_killed(monkeypatch, overrides, expected):
    store = LocalStore(Settings(**overrides))
    store.acquire()
    store.initialize()
    dispatcher = ImportDispatcher(ImportService(AccessService(store)))
    original = subprocess.Popen
    children = []
    observed = set()
    original_memory = psutil.Process.memory_info

    def record_memory(process):
        observed.add(process.pid)
        return original_memory(process)

    monkeypatch.setattr(psutil.Process, "memory_info", record_memory)

    def launch(*args, **kwargs):
        child = original(
            [sys.executable, "-c", "import sys,time; sys.stdin.buffer.read(); time.sleep(30)"],
            **kwargs,
        )
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", launch)
    row = {
        "file_id": str(uuid4()),
        "workspace_id": str(uuid4()),
        "mapping_json": "{}",
        "adapter_version": "csv-v1",
        "kind": "PURCHASE",
        "period": "2024-05",
        "sheet_name": None,
        "recipient_gstin": ROW["recipient_gstin"],
    }
    try:
        outcome = dispatcher.parse(row)
        assert outcome["error_code"] == expected
        assert children[0].poll() is not None
        assert not psutil.pid_exists(children[0].pid)
        assert observed and all(not psutil.pid_exists(pid) for pid in observed)
        assert list(store.root.glob("parser-*.json")) == []
    finally:
        store.close()


def test_queue_bound_and_interrupted_job_recovery(account):
    settings, _, workspace, registration = account
    app = create_app(settings)
    with TestClient(app) as client:
        headers = signed_in(client)
        state = app.app.app.state
        state.dispatcher.close()
        state.imports.settings = settings.model_copy(update={"max_queued_jobs_per_workspace": 1})
        response = upload(client, workspace, registration, headers)
        assert response.status_code == 202
        identifier = response.json()["data"]["id"]
        different = csv_content([{**ROW, "voucher_id": "V2", "invoice_number": "I2"}])
        assert (
            upload(client, workspace, registration, headers, content=different).json()["error"][
                "code"
            ]
            == "QUEUE_FULL"
        )
        with state.store.transaction() as connection:
            connection.execute("UPDATE jobs SET state='RUNNING' WHERE import_id=?", (identifier,))
            connection.execute("UPDATE imports SET state='PARSING' WHERE id=?", (identifier,))
        state.imports.settings = settings
        queued = upload(client, workspace, registration, headers, content=different)
        assert queued.status_code == 202
        queued_id = queued.json()["data"]["id"]
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        data = completed(client, workspace, identifier)
        assert data["state"] == "FAILED" and data["errors"][0]["reason"] == "PROCESSING_INTERRUPTED"
        job = client.get(f"/api/v1/workspaces/{workspace}/jobs/{data['job_id']}").json()["data"]
        assert job["state"] == "FAILED" and job["error_code"] == "PROCESSING_INTERRUPTED"
        assert completed(client, workspace, queued_id)["state"] == "AWAITING_CONFIRMATION"
        retry = client.patch(
            f"/api/v1/workspaces/{workspace}/imports/{identifier}/mapping",
            json={"expected_version": data["version"], "mapping": {}},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert retry.status_code == 202, retry.text
        retry_id = retry.json()["data"]["id"]
        assert retry_id != identifier
        recovered = completed(client, workspace, retry_id)
        assert recovered["state"] == "AWAITING_CONFIRMATION" and recovered["accepted_rows"] == 1
        assert recovered["derived_from_import_id"] == identifier


def test_import_baseline_100_and_2000_rows_csv_xlsx(account):
    settings, _, workspace, registration = account
    app = create_app(settings)
    with TestClient(app) as client:
        headers = signed_in(client)
        measurements = []
        for count in (100, 2000):
            rows = [
                {**ROW, "voucher_id": f"V{index}", "invoice_number": f"I{index}"}
                for index in range(count)
            ]
            for adapter, content in (
                ("csv-v1", csv_content(rows)),
                ("xlsx-v1", xlsx_content(rows)),
            ):
                app.app.app.state.dispatcher.peak_rss = 0
                start = time.monotonic()
                response = upload(
                    client, workspace, registration, headers, adapter=adapter, content=content
                )
                assert response.status_code == 202, response.text
                # Health remains reachable while the disposable parser performs the heavy work.
                assert client.get("/health/live").status_code == 200
                data = completed(client, workspace, response.json()["data"]["id"])
                elapsed = time.monotonic() - start
                assert (
                    data["state"] == "AWAITING_CONFIRMATION" and data["accepted_rows"] == count
                ), data
                rss = app.app.app.state.dispatcher.peak_rss
                assert 0 < rss < settings.max_parser_rss_bytes
                measurements.append(
                    {
                        "adapter": adapter,
                        "rows": count,
                        "bytes": len(content),
                        "seconds": round(elapsed, 3),
                        "peak_child_rss": rss,
                    }
                )
        print("\nIMPORT_BASELINE", measurements)


def test_unauthorized_upload_rejected_without_receiving_body():
    app = create_app(Settings(app_env="test"))
    messages = []

    async def receive():
        raise AssertionError("Unauthorized upload body must not be read")

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": f"/api/v1/workspaces/{uuid4()}/imports",
        "root_path": "",
        "query_string": b"",
        "scheme": "http",
        "http_version": "1.1",
        "server": ("localhost", 8000),
        "client": ("127.0.0.1", 12345),
        "headers": [
            (b"host", b"localhost:8000"),
            (b"content-type", b"multipart/form-data; boundary=x"),
        ],
    }
    with TestClient(app):
        asyncio.run(app(scope, receive, send))
    assert messages[0]["status"] == 401
