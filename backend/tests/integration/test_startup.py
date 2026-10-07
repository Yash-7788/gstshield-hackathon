"""Real process/socket proof of the supported launcher's behavior."""

import json
import os
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from app.config import BACKEND_DIR, Settings

# Disable the actual presenter's dotenv in this child only. Exercise the same main()
# used by python -m app, without importing their credentials or local custom settings.
LAUNCH = (
    "import os; from pathlib import Path; from app import config; "
    "config.BACKEND_DIR = Path(os.environ['TEST_BACKEND_DIR']); "
    "from app.config import Settings; Settings.model_config['env_file'] = None; "
    "from app.__main__ import main; raise SystemExit(main())"
)


def child_environment():
    env = os.environ.copy()
    for name in list(env):
        if name.lower() in Settings.model_fields:
            del env[name]
    env["PYTHONUNBUFFERED"] = "1"
    return env


def test_real_local_http_startup_and_readiness():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = child_environment()
    env.update(
        PORT=str(port),
        PUBLIC_API_URL=f"http://127.0.0.1:{port}",
        PUBLIC_WEB_URL="http://127.0.0.1:3000",
    )
    process = subprocess.Popen(
        [sys.executable, "-c", LAUNCH],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                with urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=1) as response:
                    body = json.load(response)
                    assert response.status == 200
                    assert body["data"] == {"status": "ready"}
                    assert response.headers["X-Request-ID"] == body["meta"]["request_id"]
                    assert response.headers["Cache-Control"] == "no-store"
                    assert response.headers["Server"] is None
                break
            except URLError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise AssertionError("Local launcher did not reach readiness") from None
                time.sleep(0.05)
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)


def test_invalid_configuration_exits_cleanly_without_logging_private_value():
    env = child_environment()
    env["CORS_ORIGINS"] = "private-config-value"
    result = subprocess.run(
        [sys.executable, "-c", LAUNCH],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    assert result.returncode == 2
    assert result.stderr.strip() == "Invalid settings: CORS_ORIGINS"
    assert "private-config-value" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
