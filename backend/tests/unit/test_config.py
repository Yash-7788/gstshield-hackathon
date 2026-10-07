import re
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app import config
from app.config import BACKEND_DIR, ConfigurationError, Settings, load_settings


def test_template_and_loader_cover_exactly_the_same_variables():
    template = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    names = re.findall(r"^([A-Z][A-Z0-9_]*)=", template, re.MULTILINE)
    assert len(names) == len(set(names))
    assert set(names) == {name.upper() for name in Settings.model_fields}
    settings = Settings(_env_file=BACKEND_DIR / ".env.example")
    assert settings.storage_backend == "sqlite"
    assert settings.local_data_dir == (config.BACKEND_DIR / "data").resolve()
    assert settings.match_amount_tolerance == Decimal("0.01")
    assert not settings.whatsapp_enabled


@pytest.mark.parametrize(
    "overrides",
    [
        {"demo_mode": "yes"},
        {"whatsapp_enabled": "1"},
        {"port": 0},
        {"port": 8001},
        {"public_api_url": "https://localhost:8000"},
        {"public_api_url": "http://[::1]:8000"},
        {"port": "8000.0"},
        {"web_concurrency": True},
        {"port": 65536},
        {"host": "0.0.0.0"},
        {"storage_backend": "memory"},
        {"web_concurrency": 2},
        {"max_concurrent_processing_jobs": 2},
        {"max_upload_bytes": 0},
        {"max_upload_bytes": 67108865},
        {"max_xlsx_uncompressed_bytes": 100},
        {"cors_origins": "*"},
        {"cors_origins": "not-json"},
        {"cors_origins": []},
        {"cors_origins": ["http://localhost:3000", "http://localhost:3000"]},
        {"cors_origins": ["https://evil.example"]},
        {"cors_origins": ["http://localhost:3000/path"]},
        {"cors_origins": ["http://localhost:3000?"]},
        {"cors_origins": ["http://user:password@localhost:3000"]},
        {"cors_origins": ["http://localhost:70000"]},
        {"public_web_url": "http://localhost:3001"},
        {"public_api_url": "https://external.example"},
        {"public_api_url": "http://127.0.0.1:8000"},
        {"public_web_url": "https://localhost:3000", "cors_origins": ["https://localhost:3000"]},
        {"max_database_bytes": 100},
        {"max_local_data_bytes": 100},
        {"max_local_backups": 1},
        {"max_local_users": 101},
        {"max_api_body_bytes": 0},
        {"max_api_receive_seconds": 0},
        {"max_api_receive_seconds": 61},
        {"max_api_receive_seconds": True},
        {"max_api_receive_seconds": "1.5"},
        {"session_ttl_seconds": 86401},
        {"local_data_dir": ".."},
        {"local_data_dir": Path("data/../../private")},
        {"fuzzy_suggestion_threshold": "NaN"},
        {"fuzzy_suggestion_threshold": "100.01"},
        {"fuzzy_min_score_gap": "89"},
        {"match_amount_tolerance": "Infinity"},
        {"match_amount_tolerance": "0.001"},
        {"http_read_timeout_seconds": "NaN"},
        {"session_ttl_seconds": -1},
        {"whatsapp_send_budget": -1},
        {"whatsapp_enabled": True},
    ],
)
def test_invalid_configuration_fails_before_startup(overrides):
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_os_environment_overrides_dotenv_and_unknown_os_values_are_ignored(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text("PORT=8001\nDEMO_MODE=false\n", encoding="utf-8")
    monkeypatch.setenv("PORT", "8002")
    monkeypatch.setenv("PUBLIC_API_URL", "http://localhost:8002")
    monkeypatch.setenv("UNRELATED_APPLICATION_SETTING", "not-a-gstshield-setting")
    settings = Settings(_env_file=dotenv)
    assert settings.port == 8002
    assert not settings.demo_mode


def test_unknown_dotenv_name_is_rejected_without_echoing_its_value(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text("TYPO_SECRET=private-do-not-print\n", encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", dotenv)
    with pytest.raises(ConfigurationError) as raised:
        load_settings()
    assert str(raised.value) == "Invalid settings: CONFIGURATION"
    assert "private-do-not-print" not in str(raised.value)


def test_invalid_secret_adjacent_configuration_is_redacted(monkeypatch):
    monkeypatch.setenv("WHATSAPP_ENABLED", "private-do-not-print")
    monkeypatch.setenv("META_ACCESS_TOKEN", "second-private-value")
    with pytest.raises(ConfigurationError) as raised:
        load_settings()
    assert str(raised.value) == "Invalid settings: WHATSAPP_ENABLED"
    assert "private" not in str(raised.value)


def test_malformed_cors_is_safe_to_report(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "private-do-not-print")
    with pytest.raises(ConfigurationError) as raised:
        load_settings()
    assert str(raised.value) == "Invalid settings: CORS_ORIGINS"


def test_complete_provider_config_validates_but_secrets_are_masked():
    settings = Settings(
        whatsapp_enabled=True,
        whatsapp_public_url="https://callback.example.test",
        meta_graph_version="v25.0",  # Syntax fixture, not a supported-version claim.
        meta_phone_number_id="123456",
        meta_waba_id="654321",
        meta_access_token="secret-one",
        meta_app_secret="secret-two",
        meta_verify_token="secret-three",
    )
    assert "secret-one" not in repr(settings)
    assert "secret-two" not in repr(settings)
    assert "secret-three" not in repr(settings)


@pytest.mark.parametrize(
    "text",
    ["PORT=8000\nPORT=8001\n", "PORT\n", 'META_ACCESS_TOKEN="unclosed-private-value\n'],
)
def test_invalid_dotenv_syntax_or_duplicate_keys_fails_safely(tmp_path, monkeypatch, text):
    dotenv = tmp_path / ".env"
    dotenv.write_text(text, encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", dotenv)
    with pytest.raises(ConfigurationError) as raised:
        load_settings()
    assert "private-value" not in str(raised.value)


def test_ipv6_binding_and_advertised_origin_agree():
    settings = Settings(
        host="::1",
        public_api_url="http://[::1]:8000",
        public_web_url="http://[::1]:3000",
        cors_origins=["http://[::1]:3000"],
    )
    assert settings.host == "::1"
