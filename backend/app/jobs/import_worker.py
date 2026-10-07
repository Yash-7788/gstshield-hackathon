"""Disposable parser entry point: private source in, bounded safe JSON out."""

import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from app.domain.imports import ParseFailure


def main():
    try:
        with Path(sys.argv[1]).open("rb") as descriptor_file:
            text = descriptor_file.read(65537)
        if len(text) > 65536:
            raise ParseFailure("PARSER_INPUT_LIMIT")
        task = json.loads(text)
        with closing(
            sqlite3.connect(Path(task["database"]).as_uri() + "?mode=ro", uri=True)
        ) as connection:
            row = connection.execute(
                "SELECT content,sha256 FROM import_files WHERE id=? AND workspace_id=?",
                (task["file_id"], task["workspace_id"]),
            ).fetchone()
        if row is None or hashlib.sha256(row[0]).hexdigest() != row[1]:
            raise ParseFailure("SOURCE_INTEGRITY_FAILED")
        from app.adapters.imports import parse_import

        result = {"result": parse_import(row[0], task["descriptor"], task["limits"])}
    except ParseFailure as exc:
        result = {"error_code": exc.code}
    except Exception:
        result = {"error_code": "PARSER_FAILED"}
    sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
