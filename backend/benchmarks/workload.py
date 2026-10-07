"""Measure real local HTTP/worker workloads in disposable synthetic storage.

Run: python -m benchmarks.workload --output benchmarks/results/before.json
Not a production launcher; no private .env, database, password or provider is used.
"""

import argparse
import cProfile
import csv
import hashlib
import io
import json
import math
import os
import platform
import socket
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import closing, suppress
from pathlib import Path
from uuid import uuid4

import httpx2 as httpx
import psutil

PASSWORD = "synthetic-benchmark-passphrase"
ORIGIN = "http://127.0.0.1:3000"
ROW = {
    "voucher_id": "V1",
    "recipient_gstin": "27ABCDE1234F1Z5",
    "supplier_gstin": "27PQRSX5678L1Z2",
    "invoice_number": "INV-1",
    "invoice_date": "2024-04-10",
    "document_type": "INVOICE",
    "taxable_value": "1000.00",
    "cgst": "90.00",
    "sgst": "90.00",
    "igst": "0.00",
    "cess": "0.00",
    "other_charges": "0.00",
    "round_off": "0.00",
    "gross_total": "1180.00",
}


def dataset(count, dense=False):
    purchases, portals = [], []
    for index in range(count):
        number = "INV-" + hashlib.sha256(str(index).encode()).hexdigest()[:24].upper()
        purchase = ROW | {"voucher_id": f"V{index}", "invoice_number": number}
        portal = purchase | {
            "invoice_number": number.replace("-", "/") if index % 20 == 0 else number
        }
        if dense:
            purchase["invoice_number"] = "A" * 20 + str(index)
            portal["invoice_number"] = "Z" * 20 + str(index)
        purchases.append(purchase)
        portals.append(portal)
    return purchases, portals


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(ROW))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def serve(root, profile_actions=False):
    import uvicorn

    from app import config
    from app.config import Settings
    from app.main import create_app
    from app.services.access import AccessService
    from app.services.actions import ActionService
    from app.storage.local import LocalStore

    root = root.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "gstshield-benchmark-"
    ):
        raise ValueError("Benchmark storage must be a generated temporary directory.")
    if profile_actions:
        import faulthandler

        faulthandler.dump_traceback_later(5, repeat=True)
        original = ActionService.sync_run

        def measured(service, connection, run):
            profile = cProfile.Profile()
            try:
                return profile.runcall(original, service, connection, run)
            finally:
                entries = sorted(
                    profile.getstats(), key=lambda entry: entry.totaltime, reverse=True
                )
                (root / "action-profile.json").write_text(
                    json.dumps(
                        [
                            {
                                "function": str(entry.code)
                                if isinstance(entry.code, str)
                                else entry.code.co_name,
                                "calls": entry.callcount,
                                "seconds": round(entry.totaltime, 6),
                            }
                            for entry in entries[:20]
                        ],
                        indent=2,
                    ),
                    encoding="utf-8",
                )

        ActionService.sync_run = measured
    for name in list(os.environ):
        if name.lower() in Settings.model_fields:
            del os.environ[name]
    config.BACKEND_DIR = root
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    settings = Settings(
        _env_file=None,
        app_env="test",
        port=port,
        public_api_url=f"http://127.0.0.1:{port}",
        public_web_url=ORIGIN,
        read_requests_per_minute=5000,
        mutation_requests_per_minute=1000,
        import_requests_per_minute=100,
    )
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    try:
        with store.transaction(write=False) as connection:
            populated = connection.execute("SELECT count(*) FROM users").fetchone()[0]
        if not populated:
            access = AccessService(store)
            _, workspace = access.provision("benchmark-user", PASSWORD, "Synthetic benchmark")
            registration = access.add_registration(
                workspace, ROW["recipient_gstin"], "Synthetic registration"
            )
            _, foreign = access.provision(
                "benchmark-other", PASSWORD, "Foreign synthetic workspace"
            )
            (root / "scope.json").write_text(
                json.dumps(
                    {"workspace": workspace, "registration": registration, "foreign": foreign}
                ),
                encoding="utf-8",
            )
    finally:
        store.close()
    (root / "port.json").write_text(json.dumps({"port": port}), encoding="utf-8")
    uvicorn.Server(
        uvicorn.Config(
            create_app(settings), log_level="error", access_log=False, proxy_headers=False
        )
    ).run(sockets=[listener])


def response_data(response, allowed=(200,)):
    if response.status_code not in allowed:
        code = response.json().get("error", {}).get("code", "HTTP_ERROR")
        raise RuntimeError(f"Benchmark request failed: HTTP {response.status_code} {code}")
    return response.json()["data"]


def read(client, path, **kwargs):
    # Observe bounded storage backpressure without abandoning accepted work.
    # Every response (including retries) is counted by the measurement hook.
    deadline = time.monotonic() + 20
    while True:
        response = client.get(path, **kwargs)
        if response.status_code != 503 or time.monotonic() >= deadline:
            return response
        time.sleep(0.2)


def timing(values):
    ordered = sorted(values)
    return {
        "samples": len(values),
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 3),
        "max_ms": round(max(values), 3),
    }


class Observer:
    def __init__(self, process, origin):
        self.process, self.origin = psutil.Process(process.pid), origin
        self.stop = threading.Event()
        self.samples = []
        self.failures = 0
        self.peak_rss = 0
        self.idle_rss = []
        self.thread = threading.Thread(target=self.observe)

    def observe(self):
        with httpx.Client(timeout=3, trust_env=False) as client:
            while not self.stop.is_set():
                start = time.perf_counter()
                try:
                    response = client.get(self.origin + "/health/ready")
                    if response.status_code != 200:
                        self.failures += 1
                    else:
                        self.samples.append((time.perf_counter() - start) * 1000)
                    self.peak_rss = max(self.peak_rss, self.rss())
                except (httpx.HTTPError, psutil.Error):
                    self.failures += 1
                self.stop.wait(0.1)

    def rss(self):
        total = 0
        for member in [self.process, *self.process.children(recursive=True)]:
            with suppress(psutil.NoSuchProcess):
                total += member.memory_info().rss
        return total

    def close(self):
        self.stop.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError("Benchmark observer did not stop.")


def poll(client, path, terminal, timeout=80):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = read(client, path)
        if response.status_code == 503:
            time.sleep(0.2)
            continue
        data = response_data(response)
        if data["state"] in terminal:
            return data
        if data["state"] == "FAILED":
            raise RuntimeError("Benchmark job failed: " + str(data.get("error_code")))
        time.sleep(0.1)
    raise RuntimeError("Benchmark job did not terminate within its observation deadline.")


def command(client, path, headers, payload):
    key = str(uuid4())
    for _ in range(10):
        response = client.post(path, json=payload, headers=headers | {"Idempotency-Key": key})
        if response.status_code != 503:
            return response_data(response, (200, 202))
        time.sleep(0.2)
    raise RuntimeError("Benchmark command stayed unavailable.")


def source(client, base, registration, headers, rows, kind):
    body = csv_bytes(rows)
    start = time.perf_counter()
    response = client.post(
        base + "/imports",
        data={
            "registration_id": registration,
            "period": "2024-05",
            "kind": kind,
            "adapter_version": "csv-v1",
        },
        files={"file": ("synthetic.csv", body, "text/csv")},
        headers=headers | {"Idempotency-Key": str(uuid4())},
    )
    data = response_data(response, (202,))
    received = time.perf_counter()
    data = poll(client, base + "/imports/" + data["id"], {"AWAITING_CONFIRMATION"})
    parsed = time.perf_counter()
    if data["accepted_rows"] != len(rows) or data["rejected_rows"] or data["duplicate_rows"]:
        raise RuntimeError("Benchmark dropped/rejected/duplicated source rows.")
    data = command(
        client,
        base + "/imports/" + data["id"] + "/confirm",
        headers,
        {"expected_version": data["version"]},
    )
    return data, {
        "bytes": len(body),
        "upload_accept_ms": round((received - start) * 1000, 3),
        "parse_after_accept_ms": round((parsed - received) * 1000, 3),
        "confirm_ms": round((time.perf_counter() - parsed) * 1000, 3),
    }


def trial(client, base, headers, registration, purchase, portal, count, dense, report):
    start = time.perf_counter()
    run = command(
        client,
        base + "/runs",
        headers,
        {
            "registration_id": registration,
            "period": "2024-05",
            "purchase_import_id": purchase["id"],
            "portal_import_id": portal["id"],
        },
    )
    accepted = time.perf_counter()
    run = poll(client, base + "/runs/" + run["id"], {"COMPLETED", "FAILED"})
    completed = time.perf_counter()
    if run["state"] == "FAILED":
        return {
            "run_accept_ms": round((accepted - start) * 1000, 3),
            "run_complete_ms": round((completed - start) * 1000, 3),
            "failed": run.get("error_code"),
        }
    expected = (
        {"MISSING_IN_SNAPSHOT": count}
        if dense
        else {"EXACT_MATCH": count - count // 20, "FUZZY_SUGGESTION": count // 20}
    )
    actual = {key: value for key, value in run["summary"]["counts"].items() if value}
    if actual != expected or run["summary"]["accepted_purchase_rows"] != count:
        raise RuntimeError("Independent expected classification/count differs.")
    # Derive the initial suggestions before a human can resolve one. Otherwise the
    # asynchronous monitor may legitimately never create an already-resolved task.
    before_actions = time.perf_counter()
    queue = response_data(read(client, base + "/actions", params={"limit": 20}))
    if queue["automation"]["pending_sources"] or queue["automation"]["error_code"]:
        raise RuntimeError("Accepted evidence was not fully derived into business actions.")
    initial_action_refresh_ms = round((time.perf_counter() - before_actions) * 1000, 3)
    queries = []
    for _ in range(5):
        before = time.perf_counter()
        response_data(read(client, base + "/runs/" + run["id"]))
        queries.append((time.perf_counter() - before) * 1000)
    rows, cursor = [], 0
    while True:
        page = response_data(
            read(
                client, base + f"/runs/{run['id']}/results", params={"limit": 100, "cursor": cursor}
            )
        )
        rows.extend(page["results"])
        if page["next_cursor"] is None:
            break
        cursor = page["next_cursor"]
    if len(rows) != count or len({row["source_row_number"] for row in rows}) != count:
        raise RuntimeError("Paged results lost or repeated rows.")
    logical = [
        (
            row["source_row_number"],
            row["status"],
            row["canonical"]["invoice_number"],
            row["reason_codes"],
        )
        for row in rows
    ]
    metrics = {
        "run_id": run["id"],
        "initial_action_refresh_http_ms": initial_action_refresh_ms,
        "run_accept_ms": round((accepted - start) * 1000, 3),
        "run_complete_ms": round((completed - start) * 1000, 3),
        "summary_http": timing(queries),
        "golden_sha256": hashlib.sha256(json.dumps(logical, sort_keys=True).encode()).hexdigest(),
        "counts": actual,
        "tax_exposure_review": run["summary"]["tax_exposure_review"],
    }
    if not dense:
        row = next(row for row in rows if row["status"] == "FUZZY_SUGGESTION")
        detail = response_data(read(client, base + "/results/" + row["id"]))
        before = time.perf_counter()
        reviewed = command(
            client,
            base + "/results/" + row["id"] + "/review",
            headers,
            {
                "expected_version": row["version"],
                "action": "ACCEPT_CANDIDATE",
                "candidate_id": detail["candidates"][0]["id"],
                "reason": "Checked synthetic benchmark source.",
            },
        )
        metrics["review_ms"] = round((time.perf_counter() - before) * 1000, 3)
        if reviewed["status"] != "REVIEW_ACCEPTED":
            raise RuntimeError("Benchmark review was not recorded.")
        run = response_data(read(client, base + "/runs/" + run["id"]))
        if (
            run["summary"]["counts"]["REVIEW_ACCEPTED"] != 1
            or run["summary"]["tax_exposure_review"] != "0.00"
        ):
            raise RuntimeError("Exact review summary changed incorrectly.")
    before_actions = time.perf_counter()
    queue = response_data(read(client, base + "/actions", params={"limit": 20}))
    if queue["automation"]["pending_sources"] or queue["automation"]["error_code"]:
        raise RuntimeError("Accepted evidence was not fully derived into business actions.")
    metrics["action_refresh_http_ms"] = round((time.perf_counter() - before_actions) * 1000, 3)
    if report:
        before = time.perf_counter()
        artifact = command(
            client,
            base + "/artifacts",
            headers,
            {
                "kind": "RECONCILIATION_PDF",
                "source_id": run["id"],
                "expected_version": run["version"],
                "selected_result_ids": [],
            },
        )
        received = time.perf_counter()
        artifact = poll(client, base + "/artifacts/" + artifact["id"], {"READY", "FAILED"})
        if artifact["state"] == "FAILED":
            metrics["report"] = {
                "accept_ms": round((received - before) * 1000, 3),
                "complete_ms": round((time.perf_counter() - before) * 1000, 3),
                "failed": artifact["error_code"],
            }
            return metrics
        ready = time.perf_counter()
        download = read(client, base + "/artifacts/" + artifact["id"] + "/download")
        if download.status_code != 200 or not download.content.startswith(b"%PDF"):
            raise RuntimeError("Benchmark report download failed.")
        metrics["report"] = {
            "accept_ms": round((received - before) * 1000, 3),
            "complete_ms": round((ready - before) * 1000, 3),
            "download_ms": round((time.perf_counter() - ready) * 1000, 3),
            "bytes": len(download.content),
            "detail_rows": min(count, 200),
        }
    return metrics


def micro():
    from app.domain.imports import canonical_row
    from app.domain.reconciliation import reconcile

    policy = {
        "amount_tolerance": "0.01",
        "fuzzy_threshold": "88.00",
        "fuzzy_gap": "5.00",
        "max_candidates": 10000,
        "max_pairs": 4000000,
    }
    raw = dataset(2000, True)
    rows = [
        [
            canonical_row(row, {key: key for key in row}, ROW["recipient_gstin"], kind, index + 1)
            for index, row in enumerate(source)
        ]
        for source, kind in zip(raw, ("PURCHASE", "PORTAL_2B"), strict=True)
    ]
    seconds = []
    for _ in range(2):
        start = time.perf_counter()
        result = reconcile(*rows, policy)
        seconds.append(round(time.perf_counter() - start, 6))
        if (
            result["compared_pairs"] != 4000000
            or result["candidate_count"]
            or len(result["results"]) != 2000
        ):
            raise RuntimeError("Dense matching graph differs from independent expectation.")
    profile = cProfile.Profile()
    profile.enable()
    reconcile([*rows[0][:100]], [*rows[1][:100]], policy)
    profile.disable()
    entries = profile.getstats()
    return {
        "dense_2000_seconds": seconds,
        "profile_100": [
            {
                "function": entry.code.co_name,
                "calls": entry.callcount,
                "total_seconds": round(entry.totaltime, 6),
            }
            for entry in sorted(entries, key=lambda e: e.totaltime, reverse=True)
            if hasattr(entry.code, "co_name")
        ][:10],
    }


def terminate(process):
    with suppress(psutil.NoSuchProcess):
        members = [
            psutil.Process(process.pid),
            *psutil.Process(process.pid).children(recursive=True),
        ]
        for member in reversed(members):
            with suppress(psutil.NoSuchProcess):
                member.kill()
        _, alive = psutil.wait_procs(members, timeout=5)
        if alive:
            raise RuntimeError("Benchmark processes did not stop.")
    process.wait(timeout=5)


def measure(output=None, case="all", profile_actions=False):
    report = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "application_sha256": hashlib.sha256(
            b"".join(
                str(path.relative_to(Path("app"))).replace("\\", "/").encode()
                + b"\0"
                + path.read_bytes().replace(b"\r\n", b"\n")
                + b"\0"
                for path in sorted(Path("app").rglob("*.py"))
            )
        ).hexdigest(),
        "lock_sha256": hashlib.sha256(Path("uv.lock").read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "os": platform.platform(),
        "cpu": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "physical_memory_bytes": psutil.virtual_memory().total,
        "conditions": {
            "percentile_method": "nearest-rank ceil(0.95*n); small-sample p95 equals max",
            "case": case,
            "profile_actions": profile_actions,
            "transport": "real loopback HTTP, one Uvicorn process, disposable workers",
            "source_rows": [100, 2000],
            "normal_distribution": "95% exact, 5% separator-only human suggestions",
            "dense_distribution": "one identity group; dissimilar numbers; 4 million pairs",
            "read_per_minute": 5000,
            "mutation_per_minute": 1000,
            "import_per_minute": 100,
            "other_limits": "defaults: 60s worker, sampled 256 MiB child RSS, 1 worker, 5 pending",
        },
        "workloads": [],
        "measurement_complete": False,
        "http_status_counts": {},
    }

    def save_progress():
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def count_status(response):
        key = str(response.status_code)
        report["http_status_counts"][key] = report["http_status_counts"].get(key, 0) + 1

    report["domain"] = micro()
    print(
        "Dense domain measurement: " + str(report["domain"]["dense_2000_seconds"]),
        file=sys.stderr,
        flush=True,
    )
    save_progress()
    with tempfile.TemporaryDirectory(prefix="gstshield-benchmark-") as directory:
        root = Path(directory)
        server_log = (root / "server.log").open("wb")
        process = subprocess.Popen(
            [sys.executable, "-m", "benchmarks.workload", "--serve", str(root)]
            + (["--profile-actions"] if profile_actions else []),
            stdout=subprocess.DEVNULL,
            stderr=server_log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        observer = None
        try:
            deadline = time.monotonic() + 30
            while not (root / "port.json").exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Synthetic benchmark server did not start.")
                time.sleep(0.1)
            origin = f"http://127.0.0.1:{json.loads((root / 'port.json').read_text())['port']}"
            with httpx.Client(
                base_url=origin,
                timeout=90,
                trust_env=False,
                event_hooks={"response": [count_status]},
            ) as client:
                while True:
                    try:
                        if client.get("/health/ready").is_success:
                            break
                    except httpx.HTTPError:
                        pass
                    if time.monotonic() > deadline:
                        raise RuntimeError("Synthetic benchmark server was not ready.")
                    time.sleep(0.1)
                scope = json.loads((root / "scope.json").read_text())
                session = response_data(
                    client.post(
                        "/api/v1/auth/login",
                        json={"username": "benchmark-user", "password": PASSWORD},
                        headers={"Origin": ORIGIN},
                    )
                )
                headers = {"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]}
                base = "/api/v1/workspaces/" + scope["workspace"]
                observer = Observer(process, origin)
                observer.thread.start()
                workloads = {
                    "all": [(100, False, 3), (2000, False, 3), (2000, True, 2)],
                    "demo": [(100, False, 3)],
                    "normal-max": [(2000, False, 3)],
                    "dense-max": [(2000, True, 2)],
                }
                for count, dense, repeats in workloads[case]:
                    purchases, portals = dataset(count, dense)
                    purchase, left = source(
                        client, base, scope["registration"], headers, purchases, "PURCHASE"
                    )
                    portal, right = source(
                        client, base, scope["registration"], headers, portals, "PORTAL_2B"
                    )
                    workload = {
                        "rows_per_source": count,
                        "dense": dense,
                        "imports": [left, right],
                        "trials": [],
                    }
                    report["workloads"].append(workload)
                    for iteration in range(repeats):
                        metrics = trial(
                            client,
                            base,
                            headers,
                            scope["registration"],
                            purchase,
                            portal,
                            count,
                            dense,
                            not dense,
                        )
                        metrics["iteration"] = iteration + 1
                        metrics["database_bytes"] = (root / "data/gstshield.sqlite3").stat().st_size
                        with closing(
                            sqlite3.connect(
                                (root / "data/gstshield.sqlite3").as_uri() + "?mode=ro", uri=True
                            )
                        ) as connection:
                            actions = connection.execute(
                                "SELECT count(*) FROM business_actions "
                                "WHERE workspace_id=? AND run_id=?",
                                (scope["workspace"], metrics["run_id"]),
                            ).fetchone()[0]
                        expected_actions = count if dense else count // 20
                        if actions != expected_actions:
                            raise RuntimeError(
                                f"Expected {expected_actions} retained actions; got {actions}."
                            )
                        metrics["retained_actions_for_purchase"] = actions
                        metrics["scratch_files_after_job"] = len(
                            list((root / "data").glob("parser-*"))
                        )
                        metrics["process_tree_rss_after_job"] = observer.rss()
                        workload["trials"].append(metrics)
                        save_progress()
                        print(
                            f"Measured rows={count} dense={dense} iteration={iteration + 1} "
                            f"run={metrics['run_complete_ms']:.0f}ms",
                            file=sys.stderr,
                            flush=True,
                        )
                foreign = read(client, f"/api/v1/workspaces/{scope['foreign']}/runs")
                if foreign.status_code != 404:
                    raise RuntimeError("Benchmark lost workspace isolation.")
                report["foreign_scope_status"] = foreign.status_code
                report["health_http"] = timing(observer.samples)
                report["health_failures"] = observer.failures
                report["peak_process_tree_rss_bytes"] = observer.peak_rss
                report["retained_database_bytes"] = (root / "data/gstshield.sqlite3").stat().st_size
                with closing(
                    sqlite3.connect(
                        (root / "data/gstshield.sqlite3").as_uri() + "?mode=ro", uri=True
                    )
                ) as connection:
                    report["integrity_check"] = connection.execute(
                        "PRAGMA integrity_check"
                    ).fetchone()[0]
                    report["foreign_key_violations"] = len(
                        connection.execute("PRAGMA foreign_key_check").fetchall()
                    )
                    report["completed_runs"] = connection.execute(
                        "SELECT count(*) FROM runs WHERE state IN ('COMPLETED','SUPERSEDED')"
                    ).fetchone()[0]
                    report["active_jobs_after_work"] = sum(
                        connection.execute(
                            f"SELECT count(*) FROM {table} WHERE state IN ('QUEUED','RUNNING')"
                        ).fetchone()[0]
                        for table in ("jobs", "run_jobs", "artifact_jobs")
                    )
        except Exception as exc:
            report["interruption"] = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            try:
                if observer is not None:
                    observer.close()
                    report["health_http"] = timing(observer.samples) if observer.samples else None
                    report["health_failures"] = observer.failures
                    report["peak_process_tree_rss_bytes"] = observer.peak_rss
            finally:
                terminate(process)
                server_log.close()
                if (root / "action-profile.json").exists():
                    report["action_profile"] = json.loads(
                        (root / "action-profile.json").read_text(encoding="utf-8")
                    )
                log = (root / "server.log").read_text(encoding="utf-8", errors="replace")
                # Only this synthetic server's diagnostics; never a private application log.
                if output:
                    output.with_suffix(".log").write_text(log, encoding="utf-8")
                save_progress()
    report["measurement_complete"] = True
    report["measurement_passed"] = (
        report["integrity_check"] == "ok"
        and not report["foreign_key_violations"]
        and not report["active_jobs_after_work"]
        and not report["health_failures"]
        and all(
            not trial.get("failed") and not trial.get("report", {}).get("failed")
            for workload in report["workloads"]
            for trial in workload["trials"]
        )
    )
    save_progress()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", choices=("all", "demo", "normal-max", "dense-max"), default="all")
    parser.add_argument("--serve", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--profile-actions", action="store_true")
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.profile_actions)
        return
    result = measure(args.output, args.case, args.profile_actions)
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    if not result["measurement_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
