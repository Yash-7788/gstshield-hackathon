from contextlib import contextmanager
from types import SimpleNamespace

from app.services.processes import ProcessService


def test_monitor_advances_beyond_first_fifty_and_revisits_prior_runs():
    records = [{"id": f"{i:03}", "created_by": "approved"} for i in range(101)]
    queries = []

    class Connection:
        def execute(self, sql, params):
            queries.append((sql, params))
            return SimpleNamespace(
                fetchall=lambda: [r for r in records if r["id"] > params[1]][:50]
            )

    class Store:
        @contextmanager
        def transaction(self):
            yield Connection()

    service = ProcessService.__new__(ProcessService)
    service.store = Store()
    service.scan_cursors = {}
    seen = []
    service.refresh_row = lambda con, actor, row, internal: seen.append(row["id"])
    for _ in range(4):
        service.scan("workspace")
    assert seen[:101] == [r["id"] for r in records]
    assert seen[101:] == [r["id"] for r in records[:50]]
    assert all(
        params[0] == "workspace" and "m.active=1" in sql and "u.active=1" in sql
        for sql, params in queries
    )
