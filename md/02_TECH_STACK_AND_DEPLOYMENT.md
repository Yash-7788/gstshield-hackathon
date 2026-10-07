# GST-Shield — actual technology stack and local setup

> **Active local implementation (2026-10-04):** This is a website with a Python backend running on the PC. Authoritative storage is a private SQLite file under `backend/data/`; accounts are provisioned locally and browser access uses revocable sessions. No external database, hosted identity, cloud storage or application hosting is selected. Phases 1–12 are complete and locally verified. Phase 11 passed the full backend regression (343 passed, 1 Windows privilege-related skip). Phase 12 passed 22 browser checks, built-preview checks and real 100/2,000-row website measurements. See 05 for dated evidence. Phase 13 local WhatsApp integration is implemented with focused checks; Meta setup and physical-phone acceptance remain pending. Phase 14 is not started. Full Phase 13 regression was stopped at the user’s request. The landing page/design is pending. The user authorized a new internal website in Phases 8–9; real WhatsApp remains Phase 13.

## Selected architecture

Use one FastAPI backend process on the local PC, Python's standard-library SQLite driver, and private files under backend/data. The internal website is a browser interface authorized for Phases 8–9. The user will supply the landing page/design separately later. It calls the same application services that a future WhatsApp adapter will call. The PC must remain running while the backend is used.

This decision replaces the earlier cloud plan throughout this planning pack. There is no database account, service connection string, hosted authentication project, object-storage bucket or application hosting bill. Internet access remains useful for dependency installation and necessary for real Meta messaging; local website/backend behavior does not need a provider round-trip.

| Earlier proposal | Current choice | Reason / effect |
|---|---|---|
| PostgreSQL / hosted database | Local SQLite file | Durable PC storage without a separate database process |
| Supabase Auth / signed JWTs | Local operator provisioned accounts + opaque sessions | No public signup, auth provider or refresh-token integration |
| Supabase Storage / signed bucket URLs | Private local directory | Paths stay server generated; future file access goes through scoped backend routes |
| Render / static cloud hosting | Backend and internal website run locally | PC availability determines uptime; no cloud deployment is required |
| SQLAlchemy, psycopg, Alembic | sqlite3 + explicit schema version | Fewer dependencies; later upgrades are reviewed, backed up and tested |
| Redis / external worker | SQLite job records + one bounded local dispatcher | Only one backend process may hold the data lock |
| Browser localStorage as business storage | Backend SQLite as authority | Browser reloads and account changes cannot invent or lose financial truth |

## Installed runtime, not release candidates

The committed `backend/uv.lock` records the full resolved graph and hashes. The versions below were installed and exercised on this Windows PC. This establishes compatibility for the tested code, not a claim that every future parser or provider integration is already implemented.

| Component | Installed version / use |
|---|---|
| CPython | 3.13.16, selected by .python-version |
| uv | 0.12.22 used on this PC |
| FastAPI | 0.142.2, HTTP routes and schema |
| Starlette | 1.7.0, resolved framework dependency |
| Pydantic | 2.13.5, input/output validation |
| Pydantic Settings | 2.15.0, validated environment configuration |
| python-dotenv | 1.2.4, dotenv parsing |
| Uvicorn | 0.54.0, supported local launcher |
| HTTPX2 | 2.13.1, test client only |
| pytest | 9.1.1, regression checks |
| Ruff | 0.16.10, lint and formatting |
| SQLite | 3.53.1 in this PC's selected interpreter; stdlib driver |
| RapidFuzz | 3.14.6, invoice-number suggestions only |
| Password/session/CSRF primitives | hashlib.scrypt, secrets, hmac from the standard library |

HTTPX2 matches the installed Starlette test client; do not reintroduce the deprecated HTTPX dependency from the early candidate list. Do not silently refresh the lock during the demo. New dependencies belong to the phase that actually uses them.

## Dependencies reserved for future phases

- Phase 3 now uses standard-library CSV/JSON, openpyxl 3.1.5, defusedxml 0.7.1, python-multipart 0.0.32 and psutil 7.2.2. The exact graph is committed in uv.lock; no pandas, ORM or external queue was added.
- Phase 4 installs RapidFuzz 3.14.6 (locked range >=3.14.6,<3.15) for suggestions. Integer paise and standard-library Decimal handle money; floating point is confined to similarity scores. Similarity never becomes automatic legal approval.
- Phase 5 installs ReportLab 5.0.1 (locked >=5.0.1,<5.1), resolving Pillow 12.3.0 and charset-normalizer 3.5.2. Bundled Noto Sans has a checked SHA-256 and SIL font license. pypdf 6.19.0 and PyMuPDF 1.28.2 are development-only extraction/rendering tools. No browser renderer or hosted reporting service is used.
- Phases 8–9: the authorized internal website uses the pinned React/Vite/TypeScript stack recorded below and its pnpm lockfile. Inspect the separately supplied landing page/design when it arrives before integrating it.
- Phase 13: select and test a supported HTTP client for Meta calls with real timeouts, redirect policy and bounded response bodies. The current HTTPX2 installation is a development dependency, not a provider adapter.

Pandas, an AI service, a messaging aggregator and an external queue are not required for the deterministic core. Optional packages need a concrete implemented use and compatibility proof.

## Local installation and launch

From PowerShell on this PC:

```powershell
Set-Location 'C:\Users\yashk\Downloads\gstshield\backend'
..\.tooling\Scripts\uv.exe sync --frozen
if (!(Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage user-create --username demo-owner --workspace 'Demo Workspace'
..\.tooling\Scripts\uv.exe run --frozen python -m app
```

The account command prompts privately for a chosen password and confirmation. There is no shipped default account/password. It prints the new user/workspace IDs. Stop the backend before account changes or backup/restore maintenance.

Teammates install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use `uv sync --frozen` and `uv run --frozen ...` from backend/. The ignored .tooling directory is this PC's convenience installation; it is not a requirement to commit a runtime or share a virtual environment.

Use `python -m app` through the locked environment. The launcher honors validated HOST/PORT, uses one worker, disables URL access logs and does not trust proxy headers. A direct alternate Uvicorn command can invalidate these guarantees; do not use the old cloud start command.

Liveness is /health/live. Readiness is /health/ready and includes a local storage query. Developer docs/schema are enabled in local/test and hidden in demo. A healthy response does not certify GST calculations or future phone/report features.

## Browser connectivity

Default website origin: http://localhost:3000. Default API origin: http://localhost:8000. Different ports are allowed; both must use the same HTTP hostname for SameSite=Strict cookies. Do not mix localhost with 127.0.0.1 in the browser's chosen API base URL.

If choosing IPv4 literals, change PUBLIC_WEB_URL and PUBLIC_API_URL together and include the exact website origin in CORS_ORIGINS. If changing API port, change PORT and PUBLIC_API_URL together. IPv6 binding uses ::1 and matching website/API hostname configuration.

The API currently binds only to loopback. A separately hosted website cannot reach a private PC backend from an arbitrary remote browser. LAN access, public HTTPS and a phone callback require a later deliberate connectivity decision; no tunnel is provisioned in Phase 2.

The future API client uses credentials:include, not a JavaScript-held access token. It recovers session/CSRF state through GET /api/v1/auth/session and includes X-CSRF-Token plus Origin on authenticated mutations. Details are authoritative in 08.

## Local persistence and recovery

The database is backend/data/gstshield.sqlite3. Settings allow a nested directory only within backend/data. The process holds an OS lock; a second runtime or maintenance process is refused. Symlinks, junctions, traversal and non-ordinary private storage entries are rejected.

SQLite uses STRICT tables, foreign keys, DELETE journaling, FULL synchronization and short explicit transactions. A new file is created exclusively. Existing empty, corrupt, foreign, changed or unsupported-version databases are refused and preserved; runtime reads never silently recreate a missing live file.

Data persists across backend restarts. Session expiry is absolute, normally 30 minutes, with no sliding refresh. A new login replaces the previous session for that account. Expiry is checked in the backend independently of the cookie lifetime.

Backup commands copy the actual database and validate the result; Phase 3 sources are private SQLite BLOBs, so source bytes, preview rows, context and job history are included atomically. Generated UUIDs identify backups. Backup count, total retained bytes, database page limits and free-disk reserve are enforced. Archive an old backup outside the private directory before filling the backup budget.

```powershell
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage backup
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage restore --backup-id '<printed UUID>'
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage password-reset --username demo-owner
```

Restore preserves the previous database, validates/stages the chosen backup, removes restored sessions/request windows, disables restored accounts, and replaces the live database. Review memberships and reset the passwords of intended users before launch. This prevents a backup from silently reactivating old revoked credentials.

An unresolved journal/WAL/SHM sidecar blocks restore; retain it for operator recovery rather than deleting evidence. Phase 3 source uploads are inside the database and need no second file manifest. Phase 5 stores generated artifact bytes and immutable snapshots in SQLite, so the existing offline backup preserves reports together with cases, proposals and their job history. No separate report directory or manifest restore is required.

## Environment contract

`backend/.env.example` is the complete recognized template. OS settings override dotenv values; unknown OS names are ignored, unknown/malformed/duplicate dotenv settings are refused. No secret values are printed in configuration failures.

The table below is generated from the template for this planning update. Blank Meta values are deliberate: WhatsApp remains disabled. Storage, sessions, request limits and Phase 3 upload/parser boundaries are enforced. Report and action limits are implemented; linking/provider settings remain reservations until Phase 13.

| Variable | Example default |
|---|---|
| `APP_ENV` | `local` |
| `DEMO_MODE` | `true` |
| `LOG_LEVEL` | `INFO` |
| `HOST` | `127.0.0.1` |
| `PORT` | `8000` |
| `PUBLIC_WEB_URL` | `http://localhost:3000` |
| `PUBLIC_API_URL` | `http://localhost:8000` |
| `CORS_ORIGINS` | `["http://localhost:3000","http://127.0.0.1:3000"]` |
| `STORAGE_BACKEND` | `sqlite` |
| `LOCAL_DATA_DIR` | `data` |
| `WEB_CONCURRENCY` | `1` |
| `SESSION_TTL_SECONDS` | `1800` |
| `MEMORY_STATE_MAX_BYTES` | `67108864` |
| `MAX_ACTIVE_DEMO_SESSIONS` | `20` |
| `MAX_CONCURRENT_PROCESSING_JOBS` | `1` |
| `MAX_QUEUED_JOBS_PER_WORKSPACE` | `5` |
| `MAX_IMPORTS_PER_WORKSPACE` | `20` |
| `MAX_PARSED_IMPORT_BYTES` | `16777216` |
| `MAX_PARSER_RSS_BYTES` | `268435456` |
| `MAX_UPLOAD_RECEIVE_SECONDS` | `20` |
| `MAX_UPLOAD_BYTES` | `5242880` |
| `MAX_IMPORT_ROWS` | `2000` |
| `MAX_IMPORT_COLUMNS` | `50` |
| `MAX_CELL_CHARACTERS` | `10000` |
| `MAX_JSON_DEPTH` | `20` |
| `MAX_XLSX_UNCOMPRESSED_BYTES` | `52428800` |
| `MAX_XLSX_ARCHIVE_ENTRIES` | `1000` |
| `PROCESSING_TIMEOUT_SECONDS` | `60` |
| `CURRENCY` | `INR` |
| `MATCH_AMOUNT_TOLERANCE` | `0.01` |
| `FUZZY_SUGGESTION_THRESHOLD` | `88.00` |
| `FUZZY_MIN_SCORE_GAP` | `5.00` |
| `MATCH_POLICY_VERSION` | `match-v1` |
| `MAX_RUNS_PER_WORKSPACE` | `20` |
| `MAX_MATCH_PAIRS` | `4000000` |
| `MAX_MATCH_CANDIDATES` | `10000` |
| `WHATSAPP_ENABLED` | `false` |
| `META_GRAPH_VERSION` | `` |
| `META_PHONE_NUMBER_ID` | `` |
| `META_WABA_ID` | `` |
| `META_ACCESS_TOKEN` | `` |
| `META_APP_SECRET` | `` |
| `META_VERIFY_TOKEN` | `` |
| `WHATSAPP_SEND_BUDGET` | `0` |
| `HTTP_CONNECT_TIMEOUT_SECONDS` | `5` |
| `HTTP_READ_TIMEOUT_SECONDS` | `20` |
| `HTTP_WRITE_TIMEOUT_SECONDS` | `20` |
| `HTTP_POOL_TIMEOUT_SECONDS` | `5` |
| `LINK_CODE_TTL_SECONDS` | `600` |
| `LINK_ATTEMPTS_PER_WINDOW` | `5` |
| `LINK_ATTEMPT_WINDOW_SECONDS` | `600` |
| `DOWNLOAD_CAPABILITY_TTL_SECONDS` | `600` |
| `DOWNLOAD_CAPABILITY_MAX_DOWNLOADS` | `3` |
| `READ_REQUESTS_PER_MINUTE` | `60` |
| `MUTATION_REQUESTS_PER_MINUTE` | `10` |
| `IMPORT_REQUESTS_PER_MINUTE` | `3` |
| `MAX_DATABASE_BYTES` | `67108864` |
| `MAX_LOCAL_DATA_BYTES` | `268435456` |
| `MIN_FREE_DISK_BYTES` | `16777216` |
| `MAX_LOCAL_BACKUPS` | `3` |
| `MAX_LOCAL_USERS` | `20` |
| `MAX_LOCAL_WORKSPACES` | `20` |
| `MAX_REGISTRATIONS_PER_WORKSPACE` | `20` |
| `MAX_API_BODY_BYTES` | `65536` |
| `MAX_API_RECEIVE_SECONDS` | `20` |
| `MAX_CASES_PER_WORKSPACE` | `100` |
| `MAX_CASE_EVENTS` | `100` |
| `MAX_PROPOSALS_PER_WORKSPACE` | `20` |
| `MAX_ARTIFACTS_PER_WORKSPACE` | `40` |
| `MAX_ARTIFACT_BYTES` | `5242880` |
| `MAX_REPORT_SNAPSHOT_BYTES` | `8388608` |
| `ARTIFACT_TTL_SECONDS` | `604800` |
| `MAX_REPORT_ROWS` | `200` |
| `MAX_REPORT_PAGES` | `100` |
| `MAX_ACTIONS_PER_WORKSPACE` | `3000` |
| `MAX_ACTION_EVENTS` | `100` |
| `AUTOMATION_INTERVAL_SECONDS` | `5` |
| `AUTOMATION_SOURCE_BATCH` | `8` |
| `AUTOMATION_DUE_BATCH` | `50` |

## Enforced current resource policy

- Database: 64 MiB; all private data: 256 MiB; free-disk reserve: 16 MiB.
- Backups: three retained files, including preserved recovery copies counted toward the same directory budget.
- Accounts/workspaces: twenty each; registrations: twenty per workspace; absolute configured upper bounds keep lists finite.
- Active sessions: twenty; one active session per account; session lifetime at most one day even if configured above the demo default.
- Small mutation bodies: 64 KiB actual streamed bytes; malformed duplicate Content-Length is rejected.
- Sign-in: five attempts per username per minute and thirty globally; one scrypt hash computation at a time.
- Private requests: sixty reads and ten mutations per session per minute, stored in SQLite across restart.
- SQL lock waiting: bounded to two seconds; failure is a truthful storage error, never successful empty data.

These bounds are hackathon choices. Phase 11 measured the fixed demo/maximum workloads and retained them; see 05 for budgets and capacity limits. Uploads have their own authenticated streaming boundary: 5 MiB file plus 64 KiB multipart envelope, one upload reception at a time and a 20-second receive deadline. Other mutation bodies remain 64 KiB. The dispatcher admits five queued/running jobs per workspace and runs one parser globally; twenty imports per workspace and 1,000 remembered operations per workspace bound history.

## Checks and evidence

```powershell
..\.tooling\Scripts\uv.exe sync --frozen
..\.tooling\Scripts\uv.exe run --frozen ruff check .
..\.tooling\Scripts\uv.exe run --frozen ruff format --check .
..\.tooling\Scripts\uv.exe run --frozen python -m compileall -q app
..\.tooling\Scripts\uv.exe run --frozen pytest -q
```

The GitHub workflow uses Windows/Linux test runners; Ubuntu in CI is a verification environment, not a deployed server. Local test success and remote workflow results are separate evidence. Record failures and fixes rather than declaring unrun checks green.

The current project is a website, not a native phone app. Real WhatsApp is Phase 13 and needs Meta assets, internet connectivity, an HTTPS callback and account-specific entitlement checks. Do not promise zero messaging cost merely because local backend/storage has no hosting bill.

## Technical references

Python documents SQLite connections, bound SQL and backup APIs in the [Python 3.13 sqlite3 reference](https://docs.python.org/3.13/library/sqlite3.html). STRICT table behavior is defined by [SQLite](https://www.sqlite.org/stricttables.html). Current access choices and their limits are explained in 06 and implemented in the backend; these references do not certify the entire app.


## Phase 3 process and schema decision

Imports run in one disposable local Python process, scheduled by one backend thread. The thread only claims work, monitors the child and publishes a short database transaction. Parsing never holds a write transaction. The child reads one bound source ID from readonly SQLite and receives only its server-built descriptor. A generated private descriptor file is limited to 64 KiB so feeding startup cannot block the watchdog. Its result is a generated private temporary file limited to 16 MiB; it is removed after publication, cancellation or restart cleanup.

The watchdog checks a 60-second deadline and combined process-tree RSS against 256 MiB. RSS is sampled, so this is not a hard Windows kernel memory allocation limit. Windows virtual-environment launchers can spawn a second interpreter; both memory accounting and termination include that process tree. This is resource isolation, not a full operating-system security sandbox. Sources remain private to the OS user running the hackathon backend.

Schema version 2 adds import_files, imports, import_rows, jobs, import_operations and import_events. Startup preserves and refuses an old schema rather than silently changing it. For a valid Phase 2 database, stop the backend and run `python -m app.manage storage-upgrade` from backend/. It validates the exact old schema, saves a generated backup, then adds the import tables in one transaction. The preserved v1/v2 backups remain old-version recovery evidence. Phase 4 now initializes v3 and current restore accepts v3 backups. Recovering an older backup requires offline recovery plus the validated storage-upgrade command before launch.

Rename the old unused `MAX_QUEUED_JOBS_PER_SESSION` dotenv entry to `MAX_QUEUED_JOBS_PER_WORKSPACE`. It now limits actual workspace jobs. Old dotenv keys are deliberately refused rather than silently ignored; the complete current template is above and in backend/.env.example.

The XML defense follows [openpyxl's security guidance](https://openpyxl.readthedocs.io/en/stable/): defusedxml is installed, and archive/XML inspection runs before workbook parsing. [python-multipart](https://pypi.org/project/python-multipart/) handles the bounded multipart envelope. Process-tree RSS uses [psutil's process API](https://psutil.io/api/). Installed 7.x is pinned below 8 to avoid introducing the documented breaking 8.x API changes.

## Phase 4 runtime and schema alignment

Phase 4 introduced schema v3; active fresh storage is now schema v5. Offline `python -m app.manage storage-upgrade` validates exact v1/v2/v3/v4 fingerprints, preserves a compatible old-version backup and adds only missing tables. It does not rebuild or overwrite imported files. Startup refuses older schemas until this explicit upgrade runs. Current restore accepts v5 backups; older preservation backups remain recovery evidence requiring compatible offline recovery plus upgrade. One dispatcher runs imports, reconciliation and reports serially in disposable children, with the same 60-second deadline, 16 MiB output and sampled 256 MiB process-tree RSS bound. No second worker, DB service or cloud integration was introduced.

The installed similarity API was checked against [RapidFuzz ratio documentation](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) on 2026-10-03. Use normalized Indel ratio with explicit invoice preprocessing; no token/subset scorer. Threshold comparisons floor scores to two decimal places, while the minimum score gap uses unrounded scores to avoid rounding up confidence. This is a server-versioned comparison policy, not a probability.

## Phase 5 operational choices

Artifact generation runs offline in the existing killable child, sharing the import/run admission limit, processing timeout, output bound and sampled process-tree RSS guard. Report snapshots are capped at 8 MiB, generated bytes at 5 MiB, PDF pages at 100 and reconciliation detail rows at 200. Base64 IPC must fit MAX_PARSED_IMPORT_BYTES; startup checks that relationship. SQLite owns both report bytes and metadata, so rollback, restart and offline backups retain one consistent authority.

Schema 4 preserves v1/v2/v3 fingerprints. For an existing older store, stop the backend and run `uv run --frozen python -m app.manage storage-upgrade`; it validates and backs up the old store before adding only the missing tables. Phase 5 created schema 4; fresh installations now create schema 5 directly. No external database migration or provider account is involved.

The font's glyph coverage is checked before rendering. Unsupported text produces FAILED / REPORT_UNSUPPORTED_TEXT, never a PDF with silently missing characters. Latin/Greek/Cyrillic and the rupee sign are covered; arbitrary Indic scripts or emoji are not promised. CSV remains UTF-8. Dependency source: [ReportLab on PyPI](https://pypi.org/project/reportlab/); font source/license/hash live in backend/app/assets/README.md.


## Phase 6 business workflow infrastructure boundary

The newly scheduled business actions, recorded-date reminders and snapshot-change review use the existing local Python/SQLite architecture. Phase 6 requires bounded automatic due-review checks while the backend runs, startup catch-up and authenticated due queries; no hosted scheduler, government API, external database or messaging SDK is implicitly selected. Reminders are unavailable while the PC/backend is off, and restart must show overdue work without replaying external sends. Add dependencies or validated environment settings only if actual implementation needs them; align the lock and example in that phase. The implemented monitor uses only the standard library; no new dependency was added.


Current scope/status is reconciled in the [capability ledger in 05](05_BUILD_AND_VERIFICATION_PLAN.md#capability-status-and-remaining-work-ledger). Phase 6 now has local business-action APIs, automatic deduplicated evidence-change and due-review tracking, private follow-up drafts/history, a review worksheet and separately evidenced user-recorded filing/submission observations. Browser presentation/connection remains 8–9 and conditional WhatsApp delivery remains 13. Automatic fetching, government filing and legal decision integrations are deferred; guaranteed recovery is not a software promise.


## Phase 6 implemented local operating settings

Schema 5 adds only the business-action layer; schema 1–4 fingerprints remain unchanged. An existing schema 1/2/3/4 database must be upgraded offline with `python -m app.manage storage-upgrade`. The command validates and preserves the previous version before its additive transaction. Fresh storage creates version 5; ordinary restore accepts version 5 backups. Earlier backups remain recovery evidence requiring compatible offline recovery and upgrade. Never delete a store to bypass this check.

The `ActionMonitor` uses a standard-library thread alongside the existing disposable import/run/report worker; it never parses files or contacts a provider. Defaults are `AUTOMATION_INTERVAL_SECONDS=5`, `AUTOMATION_SOURCE_BATCH=8`, `AUTOMATION_DUE_BATCH=50`, `MAX_ACTIONS_PER_WORKSPACE=3000`, `MAX_ACTION_EVENTS=100`. Every setting has strict numeric bounds and appears in the example. One workspace is checked per tick with round-robin selection. At the maximum twenty workspaces, a scan round can take at least 100 seconds; a backlog needs further rounds. These are bounded checks, not instantaneous delivery guarantees. Authenticated action reads also request bounded catch-up.

Per-source derivation commits or rolls back atomically. A failed source remains pending with a private error code, and rotates behind other pending sources. Stale/full-history due items do not block independent reminders. Due events are emitted once per recorded UTC review date; explicitly change the date to schedule another event. No event claims that a message was sent. The monitor cannot run while the PC/backend is off; startup catches up bounded work. Finite retained history is not silently deleted or reset to make quota errors disappear.


## Verification cost and batch cadence

Uninterrupted full Windows Phase 6 runs took roughly eleven to sixteen minutes; the final passing run took 951.44 seconds (15 minutes 51 seconds); machine sleep can inflate wall-clock reports dramatically. Use targeted phase checks plus lint/format/syntax while implementing, then one full regression after two or three related phases. Major shared storage/authentication/calculation changes or an uncontained regression warrant an earlier full run. See 05 for the recorded user decision. Do not describe an interrupted/failed run as passing evidence.

## Internal website stack added in Phase 8

React/DOM 19.3.0, Vite 8.3.2, React plugin 6.1.1 and TypeScript 7.0.2 are pinned in frontend/package.json and pnpm-lock.yaml. Node 24.19.0 and pnpm 11.19.0 were used for the verified install/build. Playwright 1.63.0 and Prettier 3.9.9 are development tools. No UI framework, remote fonts, cloud API client or external database is required. `.env.example` contains optional public `VITE_API_BASE_URL`; browser and backend must use the same HTTP loopback hostname. Screens call the actual private API contracts. Official stack references: [React release](https://react.dev/blog/2026/09/09/react-19-3), [Vite runtime requirements](https://vite.dev/guide/). Published npm registry metadata/peer requirements were checked before pinning. Final frontend audit returned zero known advisories for 72 dependency entries on 2026-10-04; that is a time-bound database result.


## Phase 11 local performance evidence

The implemented local stack remains Python/SQLite plus the existing disposable processing child.
No dependency, external service, environment setting or storage schema changed. The final real
loopback workload completed eight runs, six private PDFs, every expected retained action and all
health probes without a 503. Recorded timings, hardware, source hashes and local acceptance
budgets are in 05 and `backend/benchmarks/results/after.json`.

Measured optimizations use existing workspace-leading indexes, short database snapshots before
CPU work, actual readonly connections for read transactions, per-call invoice normalization and
compact report presentation. SQLite DELETE journaling, FULL write synchronization, schema 5,
exclusive process ownership, exact money, source/lease checks and finite histories remain.
The single worker and shared queue budgets have not been increased. Full backend process-tree
RSS measured about 175.7 MiB at peak; that observation is distinct from the enforced sampled
256 MiB processing-child tree limit.

Eight maximum/repeated stress runs retain about 51.5 MiB in the default 64 MiB database. Retention
is deliberate and can exhaust byte capacity before the run-count quota. Keep backups and use
existing reviewed maintenance; performance changes never silently discard earlier sources,
actions, events or reports. This measurement covers fixed synthetic CSV distributions, not every
5 MiB input or production concurrency. Browser performance remains Phase 12.


## Phase 12 website performance verification — 2026-10-04

The installed pinned stack and both lockfiles remain unchanged. The built website was profiled against the actual isolated local API with 100 and 2,000 invoices; all local interaction, processing, download and retained-JS-heap budgets passed. Baseline and final synthetic measurements and repeatable instructions live in frontend/benchmarks. This introduces no additional service, database, package or deployment requirement. Startup/navigation stayed broadly similar; the principal improvements are preserving same-context forms/filters and reducing unnecessary polling/rendering. See 05 for measured values and limits.


## Phase 13 current configuration — 2026-10-04

Local WhatsApp integration uses the existing Python standard-library HTTPS/TLS transport, SQLite and one bounded channel thread. No package/lockfile, cloud, external database or tunnel is added. Schema 6 requires explicit offline `python -m app.manage storage-upgrade` with backup validation; no presenter database was modified. The browser still uses only VITE_API_BASE_URL. META_* credentials remain backend-only.

WHATSAPP_ENABLED defaults false; WHATSAPP_PUBLIC_URL is an approved exact HTTPS origin for channel routes only. WHATSAPP_SEND_BUDGET defaults zero and limits cumulative send attempts, including failed/unknown attempts. It is not a monetary cap. Keep disabled/zero until actual account/assets, supported Graph version, token permissions, allowed recipient and callback setup are verified. The user has no Meta setup yet. Real delivery and current price entitlement are pending. See 05 for verification gaps.
