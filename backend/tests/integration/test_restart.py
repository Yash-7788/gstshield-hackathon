"""Phase 1 + 2 connectivity across actual backend processes and offline maintenance."""

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager

import httpx2

from app.config import BACKEND_DIR, Settings
from app.services.access import AccessService
from app.storage.local import LocalStore

PRELUDE = (
    "import os; from pathlib import Path; from app import config; "
    "config.BACKEND_DIR=Path(os.environ['TEST_BACKEND_DIR']); "
    "from app.config import Settings; Settings.model_config['env_file']=None; "
)


@contextmanager
def running_backend(port, environment):
    process = subprocess.Popen(
        [sys.executable, "-c", PRELUDE + "from app.__main__ import main; raise SystemExit(main())"],
        cwd=BACKEND_DIR,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with httpx2.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=15, trust_env=False
        ) as client:
            deadline = time.monotonic() + 10
            while True:
                try:
                    if client.get("/health/ready").status_code == 200:
                        break
                except httpx2.TransportError:
                    pass
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise AssertionError("Real backend did not become ready")
                time.sleep(0.05)
            yield client
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)


def maintenance(environment, *arguments):
    return subprocess.run(
        [
            sys.executable,
            "-c",
            PRELUDE + "from app.manage import main; raise SystemExit(main())",
            *arguments,
        ],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )


def test_real_restart_keeps_private_records_and_session_then_logout_revokes():
    settings = Settings()
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    try:
        _, workspace = access.provision("alice", "synthetic-passphrase-only", "Persisted workspace")
        registration = access.add_registration(
            workspace, "27ABCDE1234F1Z5", "Persisted registration"
        )
    finally:
        store.close()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = os.environ.copy()
    for name in list(environment):
        if name.lower() in Settings.model_fields:
            del environment[name]
    environment.update(
        PORT=str(port),
        PUBLIC_API_URL=f"http://127.0.0.1:{port}",
        PUBLIC_WEB_URL="http://127.0.0.1:3000",
        PYTHONUNBUFFERED="1",
    )
    origin = "http://127.0.0.1:3000"
    with running_backend(port, environment) as client:
        assert client.get("/health/live").status_code == 200
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "synthetic-passphrase-only"},
            headers={"Origin": origin},
        )
        assert response.status_code == 200
        csrf = response.json()["data"]["csrf_token"]
        token = client.cookies.get("gstshield_session")
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/registrations").json()["data"][0]["id"]
            == registration
        )
        locked = maintenance(environment, "backup")
        assert locked.returncode == 2 and "Cannot lock" in locked.stderr
    backup = maintenance(environment, "backup")
    assert backup.returncode == 0 and backup.stdout.startswith("Backup ID: ")
    identifier = backup.stdout.strip().removeprefix("Backup ID: ")
    with running_backend(port, environment) as client:
        client.cookies.set("gstshield_session", token, path="/api/v1")
        assert client.get("/api/v1/workspaces").json()["data"][0]["id"] == workspace
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/registrations").json()["data"][0]["id"]
            == registration
        )
        assert (
            client.post(
                "/api/v1/auth/logout", headers={"Origin": origin, "X-CSRF-Token": csrf}
            ).status_code
            == 200
        )
        assert client.get("/api/v1/workspaces").status_code == 401
    restored = maintenance(environment, "restore", "--backup-id", identifier)
    assert restored.returncode == 0 and "accounts are disabled" in restored.stdout
    with running_backend(port, environment) as client:
        client.cookies.set("gstshield_session", token, path="/api/v1")
        assert client.get("/api/v1/auth/session").status_code == 401
        assert client.get("/health/ready").status_code == 200
