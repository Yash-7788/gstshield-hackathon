"""Read-only report child; output published only after parent validates freshness."""

import base64
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from app.adapters.reports import ReportFailure, generate
from app.services.imports import digest, encode


def main():
    try:
        task = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        with closing(
            sqlite3.connect(Path(task["database"]).as_uri() + "?mode=ro", uri=True)
        ) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT snapshot_json,snapshot_sha256 FROM artifacts "
                "WHERE workspace_id=? AND id=? AND state='PENDING'",
                (task["workspace_id"], task["artifact_id"]),
            ).fetchone()
        if row is None or len(row["snapshot_json"].encode()) > task["max_snapshot_bytes"]:
            raise ReportFailure("REPORT_SNAPSHOT_INVALID")
        snapshot = json.loads(row["snapshot_json"])
        if digest(snapshot) != row["snapshot_sha256"]:
            raise ReportFailure("REPORT_SNAPSHOT_INVALID")
        content = generate(snapshot, task["max_bytes"], task["max_pages"])
        outcome = {
            "content": base64.b64encode(content).decode("ascii"),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    except ReportFailure as exc:
        outcome = {"error_code": exc.code}
    except Exception:
        outcome = {"error_code": "REPORT_FAILED"}
    print(encode(outcome))


if __name__ == "__main__":
    main()
