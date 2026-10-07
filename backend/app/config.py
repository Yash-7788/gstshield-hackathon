"""Validated local configuration. Never render raw validation errors or settings."""

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from dotenv.parser import parse_stream
from pydantic import (
    BeforeValidator,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError

BACKEND_DIR = Path(__file__).resolve().parents[1]


def parse_integer(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    raise ValueError("Use an integer")


PositiveInt = Annotated[int, BeforeValidator(parse_integer), Field(gt=0)]
SingleWorker = Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=1)]
PositiveSeconds = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Score = Annotated[Decimal, Field(ge=0, le=100, allow_inf_nan=False)]


def validate_origin(value: str) -> str:
    """An origin, not a URL with credentials, path, query or fragments."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("Expected an exact HTTP(S) origin") from None
    if (
        value != value.strip()
        or any(character.isspace() for character in value)
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or "*" in value
        or "\\" in value
        or (port is not None and not 1 <= port <= 65535)
        or parsed.netloc.endswith(":")
        or value.endswith(("?", "#"))
    ):
        raise ValueError("Expected an exact HTTP(S) origin")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    app_env: Literal["local", "demo", "test"] = "local"
    demo_mode: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    # Loopback only until a separate LAN/remote access phase is explicitly selected.
    host: Literal["127.0.0.1", "::1"] = "127.0.0.1"
    port: Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=65535)] = 8000
    public_web_url: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"
    cors_origins: Annotated[list[str], NoDecode, Field(min_length=1, max_length=10)] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = Field(
        default="gemini-3.1-flash-lite", pattern=r"^gemini-[a-zA-Z0-9.-]{1,80}$"
    )
    gemini_timeout_seconds: int = Field(default=20, ge=5, le=25)
    max_passports_per_workspace: int = Field(default=100, ge=1, le=500)

    storage_backend: Literal["sqlite"] = "sqlite"
    local_data_dir: Path = Path("data")
    max_database_bytes: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=1048576, le=1073741824)
    ] = 67108864
    max_local_data_bytes: PositiveInt = 268435456
    min_free_disk_bytes: PositiveInt = 16777216
    max_local_backups: Annotated[int, BeforeValidator(parse_integer), Field(ge=2, le=10)] = 3
    max_local_users: Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=100)] = 20
    max_local_workspaces: Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=100)] = 20
    max_registrations_per_workspace: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=1, le=100)
    ] = 20
    max_api_body_bytes: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=1024, le=1048576)
    ] = 65536
    max_api_receive_seconds: Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=60)] = 20
    web_concurrency: SingleWorker = 1
    session_ttl_seconds: PositiveInt = 1800
    memory_state_max_bytes: PositiveInt = 67108864
    max_active_demo_sessions: PositiveInt = 20
    max_concurrent_processing_jobs: SingleWorker = 1
    max_queued_jobs_per_workspace: PositiveInt = 5
    max_imports_per_workspace: PositiveInt = 20
    max_runs_per_workspace: PositiveInt = 20
    max_cases_per_workspace: Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=200)] = (
        100
    )
    max_case_events: Annotated[int, BeforeValidator(parse_integer), Field(ge=5, le=200)] = 100
    max_actions_per_workspace: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=1, le=10000)
    ] = 3000
    max_action_events: Annotated[int, BeforeValidator(parse_integer), Field(ge=5, le=200)] = 100
    automation_interval_seconds: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=1, le=60)
    ] = 5
    automation_source_batch: Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=20)] = 8
    automation_due_batch: Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=200)] = 50
    max_proposals_per_workspace: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=1, le=100)
    ] = 20
    max_artifacts_per_workspace: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=1, le=100)
    ] = 40
    max_artifact_bytes: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=1024, le=5242880)
    ] = 5242880
    max_report_snapshot_bytes: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=1024, le=8388608)
    ] = 8388608
    artifact_ttl_seconds: Annotated[
        int, BeforeValidator(parse_integer), Field(ge=60, le=2592000)
    ] = 604800
    max_report_rows: Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=200)] = 200
    max_report_pages: Annotated[int, BeforeValidator(parse_integer), Field(ge=1, le=100)] = 100
    max_match_pairs: PositiveInt = 4000000
    max_match_candidates: PositiveInt = 10000
    max_parsed_import_bytes: PositiveInt = 16777216
    max_parser_rss_bytes: PositiveInt = 268435456
    max_upload_receive_seconds: PositiveInt = 20

    max_upload_bytes: PositiveInt = 5242880
    max_import_rows: PositiveInt = 2000
    max_import_columns: PositiveInt = 50
    max_cell_characters: PositiveInt = 10000
    max_json_depth: PositiveInt = 20
    max_xlsx_uncompressed_bytes: PositiveInt = 52428800
    max_xlsx_archive_entries: PositiveInt = 1000
    processing_timeout_seconds: PositiveInt = 60

    currency: Literal["INR"] = "INR"
    match_amount_tolerance: Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False)] = Decimal(
        "0.01"
    )
    fuzzy_suggestion_threshold: Score = Decimal("88.00")
    fuzzy_min_score_gap: Score = Decimal("5.00")
    match_policy_version: Literal["match-v1"] = "match-v1"

    whatsapp_enabled: bool = False
    whatsapp_public_url: str = ""
    meta_graph_version: str = ""
    meta_phone_number_id: str = ""
    meta_waba_id: str = ""
    meta_access_token: SecretStr = SecretStr("")
    meta_app_secret: SecretStr = SecretStr("")
    meta_verify_token: SecretStr = SecretStr("")
    whatsapp_send_budget: Annotated[int, BeforeValidator(parse_integer), Field(ge=0)] = 0
    http_connect_timeout_seconds: PositiveSeconds = Decimal("5")
    http_read_timeout_seconds: PositiveSeconds = Decimal("20")
    http_write_timeout_seconds: PositiveSeconds = Decimal("20")
    http_pool_timeout_seconds: PositiveSeconds = Decimal("5")

    link_code_ttl_seconds: PositiveInt = 600
    link_attempts_per_window: PositiveInt = 5
    link_attempt_window_seconds: PositiveInt = 600
    download_capability_ttl_seconds: PositiveInt = 600
    download_capability_max_downloads: PositiveInt = 3
    read_requests_per_minute: PositiveInt = 60
    mutation_requests_per_minute: PositiveInt = 10
    import_requests_per_minute: PositiveInt = 3

    @model_validator(mode="after")
    def report_limits(self):
        if (self.max_artifact_bytes + 2) // 3 * 4 + 65536 > self.max_parsed_import_bytes:
            raise ValueError("MAX_PARSED_IMPORT_BYTES must accommodate encoded artifacts")
        if self.max_report_snapshot_bytes > self.memory_state_max_bytes:
            raise ValueError("Report snapshots exceed the configured state budget")
        return self

    @field_validator("demo_mode", "whatsapp_enabled", mode="before")
    @classmethod
    def strict_boolean(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise ValueError("Use true or false")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def decode_origins(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (ValueError, RecursionError):
                raise ValueError("CORS_ORIGINS must be a JSON array") from None
        return value

    @field_validator("cors_origins")
    @classmethod
    def check_origins(cls, value: list[str]) -> list[str]:
        for origin in value:
            validate_origin(origin)
            if urlsplit(origin).hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("Only local website origins are supported in this phase")
        if len(set(value)) != len(value):
            raise ValueError("Duplicate CORS origins")
        return value

    @field_validator("public_web_url", "public_api_url")
    @classmethod
    def check_public_origin(cls, value: str) -> str:
        validate_origin(value)
        if urlsplit(value).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Only local website/API URLs are supported in this phase")
        return value

    @field_validator("whatsapp_public_url")
    @classmethod
    def check_channel_origin(cls, value: str) -> str:
        if not value:
            return value
        validate_origin(value)
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.port not in {None, 443}
            or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("WHATSAPP_PUBLIC_URL must be an exact public HTTPS origin")
        return value

    @field_validator("local_data_dir")
    @classmethod
    def check_local_directory(cls, value: Path) -> Path:
        # Keep future private files inside backend/data; no remote/UNC storage paths.
        data_root = BACKEND_DIR / "data"
        resolved = (BACKEND_DIR / value).resolve()
        if not resolved.is_relative_to(data_root):
            raise ValueError("LOCAL_DATA_DIR must stay inside backend/data")
        return resolved

    @model_validator(mode="after")
    def check_relationships(self) -> "Settings":
        api_origin = urlsplit(self.public_api_url)
        advertised_port = api_origin.port or (443 if api_origin.scheme == "https" else 80)
        if api_origin.scheme != "http" or advertised_port != self.port:
            raise ValueError("PUBLIC_API_URL must use HTTP and match PORT for this local launcher")
        web_origin = urlsplit(self.public_web_url)
        if web_origin.scheme != "http" or web_origin.hostname != api_origin.hostname:
            raise ValueError(
                "Website and API must use the same HTTP hostname for local browser sessions"
            )
        compatible_hosts = {"localhost", self.host}
        if api_origin.hostname not in compatible_hosts:
            raise ValueError("PUBLIC_API_URL must match the configured loopback HOST")
        if self.public_web_url not in self.cors_origins:
            raise ValueError("PUBLIC_WEB_URL must be included in CORS_ORIGINS")
        if self.max_local_data_bytes < self.max_database_bytes * 3 + 131072:
            raise ValueError(
                "MAX_LOCAL_DATA_BYTES must cover database, journal, backup and reserve"
            )
        if self.session_ttl_seconds > 86400:
            raise ValueError("SESSION_TTL_SECONDS must not exceed one day")
        if self.max_upload_bytes > self.memory_state_max_bytes:
            raise ValueError("MAX_UPLOAD_BYTES exceeds MEMORY_STATE_MAX_BYTES")
        if self.max_xlsx_uncompressed_bytes < self.max_upload_bytes:
            raise ValueError("MAX_XLSX_UNCOMPRESSED_BYTES must cover MAX_UPLOAD_BYTES")
        if self.fuzzy_min_score_gap > self.fuzzy_suggestion_threshold:
            raise ValueError("FUZZY_MIN_SCORE_GAP exceeds FUZZY_SUGGESTION_THRESHOLD")
        if self.match_amount_tolerance != self.match_amount_tolerance.quantize(Decimal("0.01")):
            raise ValueError("MATCH_AMOUNT_TOLERANCE must use at most two decimal places")
        if self.whatsapp_enabled:
            # Public origin enables only callback/capability paths, never browser API access.
            if not self.whatsapp_public_url:
                raise ValueError("WHATSAPP_PUBLIC_URL is required when WhatsApp is enabled")
            if not re.fullmatch(r"v[1-9][0-9]*\.[0-9]+", self.meta_graph_version):
                raise ValueError("META_GRAPH_VERSION is required and must have version syntax")
            for name in ("meta_phone_number_id", "meta_waba_id"):
                if not re.fullmatch(r"[0-9]+", getattr(self, name)):
                    raise ValueError(f"{name.upper()} must contain a numeric provider ID")
            for name in ("meta_access_token", "meta_app_secret", "meta_verify_token"):
                if not getattr(self, name).get_secret_value().strip():
                    raise ValueError(f"{name.upper()} is required")
        return self


class ConfigurationError(RuntimeError):
    """Safe for terminal output: contains field names, never supplied values."""


def load_settings() -> Settings:
    try:
        dotenv_path = Settings.model_config.get("env_file")
        if dotenv_path is not None and Path(dotenv_path).exists():
            seen = set()
            with Path(dotenv_path).open(encoding="utf-8") as stream:
                for binding in parse_stream(stream):
                    if binding.error:
                        raise ConfigurationError("Invalid .env syntax")
                    if binding.key is not None:
                        key = binding.key.lower()
                        if binding.value is None or key in seen:
                            raise ConfigurationError("Invalid or duplicate .env setting")
                        seen.add(key)
        return Settings()
    except ValidationError as exc:
        names = sorted(
            {
                str(error["loc"][0]).upper() if error["loc"] else "CONFIGURATION"
                for error in exc.errors(include_input=False, include_context=False)
            }
        )
        # Unknown dotenv keys may contain private text; only known field names are printed.
        known_names = {name.upper() for name in Settings.model_fields}
        names = [name if name in known_names else "CONFIGURATION" for name in names]
        raise ConfigurationError("Invalid settings: " + ", ".join(sorted(set(names)))) from None
    except (SettingsError, OSError, UnicodeError, ValueError):
        raise ConfigurationError(
            "Cannot load backend configuration; check .env formatting"
        ) from None
