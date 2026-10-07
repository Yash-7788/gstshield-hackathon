"""One durable local queue, one killable parser child, atomic preview publication."""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import psutil

from app.config import Settings
from app.domain.imports import MONEY_FIELDS
from app.errors import StorageError
from app.services.imports import encode

logger = logging.getLogger("gstshield")
LIMIT_NAMES = (
    "max_upload_bytes",
    "max_import_rows",
    "max_import_columns",
    "max_cell_characters",
    "max_json_depth",
    "max_xlsx_uncompressed_bytes",
    "max_xlsx_archive_entries",
    "max_parsed_import_bytes",
)


class ImportDispatcher:
    def __init__(self, imports, runs=None, reports=None):
        self.imports = imports
        self.runs = runs
        self.reports = reports
        self.store = imports.store
        self.settings = imports.settings
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="gstshield-imports", daemon=True)
        self.peak_rss = 0

    def start(self):
        with self.store.transaction() as connection:
            now = int(time.time())
            if self.runs is not None:
                self.runs.recover(connection, now)
            if self.reports is not None:
                self.reports.recover(connection, now)
            connection.execute(
                "UPDATE imports SET state='FAILED',version=version+1,updated_at=?,"
                "errors_json=? WHERE id IN (SELECT import_id FROM jobs WHERE state='RUNNING')",
                (now, encode([{"field": "file", "reason": "PROCESSING_INTERRUPTED"}])),
            )
            connection.execute(
                "UPDATE jobs SET "
                "state='FAILED',error_code='PROCESSING_INTERRUPTED',updated_at=? "
                "WHERE state='RUNNING'",
                (now,),
            )
        # Only this component's generated, ordinary result files are eligible for cleanup.
        import re

        from app import config
        from app.storage.local import check_path

        for path in self.store.root.glob("parser-*.json"):
            if re.fullmatch(r"parser-[0-9a-f-]{36}(\.task)?\.json", path.name):
                check_path(path, config.BACKEND_DIR / "data")
                path.unlink()
        self.thread.start()

    def close(self):
        self.stop_event.set()
        self.imports.wakeup.set()
        if self.thread.is_alive():
            self.thread.join(timeout=10)
        if self.thread.is_alive():
            raise StorageError("Local parser did not stop; preserve storage before restart.")

    def claim(self):
        queue_sql = (
            "SELECT kind,import_id AS target,created_at,id FROM jobs WHERE state='QUEUED' "
            "UNION ALL SELECT kind,run_id AS target,created_at,id FROM run_jobs WHERE"
            " state='QUEUED' "
            "UNION ALL SELECT kind,artifact_id AS target,created_at,id FROM artifact_jobs "
            "WHERE state='QUEUED' ORDER BY created_at,id LIMIT 1"
        )
        with self.store.transaction(write=False) as connection:
            if connection.execute(queue_sql).fetchone() is None:
                return None
        with self.store.transaction() as connection:
            pending = connection.execute(queue_sql).fetchone()
            if pending is None:
                return None
            if pending["kind"] == "ARTIFACT":
                if self.reports is None:
                    raise StorageError("Report dispatcher is unavailable.")
                return self.reports.claim(connection, pending["target"])
            if pending["kind"] == "RUN":
                if self.runs is None:
                    raise StorageError("Reconciliation dispatcher is unavailable.")
                return self.runs.claim(connection, pending["target"])
            row = connection.execute(
                "SELECT i.*,r.gstin AS recipient_gstin FROM imports i JOIN registrations r "
                "ON r.id=i.registration_id AND r.workspace_id=i.workspace_id WHERE i.id=?",
                (pending["target"],),
            ).fetchone()
            now = int(time.time())
            connection.execute(
                "UPDATE jobs SET state='RUNNING',updated_at=? WHERE id=?", (now, pending["id"])
            )
            connection.execute(
                "UPDATE imports SET state='PARSING',version=version+1,updated_at=? WHERE id=?",
                (now, row["id"]),
            )
            return dict(row)

    def parse(self, row):
        self.store.capacity(self.settings.max_parsed_import_bytes + 131072)
        output = self.store.root / f"parser-{uuid4()}.json"
        module = "app.jobs.import_worker"
        if row.get("job_kind") == "ARTIFACT":
            module = "app.jobs.report_worker"
            task = {
                "database": str(self.store.path),
                "artifact_id": row["id"],
                "workspace_id": row["workspace_id"],
                "max_snapshot_bytes": self.settings.max_report_snapshot_bytes,
                "max_bytes": self.settings.max_artifact_bytes,
                "max_pages": self.settings.max_report_pages,
            }
        elif row.get("job_kind") == "RUN":
            module = "app.jobs.run_worker"
            task = {
                "database": str(self.store.path),
                "run_id": row["id"],
                "workspace_id": row["workspace_id"],
            }
        else:
            task = {
                "database": str(self.store.path),
                "file_id": row["file_id"],
                "workspace_id": row["workspace_id"],
                "descriptor": {
                    key: row[key]
                    for key in (
                        "adapter_version",
                        "kind",
                        "period",
                        "sheet_name",
                        "recipient_gstin",
                    )
                },
                "limits": {key: getattr(self.settings, key) for key in LIMIT_NAMES},
            }
            task["descriptor"]["mapping"] = json.loads(row["mapping_json"])
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.lower() not in Settings.model_fields
        }
        environment["PYTHONIOENCODING"] = "utf-8"
        input_path = output.with_suffix(".task.json")
        child = None
        tracked = {}
        try:
            task_bytes = encode(task).encode()
            if len(task_bytes) > 65536:
                return {"error_code": "PARSER_INPUT_LIMIT"}
            with input_path.open("xb") as descriptor_file:
                descriptor_file.write(task_bytes)
            with output.open("xb") as stream:
                child = subprocess.Popen(
                    [sys.executable, "-m", module, str(input_path)],
                    cwd=Path(__file__).resolve().parents[2],
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                process = psutil.Process(child.pid)
                tracked[process.pid] = process
                deadline = time.monotonic() + self.settings.processing_timeout_seconds
                while child.poll() is None:
                    code = None
                    if self.stop_event.is_set():
                        code = "PROCESSING_INTERRUPTED"
                    elif time.monotonic() >= deadline:
                        code = "PROCESSING_TIMEOUT"
                    elif output.stat().st_size > self.settings.max_parsed_import_bytes:
                        code = "PARSED_RESULT_LIMIT"
                    try:
                        for descendant in process.children(recursive=True):
                            tracked[descendant.pid] = descendant
                        rss = 0
                        for member in tracked.values():
                            with suppress(psutil.NoSuchProcess):
                                rss += member.memory_info().rss
                        self.peak_rss = max(self.peak_rss, rss)
                        if rss > self.settings.max_parser_rss_bytes:
                            code = "PARSER_MEMORY_LIMIT"
                    except psutil.NoSuchProcess:
                        pass
                    if code:
                        self.terminate(child, tracked.values())
                        return {"error_code": code}
                    self.stop_event.wait(0.02)
            if child.returncode != 0:
                return {"error_code": "PARSER_FAILED"}
            if output.stat().st_size > self.settings.max_parsed_import_bytes:
                return {"error_code": "PARSED_RESULT_LIMIT"}
            return json.loads(output.read_text(encoding="utf-8"))
        finally:
            if child is not None:
                self.terminate(child, tracked.values())
            output.unlink(missing_ok=True)
            input_path.unlink(missing_ok=True)

    @staticmethod
    def terminate(child, tracked):
        # Windows venv launchers may create a second Python process. Stop the entire
        # observed tree and count its combined RSS, rather than just the launcher.
        members = list(tracked)
        try:
            root = psutil.Process(child.pid)
            members.extend(root.children(recursive=True))
        except psutil.NoSuchProcess:
            pass
        for member in reversed(members):
            with suppress(psutil.NoSuchProcess):
                member.kill()
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
        _, alive = psutil.wait_procs(members, timeout=3)
        if alive:
            raise StorageError("Parser processes could not be stopped.")

    def publish(self, row, outcome):
        if row.get("job_kind") == "ARTIFACT":
            self.reports.publish(row, outcome)
            return
        if row.get("job_kind") == "RUN":
            self.runs.publish(row, outcome)
            return
        now = int(time.time())
        with self.store.transaction() as connection:
            current = connection.execute(
                "SELECT state FROM jobs WHERE import_id=?", (row["id"],)
            ).fetchone()
            if current is None or current[0] != "RUNNING":
                return
            error = outcome.get("error_code")
            if error:
                connection.execute(
                    "UPDATE imports SET "
                    "state='FAILED',version=version+1,errors_json=?,updated_at=? "
                    "WHERE id=?",
                    (encode([{"field": "file", "reason": error}]), now, row["id"]),
                )
                connection.execute(
                    "UPDATE jobs SET state='FAILED',error_code=?,updated_at=? WHERE import_id=?",
                    (error, now, row["id"]),
                )
                return
            result = outcome["result"]
            rows = result["rows"]
            for item in rows:
                fields = (*MONEY_FIELDS, "total_tax")
                connection.execute(
                    "INSERT INTO import_rows VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row["workspace_id"],
                        row["id"],
                        item["row_number"],
                        encode(item["original"]),
                        encode(item["canonical"]),
                        encode(item["errors"]),
                        int(item["accepted"]),
                        int(item["duplicate"]),
                        *(item["amounts"].get(field) for field in fields),
                    ),
                )
            accepted = sum(item["accepted"] for item in rows)
            connection.execute(
                "UPDATE imports SET "
                "state='AWAITING_CONFIRMATION',version=version+1,accepted_rows=?,"
                "rejected_rows=?,duplicate_rows=?,errors_json=?,columns_json=?,gen"
                "erated_at=?,sheet_name=?,"
                "updated_at=?,mapping_json=? WHERE id=?",
                (
                    accepted,
                    len(rows) - accepted,
                    result["duplicate_rows"],
                    encode(result["errors"]),
                    encode(result["columns"]),
                    result["generated_at"],
                    result["sheet_name"],
                    now,
                    encode(result["mapping"]),
                    row["id"],
                ),
            )
            connection.execute(
                "UPDATE jobs SET state='SUCCEEDED',updated_at=? WHERE import_id=?", (now, row["id"])
            )

    def run(self):
        while not self.stop_event.is_set():
            row = None
            try:
                row = self.claim()
                if row is not None:
                    self.publish(row, self.parse(row))
                    continue
            except Exception as exc:
                logger.error("Import worker failure exception_type=%s", type(exc).__name__)
                if row is not None:
                    try:
                        self.publish(row, {"error_code": "STORAGE_OR_PARSER_FAILED"})
                    except StorageError:
                        logger.error(
                            "Import failure could not be persisted; restart recovery required"
                        )
            self.imports.wakeup.wait(0.5)
            self.imports.wakeup.clear()
