import os

import pytest

from app import config
from app.config import Settings


@pytest.fixture(autouse=True)
def isolate_configuration(monkeypatch, tmp_path):
    """Never make tests depend on the presenter's actual .env or OS settings."""
    names = set(Settings.model_fields)
    for name in list(os.environ):
        if name.lower() in names:
            monkeypatch.delenv(name)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    test_backend = tmp_path / "backend"
    test_backend.mkdir()
    monkeypatch.setattr(config, "BACKEND_DIR", test_backend)
    monkeypatch.setenv("TEST_BACKEND_DIR", str(test_backend))
