"""Disposable reconciliation child: scoped immutable rows and a saved policy in."""

import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from app.domain.imports import MONEY_FIELDS, ParseFailure
from app.domain.reconciliation import reconcile


def read_rows(connection, workspace, identifier, limit):
    rows = connection.execute(
        (
            "SELECT * FROM import_rows WHERE workspace_id=? AND import_id=? ORDER BY "
            "row_number LIMIT ?"
        ),
        (workspace, identifier, limit + 1),
    ).fetchall()
    if len(rows) > limit:
        raise ParseFailure("MATCH_ROW_LIMIT")
    return [
        {
            "row_number": row["row_number"],
            "canonical": json.loads(row["canonical_json"]),
            "amounts": {field: row[field] for field in (*MONEY_FIELDS, "total_tax")},
            "accepted": bool(row["accepted"]),
            "duplicate": bool(row["duplicate"]),
        }
        for row in rows
    ]


def main():
    try:
        with Path(sys.argv[1]).open("rb") as stream:
            text = stream.read(65537)
        if len(text) > 65536:
            raise ParseFailure("PARSER_INPUT_LIMIT")
        task = json.loads(text)
        with closing(
            sqlite3.connect(Path(task["database"]).as_uri() + "?mode=ro", uri=True)
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            run = connection.execute(
                "SELECT * FROM runs WHERE workspace_id=? AND id=?",
                (task["workspace_id"], task["run_id"]),
            ).fetchone()
            if run is None or run["state"] != "RUNNING":
                raise ParseFailure("RUN_NOT_ACTIVE")
            policy = json.loads(run["policy_json"])
            sources = json.loads(run["sources_json"])
            for source in sources:
                actual = connection.execute(
                    "SELECT * FROM imports WHERE workspace_id=? AND id=?",
                    (run["workspace_id"], source["id"]),
                ).fetchone()
                if (
                    actual is None
                    or actual["state"] != "READY"
                    or actual["file_sha256"] != source["sha256"]
                ):
                    raise ParseFailure("SOURCE_SUPERSEDED")
            purchases = read_rows(
                connection, run["workspace_id"], run["purchase_import_id"], policy["max_rows"]
            )
            portals = read_rows(
                connection, run["workspace_id"], run["portal_import_id"], policy["max_rows"]
            )
        # Rows and policy are now immutable in memory. Release the read transaction
        # before CPU work so local rate/session/action writes can commit. Publication
        # still validates the lease and current source versions atomically.
        result = {"result": reconcile(purchases, portals, policy)}
        encoded = json.dumps(result, ensure_ascii=True, separators=(",", ":"))
        if len(encoded.encode()) > policy["max_result_bytes"]:
            raise ParseFailure("PARSED_RESULT_LIMIT")
    except ParseFailure as exc:
        encoded = json.dumps({"error_code": exc.code})
    except Exception:
        encoded = json.dumps({"error_code": "MATCH_FAILED"})
    sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
