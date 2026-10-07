# Local workload verification

Run from `backend/` with the existing development environment:

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -m benchmarks.workload --output benchmarks/results/after.json
```

This opt-in tool starts one actual Uvicorn process on an ephemeral loopback port, provisions
synthetic accounts in a generated temporary directory, and exercises the existing private API.
It does not load the presenter's `.env`, access `backend/data`, send messages, call tax portals,
or use cloud services. The process and worker descendants are stopped in `finally`; its
synthetic temporary storage is then removed. This is verification tooling, not the backend launcher.

## Workloads and observations

The full selection uses 100 rows per source for three runs, 2,000 rows per source for three runs,
and a dense 2,000-by-2,000 matching graph for two runs. Normal inputs have 95% exact identities
and 5% separator-only suggestions requiring human review. Dense inputs intentionally have no
eligible candidate; all 2,000 results must remain missing, with exactly INR 360,000.00 recorded
GST requiring attention. Dense matching still counts all four million possible comparisons.

Both sources pass real upload, parse, accepted/rejected counts and confirmation. Every run has
independently expected classifications, complete result pagination, and a stable logical hash.
Initial tracking is derived before review so a resolved suggestion cannot disappear from the
expected first-detection count merely because of asynchronous scheduling. A review is recorded
for one normal suggestion, the exact summary is checked again, and tracking is refreshed.
There must be five, one hundred or two thousand retained actions for the respective inputs.
Normal runs generate and download actual PDFs; summary totals cover the full run while detailed
PDF coverage retains the existing maximum of 200 selected rows. Dense runs check tracking and
results without requesting an unrelated additional PDF workload.

A concurrent thread checks actual readiness every 100 milliseconds and samples the complete
backend process tree's RSS. This tree measurement includes the server, Python launchers and
processing children; it is different from the dispatcher's existing worker-only RSS cap.
The final database must pass integrity/foreign-key checks, every run must be completed or
superseded, and no processing job may remain queued/running. An unrelated workspace must
remain opaque with HTTP 404. Scratch descriptor/output files are counted after accepted work.

The measurement records UTC date, CPU, RAM, OS, Python/SQLite, base commit, normalized application
source hash, dependency lock hash, bytes/rows, separate stage times, read latency, DB growth,
and first/repeated trials. Percentiles use nearest rank; with five samples p95 equals maximum.
Normal request budgets are increased only in this synthetic server to accommodate deliberately
rapid repeated polling: reads 5,000/minute, mutations 1,000/minute and imports 100/minute.
The application defaults, one heavy worker, five pending jobs, 60-second processing deadline,
sampled 256 MiB worker-tree limit, exact money, database/disk limits and retention quotas remain
unchanged. Every measured workload response, including transient 503 retries, is counted rather than
hidden; readiness probes have their own success/failure counters. Retried commands preserve their original idempotency key.

## Focused diagnostics

`--case demo`, `--case normal-max`, and `--case dense-max` limit the HTTP workload; the domain
microbenchmark still measures the dense graph twice. `--profile-actions` profiles synthetic
action derivation and captures thread diagnostics. It is for locating a cause, not comparable
final timing: profiling and stack dumps can alter scheduling and runtime. Captured `.log` files
are machine-local and ignored by Git. A failed tool run preserves partial JSON, labels
`measurement_complete=false`, records the interruption, and exits unsuccessfully.

## Reading the retained evidence

`results/before.json` is an explicitly partial baseline against the Phase 10 commit. The saved
100-row trials and dense-domain timings are valid observations. Its first normal 2,000-row
pagination stopped on a storage-busy response, so no complete baseline health/memory or maximum
HTTP percentile is claimed. Its old small-sample p95 index can understate p95; compare median and
maximum instead. The completed final measurement and exact optimization/equivalence evidence
are linked from the build plan. `results/action-diagnostic.json` is a failed, explicitly profiled
intermediate workload that identified expensive source lookups; it is cause evidence, not a
passing gate or comparable timing. Its 2,000 action-source calls took about 32.8 seconds under
profiling. The final unprofiled run uses corrected workspace-indexed lookups. Smaller timings do not mean that historical records, snapshots,
or previous PDFs were deleted: database growth is expected retention inside configured bounds.

The passing gate is local hackathon evidence for these synthetic distributions. Very long
notes, very large candidate graphs, retained history quotas, report page/byte limits and actual
request budgets still apply; this does not establish arbitrary-file performance or production
capacity. Frontend profiling and real WhatsApp remain separate planned phases.
