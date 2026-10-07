# GSTShield local backend

## Active scope

Decision: 2026-10-03. Run the hackathon website backend on the local PC. No Render, cloud server, external database, cloud storage, Redis or hosted identity setup. A local backend process is still required for the website to call Python functionality.

Phase 1 provides the HTTP/configuration foundation. Phase 2 adds local SQLite storage, operator provisioned accounts, revocable browser sessions and scoped workspace/registration reads. Phases 1–2 are complete. Phase 3 private uploads, previews, mapping, confirmation and import jobs are complete and locally verified. Phase 4 reconciliation, saved results and human review are complete and locally verified. Phase 5 cases, proposals and private reports are complete and locally verified. Phase 6 retained actions, local reminders and six-problem workflows are complete and locally verified. Phone routes remain Phase 13.

The [phase plan](../md/05_BUILD_AND_VERIFICATION_PLAN.md) defines the local architecture; the eight MDs now use this decision throughout. Work proceeds one phase at a time, with a review gate before the next phase.

## Start on this PC

From PowerShell:

```powershell
Set-Location 'C:\Users\yashk\Downloads\gstshield\backend'
..\.tooling\Scripts\uv.exe sync --frozen
if (!(Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
..\.tooling\Scripts\uv.exe run --frozen python -m app
```

The ignored `.tooling/` directory contains this PC's isolated uv installation. Teammates install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use `uv sync --frozen` / `uv run --frozen python -m app` from `backend/`. Python 3.13.16 is selected by `.python-version`; uv can obtain that runtime. Do not use the PC's unrelated Python 3.14 interpreter for this project.

Open [liveness](http://127.0.0.1:8000/health/live), [readiness](http://127.0.0.1:8000/health/ready) or [local API docs](http://127.0.0.1:8000/docs). Stop the process with Ctrl+C. Start the internal website with the frontend README instructions; the configured website origin defaults to localhost:3000. Keep browser and API on the same hostname.

Use the supported launcher rather than an independent Uvicorn command that overrides HOST/PORT/workers or enables access logs. It reads the checked configuration and deliberately uses one worker, no reload, no proxy-header trust and no URL access logging.

If port 8000 is occupied, set both `PORT` and `PUBLIC_API_URL` to the same new port in `.env`. Only loopback HOST values 127.0.0.1 and ::1 are accepted. For ::1, use an IPv6 or localhost API origin. There is no configured HTTPS listener, so the local API URL uses HTTP.

## Implemented endpoints

| Route | Behavior |
|---|---|
| GET /health/live | HTTP process can answer; returns status=ok |
| GET /health/ready | Startup complete and local SQLite query succeeds; returns status=ready |
| POST /api/v1/auth/login | Origin-checked local sign-in; sets HttpOnly session cookie |
| GET /api/v1/auth/session | Recover identity, expiry and CSRF token from the cookie |
| POST /api/v1/auth/logout | Origin/CSRF-protected session revocation and cookie deletion |
| GET /api/v1/workspaces | Current account's active memberships only |
| GET /api/v1/workspaces/{workspace_id}/registrations | Registrations within a currently permitted workspace |
| POST /api/v1/workspaces/{workspace_id}/imports | Authenticated, bounded multipart upload and durable parse job |
| GET /api/v1/workspaces/{workspace_id}/imports | Scoped paginated import history and context filters |
| GET /api/v1/workspaces/{workspace_id}/imports/{id} | Private state/version/mapping/counters/errors |
| GET /api/v1/workspaces/{workspace_id}/imports/{id}/rows | Paginated original/canonical rows and rejection reasons |
| PATCH /api/v1/workspaces/{workspace_id}/imports/{id}/mapping | Version-checked derived mapping preview |
| POST /api/v1/workspaces/{workspace_id}/imports/{id}/confirm | Explicit partial/supersession acknowledgement |
| GET /api/v1/workspaces/{workspace_id}/jobs/{id} | Authorized parse job state |
| GET /docs | Developer API documentation in local/test mode |
| GET /openapi.json | Schema in local/test mode |

Readiness returns 503 before startup/after shutdown. It checks SQLite availability, but does not claim import readiness, GST correctness or WhatsApp availability. Developer docs/schema are disabled in APP_ENV=demo; this mode still runs locally.

Health successes use `data` and `meta.request_id`. Application errors use `error.code/message/details/retryable` and `meta.request_id`. Each HTTP request receives a server-generated ID also returned in X-Request-ID; client-supplied IDs are not trusted.

Framework documentation, OpenAPI and CORS preflight retain their standard protocol formats. These are not private application JSON endpoints.

## Configuration contract

[.env.example](.env.example) defines every recognized environment variable and provides safe local defaults. Configuration loads backend/.env regardless of the shell's working directory; OS variables take precedence. Unrelated OS variables are ignored. Unknown dotenv names, malformed syntax and duplicate keys are rejected.

Implemented validation includes:

- True/false booleans and integer values without boolean/fractional coercion.
- Port range, a single worker/job executor and positive resource limits.
- Exact finite Decimal amounts/scores and at most two decimal places for money tolerance.
- Exact local website/API origins without credentials, wildcard, path, query or fragments.
- CORS duplicates and website-origin/API port/binding alignment.
- Local-data path containment under backend/data.
- Cross-field upload/buffer/decompression and suggestion-score limits.
- Optional Meta configuration completeness with masked secrets.

Startup configuration failures print a sanitized message and exit with code 2. Never print the settings object/model_dump, raw validation errors or environment values.

Storage, session, private request-rate and small streamed-body limits are enforced in Phase 2. Phase 3 enforces upload/parser limits; linking/download/provider limits remain reservations until their features are implemented. WHATSAPP_ENABLED must remain false: even complete provider configuration cannot activate an unfinished integration.

## Current HTTP safeguards

The launcher binds to loopback. The HTTP boundary rejects non-local Host values and duplicate Host/Origin headers. Requests carrying an unapproved Origin are rejected before routes run. CORS permits exact configured origins, GET/POST/PATCH, Content-Type, X-CSRF-Token and Idempotency-Key, with credentials enabled. The website/API must use the same HTTP hostname for SameSite=Strict cookies, such as localhost on ports 3000/8000.

Security/no-store headers and request IDs cover successful and failed HTTP responses. Unexpected errors return a generic message; logging keeps the request ID and exception class rather than the private exception contents. The outer boundary prevents the framework's completed 500 response from causing Uvicorn to log the original exception again. Partially sent responses abort with a sanitized failure.

Host/Origin controls complement the current session and membership checks; they do not grant access on their own. DEMO_MODE is a sample-data flag and never an authentication bypass.

Small mutation bodies are bounded by actual streamed bytes before JSON parsing. Phase 3 upload routes authenticate and check workspace write permission before receiving their separately bounded multipart body. The default file limit is 5 MiB plus 64 KiB envelope overhead.

## Local storage decision

Phase 2 keeps accounts, scopes and sessions in backend/data/gstshield.sqlite3. Phase 3 source bytes and preview rows are stored privately inside this database; Phase 5 report artifacts are also private SQLite BLOBs with immutable source snapshots. Browser localStorage may hold harmless UI preferences; it will not own financial records, access authority or reconciliation results.

Committed records and unexpired sessions survive normal backend restarts. Explicit transactions, parameterized SQL, STRICT tables, foreign keys, schema validation, an OS process lock and storage quotas protect the implemented local flow. Existing incompatible/corrupt files are refused and preserved. Local data/backups are not encrypted; Windows file access follows the local OS account permissions.

The database/data directory, dotenv credentials and tooling are ignored by Git. Keep real taxpayer documents out of the public repository and use synthetic fixtures for development.

## Phase plan and status

| Phase | Work | Status |
|---|---|---|
| 1 | Local runtime and HTTP foundation | Complete |
| 2 | Local storage and private access | Complete |
| 3 | File imports, checking and confirmation | Complete and locally verified |
| 4 | GST reconciliation and human review | Complete and locally verified |
| 5 | Backend reports, cases and evidence workflow | Complete |
| 6 | Business workflows for all six original problems | Not started |
| 7 | Backend security and failure review | Not started |
| 8 | Frontend inspection, cleanup and complete screens | Not started |
| 9 | Frontend and backend connection | Not started |
| 10 | Frontend security and privacy review | Not started |
| 11 | Backend performance and resource efficiency | Complete and locally verified |
| 12 | Frontend smoothness, speed and usability | Not started |
| 13 | WhatsApp connection and channel review | Local implementation; verification/provider gates pending |
| 14 | Whole-application regression and hackathon rehearsal | Not started |

The expanded plan has 14 phases covering the whole application. Every phase has correctness, security, edge-case and integration gates in the build plan. Baseline security/resource controls remain part of each feature; Phases 7 and 11 provide focused backend security/failure and measured performance reviews. Frontend phases give the internal website equal attention; the separately supplied landing page/design is later work. The dependency order does not reduce attention to later work.

Real WhatsApp needs Meta's API and an internet-reachable HTTPS callback. A purely offline/loopback backend cannot receive real phone callbacks. No tunnel or hosted service is provisioned. This decision belongs to the later integration phase.

## Verified runtime and dependencies

The full resolved dependency graph and hashes are in `uv.lock`. Actual Phase 1 versions:

| Item | Version |
|---|---|
| CPython | 3.13.16 |
| uv used locally | 0.12.22 |
| FastAPI / Starlette | 0.142.2 / 1.7.0 |
| Pydantic / Pydantic Settings | 2.13.5 / 2.15.0 |
| python-dotenv / Uvicorn | 1.2.4 / 0.54.0 |
| HTTPX2 test client | 2.13.1 |
| pytest / Ruff | 9.1.1 / 0.16.10 |

HTTPX2 is the installed Starlette version's supported test-client dependency; the deprecated HTTPX dependency was removed. Parser/report/matching libraries are added only when used in their phases. Do not silently upgrade the lock during a presentation.

## Phase 1 verification record

Local Windows checks on 2026-10-03:

- Installed/resolved the project in a fresh Python 3.13 environment; frozen sync subsequently passed.
- 78 tests passed, including a real local process/socket startup and sanitized invalid-startup exit.
- Ruff lint and formatting checks passed.
- Python syntax compilation passed.
- Config/template drift, environment precedence, bounds, malformed/duplicate dotenv entries and redaction checked.
- Lifespan readiness, errors, malformed JSON, CORS, Host/Origin checks, schema behavior and failure-log redaction checked.
- Failures before a response and after a partial response checked without leaking exception contents.

Repeat from backend/:

```powershell
..\.tooling\Scripts\uv.exe sync --frozen
..\.tooling\Scripts\uv.exe run --frozen ruff check .
..\.tooling\Scripts\uv.exe run --frozen ruff format --check .
..\.tooling\Scripts\uv.exe run --frozen python -m compileall -q app
..\.tooling\Scripts\uv.exe run --frozen pytest -q
```

GitHub checks use the same frozen install, lint, format, syntax and tests on Windows/Linux runners. This is automated verification, not application hosting. Local success is not proof that a remote workflow has already passed.

## Folder responsibilities

| Folder | Responsibility |
|---|---|
| app/api | Current access/workspace routes; future feature routes |
| app/contracts | Shared HTTP/input/output contracts |
| app/domain | Exact canonical validation and reconciliation policy |
| app/services | Local account/session access now; future shared feature use cases |
| app/adapters | Future import/report/provider boundaries |
| app/storage | Current SQLite, data locking, quota, backup/restore foundation |
| app/jobs | Future bounded local processing |
| app/security | Host/Origin/security headers and streamed body boundary; upload/callback checks later |
| tests/unit | Configuration and HTTP-boundary regressions |
| tests/integration | API lifecycle, real process startup and failure behavior |
| tests/fixtures | Reserved for clearly labeled synthetic input/expected results |

Phase 3 private imports, previews, mapping, confirmation and job endpoints are implemented. Phase 4 reconciliation/review is implemented; Phase 5 reports/cases/proposals are complete and locally verified; Phase 6 is complete and locally verified; Phase 7 security checks and Phases 8–9 internal website integration are implemented/verified; Phases 10–11 are now complete; Phases 12–14 remain ahead.

## Create local accounts and context

Stop the backend before operator commands. There are no seeded credentials or public registration route. The new account command creates a private workspace and OWNER membership atomically:

```powershell
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage user-create --username demo-owner --workspace 'Demo Workspace'
```

Choose/confirm a 12–128 character password through the private terminal prompt. The command prints user/workspace IDs. Do not put passwords in terminal command arguments, screenshots or Git. Add a synthetic registration using the printed workspace UUID:

```powershell
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage registration-create --workspace-id '<workspace UUID>' --gstin '27ABCDE1234F1Z5' --name 'Synthetic Demo Registration'
```

The example GSTIN is synthetic, structurally formatted and not government-verified. Phase 2 does not verify taxpayer existence, checksum, filing status or ITC eligibility.

Each additional account gets its own workspace. Grant/revoke a membership through offline administration when sharing a team workspace:

```powershell
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage membership-set --username teammate --workspace-id '<workspace UUID>' --role REVIEWER
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage membership-set --username teammate --workspace-id '<workspace UUID>' --role REVIEWER --revoke
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage password-reset --username demo-owner
```

Offline administration has the local operator's filesystem authority. It is not a public API or a browser role bypass. Every website resource query still checks current active membership and session state. Password reset revokes prior sessions.

## Website access contract

The internal website uses this implemented API flow: POST /api/v1/auth/login with JSON username/password and Origin, GET /api/v1/auth/session after reload, then workspace/registration reads. Use credentials:include in the browser client. The HttpOnly cookie is never copied to JavaScript storage.

Session JSON carries user_id, username, expires_at and csrf_token. Hold CSRF in memory and attach X-CSRF-Token plus the configured Origin to logout and later private mutations. A 401 requires sign-in; a 429/503 follows Retry-After with a bounded retry policy. Current lists are finite from provisioned scope limits; future financial lists paginate.

Use localhost consistently on the browser's website/API URLs. CORS alone cannot fix a SameSite cookie blocked by mixing localhost and 127.0.0.1. The configuration loader now checks this alignment. Current HTTP cookies intentionally lack Secure because the backend is a loopback HTTP listener; reachable HTTPS is a later separate integration decision.

There is one active session per account. Sign-in again replaces it; tabs in the same browser share the cookie. Expiry is absolute, normally 30 minutes. Logout deletes the SQLite session, not just the browser cookie. No refresh-token or JWT service is used.

## Offline backup and recovery

With the backend stopped:

```powershell
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage backup
..\.tooling\Scripts\uv.exe run --frozen python -m app.manage restore --backup-id '<printed backup UUID>'
```

Backups live in backend/data/backups and contain private account hashes/data. Only generated UUIDs are accepted for restore. The default budget permits three backup/recovery files; archive an old file safely outside private storage before filling it. Restore needs space/count budget to preserve the current database, including a corrupt file.

Restore validates/stages the backup, preserves the old database, clears sessions/request windows, disables restored accounts, and replaces the live file. Review memberships and reset passwords for intended users before reopening access. An old password/session must not silently regain access from a historical backup.

Existing unresolved journal/WAL/SHM files prevent restore; preserve them for operator recovery. Normal SQLite journaling handles interrupted transactions; do not delete a sidecar to bypass recovery. Unknown schema versions require a reviewed upgrade or supported backup, not deletion/recreation.

This backup covers source BLOBs, import context, previews, run/results/candidates, review history, job state and access records together. Phase 5 cases/evidence, proposals/history, generated report BLOBs/snapshots and artifact jobs are included in this same SQLite backup.

## Phase 2 verification record

Local Windows verification on 2026-10-03: **118 passed, 1 skipped** in the complete Phase 1 + Phase 2 suite. Frozen sync, Ruff lint/format, syntax compilation and diff checks passed. The skipped test requires Windows symlink privilege; the separate actual Windows junction denial test passed. Focused tests cover two identities, session/CSRF/role boundaries, persistent limits, actual process restart, offline backup/restore, preserved corrupt/foreign/future-schema files, SQL rollback and disk/database quotas. The real restart test exercises the same Phase 1 launcher and HTTP boundary with Phase 2 accounts/scoped reads.

The Windows symlink creation check may skip when Developer Mode/privilege is unavailable; a separate Windows junction check exercises the reparse-point denial without that privilege. Linux CI exercises symlinks when available. Remote workflow results remain separate evidence.


## Phase 3 local imports

Use the existing local account and workspace registration. POST multipart `/api/v1/workspaces/{workspace_id}/imports` with `file`, `kind`, `registration_id`, `period`, `adapter_version`, and optional `sheet_name`, JSON `mapping`, `supersedes_import_id`. Mutations require Origin, the session's X-CSRF-Token and a unique UUID Idempotency-Key. Keep that same key when retrying the same intended action.

Supported adapters:

| Adapter | File | Meaning |
|---|---|---|
| csv-v1 | .csv | UTF-8 purchase/portal table with header row |
| xlsx-v1 | .xlsx | Read-only worksheet, explicit selection if multiple sheets |
| canonical-demo-v1 | .json | Our fixed, explicitly synthetic portal format |

Example synthetic source files are in backend/examples/. They have structurally valid illustrative identifiers; they are not verified taxpayer data or an official GSTR-2B schema. Amounts use dot decimal strings and at most two decimal places. The parser preserves null components and rejects unsupported precision rather than rounding. Credit-note values are positive magnitudes with explicit CREDIT_NOTE type.

GET `/imports` returns private, paginated import history and supports registration_id/kind/period filters. GET `/imports/{id}` shows state, version, mapping, counters and errors. GET `/imports/{id}/rows` returns the private original/canonical rows and rejection reasons with state/cursor/limit filters. GET `/jobs/{id}` shows truthful parse progress. Paths in this paragraph share the workspace prefix above.

PATCH `/imports/{id}/mapping` supplies expected_version, sheet_name and a complete mapping. It creates/reuses a new derived preview rather than rewriting an existing import. POST `/imports/{id}/confirm` supplies expected_version and explicit allow_rejected_rows/confirmed_supersession acknowledgements where required. Parsing success alone never makes an import READY. No GST matching/credit eligibility decision happens in Phase 3.

Runtime limits: one upload receiver, one parser process globally, five queued/running jobs per workspace, twenty imports per workspace, 1,000 remembered operations per workspace, 2,000 rows, fifty columns, 10,000 characters per cell, JSON depth twenty, 1,000 ZIP entries and 50 MiB actual XLSX expansion. Result output is limited to 16 MiB. Upload receive deadline is twenty seconds and parser deadline sixty seconds. Process-tree RSS is sampled against 256 MiB; this is not a hard OS allocation sandbox.

QUEUED work survives restart and resumes. Interrupted RUNNING work becomes FAILED/PROCESSING_INTERRUPTED. Sources and persisted previews survive restart and backup/restore. Recovery never labels an unfinished parse as confirmed. Poll progress about once every two seconds with backoff; the default session read budget is sixty requests/minute.

For a Phase 2 schema, stop the backend and run from backend/:

```powershell
.\.venv\Scripts\python.exe -m app.manage storage-upgrade
```

The command preserves a validated v1/v2 backup and transactionally adds the missing Phase 3/4 tables. Fresh installations create schema v3 directly. Preserve old-version backups as recovery evidence; current restore accepts v3 backups. Old-version recovery requires offline recovery plus storage-upgrade. Update an older dotenv key MAX_QUEUED_JOBS_PER_SESSION to MAX_QUEUED_JOBS_PER_WORKSPACE using the new template. There is no external database or hosted service.

Locked Phase 3 additions: openpyxl 3.1.5, defusedxml 0.7.1, python-multipart 0.0.32, psutil 7.2.2 and openpyxl's et-xmlfile dependency. CSV/JSON/Decimal/SQLite/process handling use the Python standard library. No pandas, Redis, ORM or cloud SDK was added.


## Phase 3 verification

Local Windows verification on 2026-10-03: full Phase 1–3 regression 169 passed / one symlink-privilege skip; Windows junction protection passed. The final explicit-retry identity fix was verified by all 77 affected import/parser/HTTP tests. Frozen dependencies, Ruff lint/format, syntax compilation and diff checks passed. Actual-process restart and offline backup/restore preserve original upload bytes, source hashes, preview rows and confirmed state while retaining Phase 2's restored-access revocation. The build plan records measured 100/2,000-row CSV/XLSX baselines and watchdog limits. GitHub CI remains separate from this local evidence.

## Phase 4 reconciliation and human review

Confirm one PURCHASE and one PORTAL_2B import for the same workspace/registration/period. POST `/api/v1/workspaces/{workspace_id}/runs` with JSON registration_id, period, purchase_import_id and portal_import_id. Use the existing cookie, configured Origin, X-CSRF-Token and a fresh UUID Idempotency-Key. The 202 response includes run_id/job_id; GET the run/job to poll present state. Idempotent retries return the originally committed response.

GET `/runs` retrieves private paginated history. GET `/runs/{id}/results` pages source-row order with optional status filter; GET `/results/{id}` adds candidates and review history. These relative paths share the workspace prefix. Each result covers one accepted purchase row. Canonical identity/amounts remain nested under canonical. Scores and money are strings, unknown components remain null.

POST `/results/{id}/review` with expected_version, action=ACCEPT_CANDIDATE or REJECT_MATCH, candidate_id (required for accept, null for reject) and a nonblank reason. Only OWNER/REVIEWER may write. The server checks current membership, run/source freshness, row evidence, expected version and unique assignment. Rejection releases an assignment; acceptance becomes REVIEW_ACCEPTED. Result, recomputed summary, audit and request history commit together.

Exact matching uses recipient/supplier/document type/date and invoice number with only case/outer-whitespace normalization, then each amount field within the saved paise tolerance. Fuzzy keys remove explicit ASCII separators while preserving zeroes/year digits; RapidFuzz 3.14.6 ratio yields review suggestions. Threshold decisions floor scores to two decimals and gap decisions use unrounded scores. Shared/tied candidate conflicts stay ambiguous, duplicate identities are quarantined, and no candidate is automatically accepted because of a score.

Runs save source versions/hashes/adapters/provenance and server policy. Unknown tax exposure is a separate count beside known subtotals; credit notes remain separate. A match is comparison against supplied evidence, not legal ITC eligibility or government verification. Synthetic portal provenance remains visible.

Defaults: 20 retained runs/workspace, 4,000,000 compared pairs and 10,000 candidates/run, 2,000 input rows, one global import/run child, five queued/running jobs/workspace, 60-second processing deadline, 16 MiB result and sampled 256 MiB combined child-tree RSS. Exhaustion fails the whole run; no truncated subset is shown as complete. Sources/results/reviews/jobs are in the SQLite backup. QUEUED work resumes; RUNNING interruptions fail visibly. Explicit new runs retry failures; there is no automatic retry loop. A failed replacement keeps older completed output usable; a successful replacement marks older context revisions historical.

## Phase 4 verification

Local Windows full Phases 1–4 suite: **198 passed, 1 skipped** in 423.21 seconds. The skip requires Windows symlink privilege; the actual Windows junction denial test passed. Final zero-gap tie correction then passed all **21 affected matching/golden-run/concurrency tests**, including two added tie cases. Frozen dependency sync, Ruff lint/format, syntax compilation and diff checks passed. The [build plan](../md/05_BUILD_AND_VERIFICATION_PLAN.md) records the exact coverage and initial 100/2,000-row worker measurements. Actual process restart plus backup/restore preserved reviewed results and source/policy snapshots while revoking restored access. These are local checks; remote GitHub CI is separate. No zero-defect guarantee or completed frontend/WhatsApp claim is made.


## Phase 5 local evidence and reports

The website-facing backend now supports scoped cases/evidence, immutable allocation drafts,
reasoned approval, reconciliation/evidence PDFs, proposal CSV and rejected-row CSV. The actual
wire contracts and facts are in [Contracts and Alignment](../md/08_CONTRACTS_AND_ALIGNMENT.md).
Use the existing cookie/Origin/CSRF/UUID-idempotency flow. No frontend or WhatsApp adapter is
created by this phase.

Reports are generated offline in the same bounded child/queue as parsing and reconciliation.
SQLite stores their bytes, source snapshots and hashes atomically; ordinary backup/restore
preserves them. Downloads require membership, valid unexpired content and source freshness.
Historical PDFs/error CSV require an explicit option; stale proposal CSV remains blocked.
A proposal export never records a payment or executes a bank operation.

Default limits and comments are in .env.example: 100 cases/workspace, 100 events/case,
20 proposals/workspace, 40 artifact-history records/workspace, seven-day artifact expiry,
5 MiB generated content, 8 MiB snapshot, 200 reconciliation detail rows and 100 PDF pages.
Five queued/running imports/runs/artifacts combined are allowed per workspace. Reports show
selected-row coverage and retain full-run totals. Cleanup is OWNER-only and clears expired
artifact BLOBs while retaining history; it does not remove imports or free the history cap.
Old backups retain earlier content. Unsupported font characters (including unsupported Indic
scripts/emoji) fail visibly; CSV stays UTF-8. Font source/hash/license are in app/assets/.

An existing schema 1/2/3/4 store requires the explicit offline `python -m app.manage storage-upgrade`;
it validates and preserves the old schema before adding only missing tables. Fresh storage
now creates schema 5. Stop the backend before maintenance; never remove an old DB to bypass this
check. Phase 7 will review the backend as a whole.


Phase 5 verification: full local Windows Phases 1–5 suite **234 passed, 1 skipped** in
508.73 seconds; the separate junction-denial test passed. The final PDF layout/time-display
changes then passed all 24 affected report-rule/end-to-end checks. Generated PDFs were rendered
and visually inspected. The 200-row PDF is 41 pages and 68,286 bytes, labeling selected coverage.
Frozen sync, Ruff, compilation and diff checks passed; remote CI remains separate. Actual HTTP
restart and backup/restore preserve report bytes, cases and proposals with restored access revoked.
The [build plan](../md/05_BUILD_AND_VERIFICATION_PLAN.md) records scope, coverage and limitations.


## Business workflow roadmap correction

Phase 6 implements the six local business workflows through retained actions, supplier follow-up drafts/history, snapshot-change review, reversal/reclaim tracking, recorded-date reminders and notice/IRN tasks. Its local completion gate passed; the measured full-suite and final focused verification record is in 05. The internal website is implemented and connected through Phases 8–9; real WhatsApp remains Phase 13 and combined acceptance Phase 14. Phases 10–11 are now complete; Phases 12–14 remain ahead.


## Phase 6 local work queue and monitor

GET `/api/v1/workspaces/{workspace_id}/actions` returns up to twenty scoped actions, a UUID cursor and automation status. Filter by state or `due_only=true`; fetch detail or `/worksheet` using the same current session. Mutations `/update`, `/followups` and `/outcomes` reuse Origin/CSRF, OWNER/REVIEWER, expected versions and UUID idempotency. Exact fields/states/errors and frontend handoff live in [08](../md/08_CONTRACTS_AND_ALIGNMENT.md) and [04](../md/04_WEBSITE_AND_WHATSAPP_INTEGRATION.md).

The standard-library monitor runs only while the backend is active. Defaults: five seconds per workspace tick, eight changed sources and fifty due actions per scan, three thousand retained actions and one hundred events per action. Workspaces rotate; backlog/pending errors are visible rather than a false clean queue. Catch-up also runs on authenticated action reads and startup. Reminders occur once per recorded UTC date. No message is sent, and no universal statutory due date is guessed.

A later committed snapshot updates the same investigation only for the retained purchase document and compatible registration/period. Meaningful evidence reopens review and clears the current outcome while retaining earlier history. Equivalent observations refresh provenance without duplicate alerts. A different purchase import never inherits an unrelated review. Partial payment remains exact; absent facts stay unknown. Supported reversal/reclaim facts create a review candidate, never legal entitlement or a filed return.

Drafts remain NOT_SENT and preserve action state. An operator attempt needs the same draft/contact/request and date; it is explicitly unverified. Actual filing/submission observations need accepted review and same-case DOCUMENT evidence; the backend executes nothing and verifies no government receipt. Closing needs an explicit recorded outcome. Private PDFs include compact action history/coverage and become stale when linked action/source versions change. Normal offline backup/restore includes the whole action layer and still revokes restored access.

No new dependency, hosted server, external database, government integration or WhatsApp provider was added. Use `storage-upgrade` offline for a validated schema 1–4 store; version 5 restore accepts current backups. Final verification and accepted operating boundaries are recorded in 05.


## Phase 7 backend security/failure review

Complete locally: 230 affected tests passed, one Windows privilege skip, plus frozen dependencies, lint/format/syntax and whitespace checks. Ordinary bodies now have a 20-second total receive deadline, strict framing/JSON ambiguity checks and safe errors. Shutdown retains storage ownership until both background threads stop. All 33 workspace operations have an access scenario. See 05/06 for findings, dated dependency advisory evidence and accepted local limits. Phases 8–9 now build/connect the internal website; the landing page is supplied later. Full regression follows Phase 9.

## Phase 9 local website handoff

The internal website uses the existing opaque session/CSRF protocol and all business services. Lists now support optional registration/month filters before pagination; GET artifacts exposes bounded authorized metadata without BLOBs. Schema remains version 5; no storage migration is required. Full regression passed 314 tests, 1 Windows symlink-privilege skip in 11:39. The real browser suite and built-preview check also pass; see frontend/README and 05.


## Phase 11 performance and regression

Complete locally: **343 backend tests passed, 1 Windows privilege-related skip in 12:13**.
The 14 browser tests, 2 built-preview checks, 10 client/config checks, generated contracts and
strict website build also pass. Core matching results match the actual Phase 10 implementation
field-for-field on the recorded demo/maximum datasets. App source hashes tie the passing
measurement to the final application; CI results remain separate.

Normal 2,000-row matching takes about 1.5–1.8 seconds through real local HTTP; the four-million-pair
case takes about 6 seconds. All eight repeated runs, every expected tracking action and six
private PDFs completed; no 503 or failed health probe occurred. Query fixes use existing scoped
indexes; matching releases the read snapshot before CPU work; reads use actual readonly SQLite.
Reports print meaningful history once and summarize routine refreshes with count/date range,
while all individual events remain in private storage. New report requests identify generator v2.
Existing stored report bytes and public DTOs stay intact. Schema remains 5, with no migration,
new dependency or new environment switch.

For opt-in verification, run from backend:

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -m benchmarks.workload --output benchmarks/results/after.json
```

This is a reusable real-HTTP benchmark in temporary synthetic storage, not a runtime launcher.
It does not load the actual `.env` or database. See [benchmark instructions](benchmarks/README.md)
for measured stages, focused cases, cleanup and honest partial-baseline limitations.
The [build plan](../md/05_BUILD_AND_VERIFICATION_PLAN.md#phase-11-completion-and-measured-verification--2026-10-04)
records causes, budgets and full verification. The maximum repeated load retained about 51.5 MiB
of the 64 MiB DB cap; capacity can be reached before run-count quotas. History is never silently
removed. One child/five pending jobs, exact money, page/byte/deadline/RSS limits and local-only
storage remain. Frontend smoothness, conditional WhatsApp and combined rehearsal remain 12–14.


## Phase 13 checkpoint — 2026-10-04

Local WhatsApp commands, signed callbacks, durable inbox/outbox, supplier consent and website controls are implemented. **This is a work-in-progress checkpoint, not completed Phase 13 acceptance.** Meta setup/HTTPS callback/physical-phone proof remain pending. Default WHATSAPP_ENABLED=false and send budget zero; no real messages or tunnel were created. Existing storage now needs an explicit offline, validated/backed-up `python -m app.manage storage-upgrade` from backend/ to reach schema 6. Never delete the old database; the presenter store was not changed here.

The initial channel/provider set passed 29 tests; the final added ambiguity check passed separately. Browser run: 24 passed, one blank-page failure before login; follow-up startup also failed. Full regression was stopped at the user's request and must not be claimed as passed. See [the build plan](../md/05_BUILD_AND_VERIFICATION_PLAN.md) for exact scope, remaining checks and physical acceptance (use ../md/ from component folders). Git checkpoint skips CI to respect the request not to run regression now.
