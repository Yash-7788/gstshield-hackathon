# GST-Shield — authoritative contracts and cross-layer alignment

> **Active local implementation (2026-10-04):** This is a website with a Python backend running on the PC. Authoritative storage is a private SQLite file under `backend/data/`; accounts are provisioned locally and browser access uses revocable sessions. No external database, hosted identity, cloud storage or application hosting is selected. Phases 1–12 are complete and locally verified. Phase 11 passed the full backend regression (343 passed, 1 Windows privilege-related skip). Phase 12 passed 22 browser checks, built-preview checks and real 100/2,000-row website measurements. See 05 for dated evidence. Phase 13 local WhatsApp integration is implemented with focused checks; Meta setup and physical-phone acceptance remain pending. Phase 14 is not started. Full Phase 13 regression was stopped at the user’s request. The landing page/design is pending. The user authorized a new internal website in Phases 8–9; real WhatsApp remains Phase 13.

Contract baseline v1, 2026-10-03. This document owns wire names, enum semantics and endpoint behavior. Planned models must be reflected in generated OpenAPI and the database migration before frontend integration. [03](03_BACKEND_AND_DATA_SPEC.md) owns algorithms/persistence; [04](04_WEBSITE_AND_WHATSAPP_INTEGRATION.md) maps channels.

## General wire rules

Base path `/api/v1`. JSON uses snake_case. UUIDs identify persisted resources; human labels such as R-104 are display-only. Dates are ISO `YYYY-MM-DD`; period is `YYYY-MM`; timestamps are UTC RFC3339 ending Z. Monetary JSON is a fixed two-decimal string, currency INR. Similarity scores are decimal strings in 0–100, not probabilities.

Absent optional fields and null are documented distinctly. Create requests may omit defaultable options; persisted responses include declared nullable fields. For PATCH, omission means unchanged and explicit null means clear only where permitted. Pydantic request models reject unexpected fields. Do not accept client-computed total_tax, scores, match state, owner IDs or verified provenance as authority.

Selected registration belongs to the authorized workspace. If body registration_id conflicts with import metadata, return CONTEXT_MISMATCH; never switch context silently. Read responses include IDs/context needed to prevent stale frontend cross-workspace updates.

Current public routes are liveness/readiness and origin-checked sign-in. Session recovery/logout and workspace resources require a valid local browser session; resources also require current membership and the appropriate role. Developer docs are local/test only. Future Meta callbacks and capability redemption have their own explicit authentication and remain unimplemented.

## Implemented Phase 2 website access contracts

| Method / path | Input | Success |
|---|---|---|
| POST /api/v1/auth/login | JSON username/password; configured Origin | 200 SessionResponse; HttpOnly cookie |
| GET /api/v1/auth/session | Cookie | 200 SessionResponse |
| POST /api/v1/auth/logout | Cookie, Origin, X-CSRF-Token | 200 {data:{logged_out:true},meta:{request_id}}; expired cookie |
| GET /api/v1/workspaces | Cookie | 200 {data:WorkspaceData[],meta:{request_id}} |
| GET /api/v1/workspaces/{workspace_id}/registrations | Cookie + permitted UUID context | 200 {data:RegistrationData[],meta:{request_id}} |

LoginRequest rejects unexpected fields. Username is 3–64 lowercase ASCII letters/digits/._-, beginning with a letter/digit. Password is 12–128 characters, at most 512 UTF-8 bytes; preserve its exact characters. Password input is a secret type, never echoed in errors.

SessionData: user_id UUID, username string, expires_at UTC RFC3339 Z, csrf_token 64-character hex string. No session token or password appears in JSON. Cookie gstshield_session is opaque, HttpOnly, SameSite=Strict, Path=/api/v1, with Max-Age matching the backend absolute expiry.

WorkspaceData: id UUID, name string, role OWNER/REVIEWER/VIEWER, created_at UTC RFC3339 Z, version positive integer. RegistrationData: id UUID, workspace_id UUID, gstin string, display_name string, created_at UTC RFC3339 Z, version positive integer.

These small lists are bounded by provisioned account/workspace/registration limits and sorted by ID. They have no pagination cursor in Phase 2. Later financial lists use the paginated contract below. Role restrictions on future writes apply when those routes are implemented; membership provisioning is offline administration now.

The client uses credentials:include and the same HTTP hostname for website/API. Recover CSRF in memory after reload through the session endpoint. Authenticated mutations require a single exact Origin and a single X-CSRF-Token; credentials do not go into Authorization headers or query strings. No refresh-token endpoint exists.

Invalid credentials are a generic 401 for unknown/inactive users or a wrong password. Missing/expired/revoked/malformed sessions return AUTH_REQUIRED. Cross-workspace resources return NOT_FOUND. Login/private request limits return RATE_LIMITED with Retry-After; unavailable storage/hash slots/session capacity return their documented 503 with Retry-After.

Session replacement, logout and password reset revoke old sessions. Normal backend restart preserves unexpired sessions and scopes. Backup restore revokes all sessions and disables all restored accounts until operator recovery; the browser must return to sign-in.

The imports and import jobs below are implemented in Phase 3. Runs/results/reviews are implemented in Phase 4. Phase 5 cases, proposals, report jobs and downloads are implemented. Phase 13 implements the current local channel contracts in the final section; the earlier proposed phone catalog is superseded. Real provider acceptance remains pending. Current typed response models generate OpenAPI; the connected internal website generates its DTOs from these same models.

## Shared enums

| Name | Exact values |
|---|---|
| MemberRole | OWNER, REVIEWER, VIEWER |
| Provenance (implemented) | SYNTHETIC_DEMO, USER_PROVIDED; VERIFIED_SOURCE remains unavailable |
| ImportKind | PURCHASE, PORTAL_2B |
| ImportState | RECEIVED, PARSING, AWAITING_CONFIRMATION, READY, FAILED, SUPERSEDED |
| JobState | QUEUED, RUNNING, SUCCEEDED, FAILED |
| RunState | QUEUED, RUNNING, COMPLETED, FAILED, SUPERSEDED |
| ResultStatus | EXACT_MATCH, FUZZY_SUGGESTION, AMOUNT_MISMATCH, MISSING_IN_SNAPSHOT, AMBIGUOUS, EVIDENCE_INCOMPLETE, REVIEW_ACCEPTED, REJECTED |
| DocumentType | INVOICE, DEBIT_NOTE, CREDIT_NOTE |
| CaseKind | MSME_REVIEW, RULE37_REVIEW, RULE37A_REVIEW, IRN_REVIEW, NOTICE_REVIEW |
| CaseState | OPEN, EVIDENCE_REQUIRED, REVIEW_READY, CLOSED |
| ProposalState | DRAFT, APPROVED, EXPORTED, STALE |
| ArtifactKind | RECONCILIATION_PDF, EVIDENCE_PDF, PROPOSAL_CSV, ROW_ERRORS_CSV |
| ArtifactState | PENDING, READY, FAILED, EXPIRED |
| DeliveryState | QUEUED, SENDING, ACCEPTED, DELIVERED, READ, FAILED, UNKNOWN |
| IrnState | NOT_PROVIDED, FORMAT_INVALID, FORMAT_ONLY, VERIFIED, VERIFICATION_FAILED, UNKNOWN |

Database representation uses these uppercase strings consistently; provider status strings are explicitly mapped at adapters. Unknown provider values become recorded unknown facts, not a default successful enum. New enums require schema/OpenAPI/client changes together.

## Success, errors and pagination

Success has `data` and `meta.request_id`; paginated responses add `meta.next_cursor`. No second raw/envelope format. Multipart upload errors use the same JSON error envelope. Download routes stream bytes on success and JSON error on failure; callers check status/content type before saving.

```json
{
  "data": {"id": "00000000-0000-4000-8000-000000000010", "state": "QUEUED"},
  "meta": {"request_id": "req_104"}
}
```

```json
{
  "error": {
    "code": "CONTEXT_MISMATCH",
    "message": "The uploaded recipient does not match the selected registration.",
    "details": [{"field": "recipient_gstin", "row": null, "reason": "registration_mismatch"}],
    "retryable": false
  },
  "meta": {"request_id": "req_105"}
}
```

| HTTP | Codes / behavior |
|---|---|
| 400 | INVALID_REQUEST, UNSUPPORTED_FORMAT, CONTEXT_MISMATCH |
| 401 | AUTH_REQUIRED, INVALID_CREDENTIALS; Meta SIGNATURE_INVALID on callback |
| 403 | ROLE_FORBIDDEN, ORIGIN_REQUIRED, ORIGIN_NOT_ALLOWED, CSRF_INVALID |
| 404 | NOT_FOUND for absent/inaccessible tenant object or capability |
| 409 | VERSION_CONFLICT, IDEMPOTENCY_CONFLICT, ASSIGNMENT_CONFLICT, IMPORT_NOT_READY, RUN_SUPERSEDED, WORKSPACE_BUSY |
| 413 | PAYLOAD_TOO_LARGE currently; future FILE_TOO_LARGE, ARCHIVE_TOO_LARGE, ROW_LIMIT_EXCEEDED |
| 422 | VALIDATION_ERROR currently; future MAPPING_REQUIRED, INCOMPLETE_EVIDENCE |
| 429 | RATE_LIMITED with Retry-After |
| 503 | NOT_READY, STORAGE_UNAVAILABLE, AUTH_BUSY, SESSION_LIMIT currently; future adapter-specific failures |

Stable cursor order is `(created_at, id)` or `(source_row_number, id)` for run results, specified per endpoint. Opaque cursor encodes context/order, is validated and cannot override workspace filters. Page size defaults 50, max 100. List empty data is valid; authorization failures are never empty-success.

## Idempotency and concurrency

Create imports, runs, reviews, cases, proposals and artifact requests accept `Idempotency-Key`, a UUID generated once per intended action. Persist scope `(workspace, actor, route, key)` and canonical request hash. Reuse with identical request returns the original operation; different payload returns 409. Concurrent reservations are protected by uniqueness. Operation references survive response loss.

For upload hashing include bytes, declared context, mapping and adapter choice. A separate import content uniqueness key handles same file with a different request key. Mapping version changes legitimately produce a different operation. Phase 3 retains up to 1,000 operation keys per workspace until deliberate cleanup is implemented; it has no automatic seven-day expiry. Import identities remain persistent. Phase 5 artifact retention is seven days by default; expired content cleanup retains bounded immutable history.

Mutating existing resources requires `expected_version`. Atomic update compares version and advances it only on success. A network failure does not tell the client whether the update committed; retry the same key or fetch the resource. GET can be retried; ambiguous Meta sends cannot be retried as if they were pure reads.

One workspace job running does not reject the next valid operation: it is QUEUED. Initial pending-heavy-job ceiling is five per workspace; only exceeding that ceiling returns WORKSPACE_BUSY. Database coordination enforces the documented one-global-heavy-job execution limit inside the selected single local backend process; a second runtime is refused by its data lock.

## Endpoint catalog

All workspace paths below are prefixed `/api/v1/workspaces/{workspace_id}`. Mutations require OWNER/REVIEWER except membership/demo administration. `202` means a durable operation exists, not processing success.

| Method / suffix | Request | Response / status |
|---|---|---|
| GET /api/v1/workspaces | Cursor/limit | Membership-authorized Workspace[] / 200 |
| GET /registrations | Cursor/limit | Registration[] / 200 |
| POST /imports | Multipart file + fields below | ImportReceipt / 202 |
| GET /imports | registration_id/kind/period/cursor/limit | ImportDetail list with next_cursor / 200 |
| GET /imports/{import_id} | None | ImportDetail / 200 |
| GET /imports/{import_id}/rows | state/cursor/limit | PreviewRow[] / 200 |
| PATCH /imports/{import_id}/mapping | MappingPatch | ImportReceipt / 202 |
| POST /imports/{import_id}/confirm | ImportConfirm | ImportDetail / 200 |
| POST /runs | RunCreate | RunReceipt / 202 |
| GET /runs/{run_id} | None | RunDetail / 200 |
| GET /runs/{run_id}/results | status/cursor/limit | Result[] / 200 |
| GET /results/{result_id} | None | ResultDetail with candidates / 200 |
| POST /results/{result_id}/review | ReviewCreate | ResultDetail / 200 |
| GET /jobs/{job_id} | None | JobDetail / 200 |
| GET /cases | UUID cursor / limit 1–20 | Case list with next_cursor / 200 |
| POST /cases | CaseCreate | CaseDetail / 201 |
| GET /cases/{case_id} | None | CaseDetail / 200 |
| POST /cases/{case_id}/evidence | CaseEvidenceCreate | CaseDetail / 200 |
| POST /cases/{case_id}/transition | CaseTransition | CaseDetail / 200 |
| GET /proposals | UUID cursor / limit 1–20 | Proposal list with next_cursor / 200 |
| GET /proposals/{proposal_id} | None | ProposalDetail / 200 |
| POST /proposals | ProposalCreate | ProposalDetail / 201 |
| POST /proposals/{proposal_id}/approve | expected_version, reason | ProposalDetail / 200 |
| POST /artifacts | ArtifactCreate | ArtifactReceipt / 202 |
| GET /artifacts/{artifact_id} | None | ArtifactDetail / 200 |
| GET /artifacts/{artifact_id}/download | historical=false default | Private attachment bytes / 200; expired 410, stale/not-ready 409 |
| POST /artifacts/cleanup | {expired_only:true}; OWNER only | Expired-artifact cleanup receipt / 200 |
| POST /whatsapp/link-code | registration_id, period | LinkCodeData / 200 |
| GET /whatsapp | None | ChannelData / 200 |
| POST /whatsapp/context | registration_id, period, expected_version, consent_alerts | ChannelData / 200 |
| POST /whatsapp/unlink | expected_version | ChannelData / 200 |

Explicitly no bank-submit, GST-file, escrow-release or provider-status-override endpoint. Future features add contracts rather than overloading a review command into execution.

## Import contract

Multipart fields: `file`, `kind`, `registration_id`, `period`, `adapter_version`, optional `sheet_name`, optional JSON `mapping`, optional `supersedes_import_id`. Provenance is server-set: synthetic adapter/fixture has SYNTHETIC_DEMO; ordinary user upload has USER_PROVIDED. User upload is not VERIFIED_SOURCE merely because its filename claims official origin.

`ImportReceipt`: id, workspace_id, registration_id, kind, period, state, job_id, version, file_sha256, adapter_version, provenance. ImportDetail adds accepted_rows, rejected_rows, duplicate_rows, errors, generated_at and selected-sheet/mapping information.

`MappingPatch`: expected_version, sheet_name nullable, mapping dictionary from canonical field to source header. Mandatory fields cannot map to the same source column ambiguously. Every mapping patch creates/reuses a derived import; existing previews are immutable. A READY parent additionally becomes the explicit supersession target.

`ImportConfirm`: expected_version, allow_rejected_rows default false, confirmed_supersession default false. A rejected-row import requires explicit acknowledgement. A superseding import requires confirmation and same workspace/registration/period/kind.

Canonical demo portal input:

```json
{
  "format": "canonical-demo-v1",
  "provenance": "SYNTHETIC_DEMO",
  "recipient_gstin": "27ABCDE1234F1Z5",
  "period": "2024-05",
  "generated_at": "2024-06-14T00:00:00Z",
  "documents": [
    {
      "supplier_gstin": "27PQRSX5678L1Z2",
      "invoice_number": "INV-001",
      "invoice_date": "2024-05-10",
      "document_type": "INVOICE",
      "taxable_value": "1000.00",
      "igst": "0.00", "cgst": "90.00", "sgst": "90.00", "cess": "0.00",
      "other_charges": "0.00", "round_off": "0.00", "gross_total": "1180.00",
      "irn": null
    }
  ]
}
```

Identifiers here are invented illustrative values, not verified registrations/checksums. Fixture implementation must supply identifiers appropriate to its declared validation mode without pretending government verification. This is our format, not a claimed GSTR-2B schema.

## Run and result contract

```json
{
  "registration_id": "00000000-0000-4000-8000-000000000001",
  "period": "2024-05",
  "purchase_import_id": "00000000-0000-4000-8000-000000000002",
  "portal_import_id": "00000000-0000-4000-8000-000000000003"
}
```

Policy version is selected server-side; response exposes it. RunReceipt includes run_id, job_id, state. RunDetail includes immutable source IDs/hashes, policy_version, provenance, summary nullable, timestamps and superseded_by_run_id nullable.

Summary has `accepted_purchase_rows`, `counts` keyed by every ResultStatus, `tax_exposure_review`, `credit_note_tax_review`, `currency`. Counts include zero values. Pending/failed run has summary=null, never a zero-total success masquerading as an unfinished result.

Result includes id, run_id, purchase_document_id, source_row_number, status, version, invoice identity, component amounts, total_tax, assigned_portal_document_id nullable, provenance and `reason_codes`. Detail adds candidates and review timeline. Candidate fields: portal_document_id, original_invoice_number, invoice_date, score, rank, hard_gates_passed, amount_differences, reason_codes. Amount differences are signed decimal strings, scores fixed decimal strings.

Useful reason codes: DUPLICATE_IDENTITY, SAME_NUMBER_DIFFERENT_YEAR, COMPONENTS_UNKNOWN, TAX_COMPONENT_MISMATCH, GROSS_TOTAL_INVALID, MULTIPLE_CANDIDATES, LOW_SCORE_GAP, SOURCE_SUPERSEDED, IRN_FORMAT_ONLY. Reason labels are UI copy; server codes remain stable.

Review request:

```json
{
  "expected_version": 1,
  "action": "ACCEPT_CANDIDATE",
  "candidate_id": "00000000-0000-4000-8000-000000000020",
  "reason": "Verified against the source voucher."
}
```

Use actual candidate `id` on responses as well as portal_document_id. Actions: ACCEPT_CANDIDATE or REJECT_MATCH. Reject requires reason and candidate_id=null. Accept requires eligible candidate and no conflicting portal assignment. Reviewer does not bypass amount/identity hard gates; insufficient evidence becomes a case for correction/new import.

## Implemented job contract

JobData: id, workspace_id, import_id nullable, run_id nullable, artifact_id nullable, kind IMPORT/RUN/ARTIFACT, state QUEUED/RUNNING/SUCCEEDED/FAILED, error_code nullable, created_at, updated_at. Earlier job timestamp fields are ISO datetime strings. There is no attempt/percentage counter or public lease. Exactly the relevant resource ID identifies the private output. Interrupted running work fails with PROCESSING_INTERRUPTED; queued work resumes through one serial dispatcher.

## Implemented case contracts

CaseCreate: registration_id, result_id, purchase_document_id, kind, amount (nonnegative decimal string), currency INR default, facts default {}. Source provenance is server-derived. Registration, result and stable document must agree. No client verification/provenance override is accepted.

Facts are validated by kind; unknown optional values remain null:

| Kind | Fields in addition to observation_refs UUID[] (max 20) |
|---|---|
| MSME_REVIEW | supplier_classification MICRO/SMALL/MEDIUM/OTHER/UNKNOWN; acceptance_date; agreed_credit_days integer 0–3650; amount_paid; payment_observed_on; dispute_note max 1,000 |
| RULE37_REVIEW | original_claim_period; original_claim_amount; amount_paid; payment_observed_on; payment_due_date |
| RULE37A_REVIEW | original_claim_period; original_claim_amount; reversal_period; reversal_amount; supplier_return_period; supplier_return_status FILED/NOT_FILED/UNKNOWN; filing_observed_on |
| IRN_REVIEW | irn max 128; applicability APPLIES/DOES_NOT_APPLY/UNKNOWN |
| NOTICE_REVIEW | notice_reference max 200; notice_date; response_due_date |

Dates require ISO YYYY-MM-DD strings, periods require YYYY-MM. Amounts are exact decimal strings; booleans/numeric money are invalid. Amount paid cannot exceed the source gross; a recorded reversal cannot exceed a recorded original claim. Facts are observations, not computed legal outcomes.

CaseEvidence: expected_version, event_kind, reason (readable 1–1,000 characters), import_id nullable, facts_patch default {}. Event kinds: NOTE, DOCUMENT, PAYMENT_OBSERVATION, FILING_OBSERVATION, ACCEPTANCE_OBSERVATION, IRN_OBSERVATION. DOCUMENT requires an existing same-scope/registration import. No file path or arbitrary local upload reference is accepted. Facts patches merge and are revalidated; non-note events add a server-generated same-case observation reference. Source metadata is frozen in evidence_source.

CaseTransition: expected_version, state, reason. Legal edges: OPEN -> EVIDENCE_REQUIRED -> REVIEW_READY -> CLOSED; REVIEW_READY -> EVIDENCE_REQUIRED and CLOSED -> OPEN with an explicit reason. Ready requires kind-specific facts and matching observation snapshots. A generic note cannot replace payment/filing/acceptance/IRN evidence. Closed cases cannot be edited without reopening. Adding evidence to a ready case returns it to EVIDENCE_REQUIRED.

CaseData: id, workspace_id, registration_id, result_id, purchase_document_id, kind, amount, currency, facts, provenance, state, version, created_at, updated_at, missing_facts, irn_observation and bounded timeline. Events retain actor, kind, note, full fact snapshot, source metadata, from/to state, version, request ID and UTC time. IRN output is NOT_PROVIDED/FORMAT_INVALID/FORMAT_ONLY; never VERIFIED.

## Implemented proposal contracts

ProposalCreate: run_id, expected_run_version, expected_result_versions dictionary result UUID -> positive integer (1–100 entries), balance_observations (1–100), allocations (1–200). There is no separate selected_result_ids field; dictionary keys select the results. Each balance observation has document_id, evidence_case_id and expected_case_version. Each allocation has document_id, amount and purpose SUPPLIER_PROPOSED/INTERNAL_RESERVE_ILLUSTRATIVE. No bank account, beneficiary or executable instruction field exists.

All selected results must belong to the current completed run and be EXACT_MATCH/REVIEW_ACCEPTED. Credit notes require separate adjustment review. Each document needs a reviewed same-document MSME/Rule 37 case with current payment observation, amount_paid and payment_observed_on. All purposes combined must fit source gross minus recorded paid. Unknown/unreviewed balances fail. Negative/floating-point money is rejected.

ProposalData: id, workspace_id, run_id, snapshot, snapshot_sha256, state, stored_state, version, created_at, updated_at, sources_current, timeline. Snapshot freezes run/result/case versions, invoice/gross/paid/balance observations, allocations, total_allocated, currency, provenance and PROPOSAL_ONLY instruction. Stored lifecycle is DRAFT -> APPROVED -> EXPORTED; effective STALE is computed when sources change. GET never mutates audit history. Approve requires expected_version and reason. Approval/export never modifies amount_paid. A changed draft needs a new proposal, not an amount edit in place.

## Implemented artifact contracts; future phone capability

ArtifactCreate: kind, source_id, expected_version, selected_result_ids default [] (reconciliation PDFs only; distinct UUIDs, max configured 200). Kind determines one source: reconciliation -> run, evidence -> case, proposal CSV -> approved/current proposal, row errors -> parsed import. Request source/version is checked under the same transaction that freezes the snapshot.

ArtifactData: id, workspace_id, kind, source_id, source_version, snapshot_sha256, filename, mime_type, state PENDING/READY/FAILED/EXPIRED, sha256 nullable, size_bytes nullable, error_code nullable, expires_at, created_at, updated_at, manifest, provenance, sources_current and job_id. It never includes bytes, private paths or job leases. Workflow timestamps (case/proposal/artifact/events) are UTC Unix seconds. Values in manifests/snapshots are bounded JSON; clients must not convert unknown amounts to zero.

POST returns 202 for a durable job. Poll GET /jobs/{job_id} or artifact detail. Identical active kind/snapshot requests reuse the same artifact; idempotency repeats return the original receipt. A new UUID can regenerate a FAILED artifact. Successful report bytes, status and job commit atomically in private SQLite. Proposal export uses the immutable proposal hash, so the APPROVED -> EXPORTED lifecycle increment does not make its own CSV stale.

Downloads require a current session/member and READY, unexpired, hash/size-valid bytes. MIME and UUID filename are server-generated. A stale source returns 409 by default; historical=true allows an explicitly historical PDF/error CSV with X-GSTShield-Historical:true. Stale proposal CSV is always denied, including historical=true. Downloads set no-store, attachment and nosniff. Expired downloads return 410 and unfinished/failed artifacts return 409.

OWNER-only POST /artifacts/cleanup accepts {expired_only:true} (default true), requires CSRF/Origin/UUID idempotency and returns {expired_artifacts,scope:EXPIRED_ARTIFACT_CONTENT_ONLY}. It clears only expired report BLOBs, retains metadata/history and cancels any pending lease. It does not delete raw imports, cases or arbitrary files; old backups retain previous bytes. History caps remain explicit after cleanup.

Future Phase 13 capability route: GET /downloads/{opaque_token} is planned outside /api/v1, with revocation, expiry, membership and bounded redemption. It is not implemented by Phase 5; current browser downloads require cookie authentication.

## WhatsApp adapter alignment

Web commands use Auth subject; WhatsApp uses wa_link.user_id after current membership verification. Both construct the same application command DTO. `RUN` uses latest READY imports in the selected context; if multiple applicable sources or supersession ambiguity exist, ask the user to select in the website rather than guess.

Provider payload is not our public API contract. Adapter accepts validated known event structures and records unsupported types; a status callback does not look like a command. Sender identity comes from verified callback metadata, never user text. Every logical event maps to at most one operation key.

## Changes and contract proof

Before merging a field change, update Pydantic, generated OpenAPI/types, DB migration/defaults and adapters together. Test a genuine serialized response consumed by the website client, not only parallel handwritten interfaces. Keep a contract fixture for success/error/pagination/money/unknown-state cases.

Backward-compatible optional additions can stay v1. Renames, enum semantics, money units or null/default meaning require an explicit migration and coordinated client change. Never conceal drift with `any`, generic “value or zero,” or a success fallback that turns server failures into empty results.

## Alignment checklist

- [ ] No field has different units in database/API/website/WhatsApp.
- [ ] No client-supplied tenant/user ID grants access.
- [ ] Money remains exact and string-serialized end to end.
- [ ] Each completed run has exactly one result per accepted purchase record.
- [ ] Summary counts and detailed categories agree after review.
- [ ] Candidate IDs and portal IDs have distinct fields.
- [ ] Null unknown values survive import and display.
- [ ] Every enum is represented in UI and database validation.
- [ ] Job success requires committed visible output.
- [ ] New snapshot creates explicit supersession rather than overwriting history.
- [ ] No proposal download is represented as payment execution.
- [ ] Physical WhatsApp results equal the persisted website run.


## Current Phase 3 website contract details

All import routes are under `/api/v1/workspaces/{workspace_id}` and use the existing credentialed browser session. POST upload, PATCH mapping and POST confirmation require exact Origin, X-CSRF-Token and one lowercase UUID Idempotency-Key. Fields are named exactly as the catalog above. The actual Pydantic response models in backend/app/contracts/imports.py generate OpenAPI.

POST `/imports` returns 202 with an ImportDetail-compatible receipt. State can advance before a duplicate retry response returns. Awaiting confirmation has state=AWAITING_CONFIRMATION; parser failure has state=FAILED with fixed errors. Provenance is USER_PROVIDED for CSV/XLSX and SYNTHETIC_DEMO for canonical-demo-v1. Neither is VERIFIED_SOURCE. Created/updated timestamps are UTC RFC3339, while source generated_at is a validated zoned source timestamp.

GET `/imports/{id}/rows` accepts `state=ALL|ACCEPTED|REJECTED`, integer `cursor` (last row position, default 0), and `limit` 1..100. Its envelope data is `{rows: PreviewRow[], next_cursor: integer|null}`. Rows include row_number, original, canonical, errors, accepted and duplicate. Empty/pending previews return an empty rows array, and the detail/job state tells the website whether parsing is incomplete. No totals should be fabricated from that empty array.

GET `/jobs/{id}` currently returns id, workspace_id, import_id, kind=IMPORT, state=QUEUED|RUNNING|SUCCEEDED|FAILED, error_code nullable, created_at and updated_at. The richer future job catalog's phase/attempt/output_ref fields are not currently implemented. Poll about once every two seconds with backoff to share the sixty-reads/minute session budget with other screens. Job SUCCEEDED indicates a checked preview; explicit import confirmation is still required.

PATCH mapping uses expected_version, optional sheet_name and a complete canonical-field-to-header mapping dictionary. Money values in files use dot decimals without grouping and at most two decimal places; mapping is not an implicit currency/locale converter. Do not provide a sheet for non-XLSX or change the fixed demo JSON field mapping. Confirm uses expected_version, allow_rejected_rows=false and confirmed_supersession=false by default. Versions change when a parser starts, completes/fails, or an import confirms/supersedes; refresh before a new user action. An identical retry of the same confirmation key remains valid even after its version changed.

Current additional errors include UPLOAD_BUSY/503, QUEUE_FULL/429, IMPORT_LIMIT/409, OPERATION_LIMIT/409, UPLOAD_TIMEOUT/408, INVALID_MULTIPART/400, IDEMPOTENCY_KEY_REQUIRED/400, PARTIAL_ACK_REQUIRED/409, SUPERSESSION_ACK_REQUIRED/409 and IMPORT_NOT_CONFIRMABLE/409. Retry-After is returned for transient admission limits and exposed by CORS alongside X-Request-ID. Mapping/unsupported content errors must stay visible to the user; do not label them as a successful import or an ITC decision.

GET `/imports` returns `{imports: ImportDetail[], next_cursor: UUID|null}` with `limit` 1..100 (default 20), a last-seen UUID `cursor`, optional registration_id, kind and period filters. Results are consistently ordered by ID; this is pagination order, not a claim that a source is latest or authoritative. A browser refresh can recover durable import IDs through this list.

## Current Phase 4 website contract

Actual models are backend/app/contracts/runs.py and generate OpenAPI. All routes use `/api/v1/workspaces/{workspace_id}` and the existing private browser session. OWNER/REVIEWER may create runs and review results; VIEWER may read. Mutations require one configured Origin, X-CSRF-Token and UUID Idempotency-Key. Unexpected payload fields, boolean expected_version, blank/control-character reasons, accept-without-candidate and reject-with-candidate return 422. Inaccessible resources return 404.

| Method / relative path | Current response |
|---|---|
| POST /runs | 202 RunResponse; saved run_id/id and job_id |
| GET /runs | RunListResponse, UUID cursor, limit 1..100 |
| GET /runs/{run_id} | RunResponse |
| GET /runs/{run_id}/results | ResultListResponse, integer source-row cursor, limit 1..100, optional ResultStatus filter |
| GET /results/{result_id} | ResultResponse with candidates and review_timeline |
| POST /results/{result_id}/review | ResultResponse after atomic review |
| GET /jobs/{job_id} | Shared JobResponse for IMPORT or RUN |

RunData has id/run_id, workspace_id, registration_id, period, purchase_import_id, portal_import_id, revision, version, job_id, state, policy_version, policy, sources, sources_current, provenance, summary nullable, superseded_by_run_id nullable and UTC timestamps. `revision` orders context reruns; `version` increases for state/review changes. The receipt is saved before processing and has summary=null. Idempotent retries replay that committed receipt; poll GET for present progress. A failed run never supplies fabricated zero totals. Sources contain id/kind/sha256/version/adapter_version/provenance/generated_at/accepted_rows/rejected_rows.

Summary includes every ResultStatus count plus accepted_purchase_rows, tax_exposure_review, credit_note_tax_review, unknown_tax_exposure_rows, unknown_credit_note_tax_rows and currency=INR. Monetary totals are fixed decimal strings for the known subtotal; unknown counters must be displayed with them. All classification counts sum to accepted_purchase_rows.

ResultData contains id, workspace_id, run_id, purchase_document_id, source_row_number, status, version, canonical, assigned_portal_document_id nullable, provenance and reason_codes. Invoice identity/component amounts/total_tax are nested in `canonical` using the same names and money/null semantics as import previews. Detail adds candidates and review_timeline. Candidate has its own id, portal_document_id, original_invoice_number, invoice_date, score string, rank, hard_gates_passed, currently_available, amount_differences and reason_codes. Eligibility is saved matching evidence; availability may change after another result is reviewed. The server always rechecks both. Timeline includes actor_id/action/reason/candidate_id/result_version/created_at.

The implemented shared job response is id/workspace_id/kind/state/error_code/created_at/updated_at with import_id nullable and run_id nullable. IMPORT has import_id; RUN has run_id. No attempt/percentage/output_ref/lease fields are exposed. The earlier richer job shape is reserved for a future contract change, not an existing response. Both kinds resume QUEUED jobs and fail interrupted RUNNING jobs on restart.

Useful actual errors: SOURCE_CONTEXT_INVALID, SOURCE_SUPERSEDED, STALE_VERSION, ASSIGNMENT_CONFLICT, CANDIDATE_INELIGIBLE, IDEMPOTENCY_CONFLICT, RUN_LIMIT and QUEUE_FULL. Worker failures include MATCH_PAIR_LIMIT, MATCH_CANDIDATE_LIMIT, PROCESSING_INTERRUPTED, PROCESSING_TIMEOUT and PARSED_RESULT_LIMIT. Explain a failed run using the scoped job code; source corrections/new run are explicit actions. Match scores are similarity, never legal approval.


## Phase 6 implementation contract (complete and locally verified)

Selected implementation: schema 5 adds business actions, append-only action events, source-processing checkpoints and per-workspace automation status. Source/run/case schemas 1–4 remain immutable. A local monitor checks one workspace per configured interval; authenticated work-queue reads also request bounded catch-up. New actions derive from current completed runs and existing cases. Invoice identity is the retained purchase document UUID: automatic snapshot comparison requires the same purchase import, registration and period. A different purchase source is a separate identity and never silently closes old actions.

Implemented routes under /api/v1/workspaces/{workspace_id}: GET /actions (bounded cursor/filter list with processing status), GET /actions/{id}, POST /actions/{id}/update (expected version, state, recorded review date, assigned reviewer and reason), POST /actions/{id}/followups (deliberately supplied contact, correction request and DRAFT/ATTEMPT_RECORDED events), POST /actions/{id}/outcomes (review decision or separately evidenced filing/submission observation), GET /actions/{id}/worksheet. Mutations retain cookie/Origin/CSRF, live OWNER/REVIEWER roles and UUID idempotency keys. VIEWER may read permitted records only. No route sends messages, fetches government data, files a return or executes a bank instruction.

States: OPEN, AWAITING_SUPPLIER, EVIDENCE_REQUIRED, REVIEW_REQUIRED, CLOSED. New relevant evidence changes reopen closed actions for explicit review; same evidence does not duplicate an action or alert. Automated source refresh and due alerts retain SYSTEM attribution distinct from human events. Reminders use recorded UTC dates, never guessed statutory dates. Due alerts are deduplicated per recorded due date and require re-scheduling for another reminder. Source freshness is returned separately from action state; stale history remains readable but consequential closure/follow-up/outcome commands require refreshed evidence. Actual filing/reclaim observations need reference, observed date, exact amount and provenance; reviewed proposals are not recovered amounts.

Implemented operating limits: 3,000 retained actions per workspace, 100 events per action, eight changed sources and 50 due actions per workspace scan, five-second default monitor interval. Quota failure rolls back the affected source's action publication and leaves the source checkpoint pending; an authenticated automation status exposes the failure. Existing import/reconciliation/case success is independent of derived automation, which can be retried without re-upload. Limits and strictly validated environment settings are aligned with backend/.env.example.


### Action wire contract and error handling

Base `/api/v1/workspaces/{workspace_id}`; all replies use existing data/meta envelopes. GET `/actions` accepts `cursor` UUID, `limit` 1–20, optional state and boolean due_only. Data is `{actions, next_cursor, automation}`. Automation includes checked_at nullable epoch seconds, error_code nullable, pending_sources, interval_seconds and channel_delivery=NOT_IMPLEMENTED. Pending work/errors are an incomplete-check condition, never proof there are no problems.

Action data contains id/workspace_id/registration_id/document_id, period/kind, nullable case_id, run_id/result_id, frozen source, state/version, nullable assigned_to/due_at/reminded_at/outcome, sources_current, created_at/updated_at and timeline. These timestamps are integer UTC epoch seconds, consistent with the implemented existing resources. Source retains result/run/case versions, imported snapshots, recorded tax and candidate/assigned portal evidence. It labels legal_eligibility=NOT_DETERMINED and automatic_fetching=NOT_IMPLEMENTED. Case source adds facts, case_amount, evidence_event_ids and review (missing_facts, limitations, remaining_balance nullable, proposed_reclaim_amount nullable, reclaim_candidate, legal/provider status, IRN observation).

| Command | Fields beyond expected_version and nonblank reason | Semantics |
|---|---|---|
| POST `/actions/{id}/update` | state, review_on nullable ISO date, assigned_to nullable UUID | Full command; omitted nullable fields clear them. CLOSED requires recorded outcome; reopening clears current outcome. |
| POST `/actions/{id}/followups` | kind=DRAFT or ATTEMPT_RECORDED, contact, request, draft_id nullable, observed_on nullable | Draft is NOT_SENT and preserves state. Attempt requires same action draft/contact/request and nonfuture date; user report remains unverified. |
| POST `/actions/{id}/outcomes` | kind, decision nullable, amount nullable exact money, reference/observed_on nullable, evidence_event_ids array, provenance | REVIEW_DECISION needs REVIEW_ACCEPTED/EVIDENCE_REQUIRED/REJECTED. Filing/notice observation needs accepted review and same-case supporting DOCUMENT evidence, reference and date. Filing additionally needs positive amount within evidence/case bounds. |
| GET `/actions/{id}/worksheet` | No mutation body | JSON handoff with label REVIEW_WORKSHEET_NOT_FILED_RETURN, current source/version, reviewed outcome, pending state/date, filing_execution=NOT_IMPLEMENTED and recovery_guarantee=false. |

FILING_OBSERVATION applies only to an evidence-backed RULE37A_REVIEW candidate; NOTICE_SUBMISSION_OBSERVATION only to a complete recorded notice case. Every recorded observation reports execution=NOT_PERFORMED and government_verified=false, retaining USER_PROVIDED or propagated SYNTHETIC_DEMO provenance. These are user-supplied observations, not automatic verification. Future dates, float money, duplicate evidence IDs, extra fields, blank/control text and invalid contacts are rejected.

Timeline includes actor_kind SYSTEM/USER, nullable actor_id, kind, reason, action version, request_id, created_at and snapshot. A DRAFT event's id is the next attempt's draft_id. A meaningful evidence change keeps the action UUID and previous timeline but clears current outcome. Equivalent observation/source refresh retains it. A different purchase import creates a separate identity and cannot reuse the previous issue outcome.

Relevant codes: ACTION_SOURCE_STALE, STALE_VERSION, IDEMPOTENCY_CONFLICT, ACTION_LIMIT, ACTION_HISTORY_LIMIT, INVALID_ASSIGNEE, ACTION_CLOSED, INVALID_DRAFT, DRAFT_CHANGED, OBSERVATION_DATE, OUTCOME_AMOUNT, OUTCOME_KIND, INVALID_EVIDENCE, DOCUMENT_EVIDENCE_REQUIRED, REVIEW_OUTCOME_REQUIRED, RECLAIM_EVIDENCE_REQUIRED and NOTICE_EVIDENCE_REQUIRED. Processing status may show STORAGE_UNAVAILABLE or AUTOMATION_FAILED. Refresh source/action state after conflicts; retain the original key/payload for uncertain retries. Generic HTTP errors still hide inputs and private paths.


A future supplier-filing observation or future recorded claim/reversal period cannot produce a current reclaim-review candidate. Such facts stay retained for review with reclaim_conditions_require_evidence_review rather than being treated as observed recovery evidence. Recorded future review dates remain valid for scheduling; this guard is specific to claimed past observations, not statutory deadline calculation.


## Phase 7 request envelope errors

All ordinary POST/PUT/PATCH bodies are bounded before JSON processing. REQUEST_TIMEOUT is a sanitized HTTP 408 with the normal error/meta envelope when the total receive deadline is exceeded. No completed command is claimed. BAD_REQUEST (400) covers actual/declaration byte mismatch or ambiguous Content-Type; PAYLOAD_TOO_LARGE remains 413. Duplicate/nested/escaped JSON keys, malformed JSON/encoding and NaN/Infinity constants produce VALIDATION_ERROR (422). These replies retain no-store, server request IDs and allowed-origin headers. Existing source/role/version/CSRF contracts are unchanged. The environment example includes MAX_API_RECEIVE_SECONDS=20; uploads retain their separate deadline and authorization order.

## Connected website/list contract — Phase 9

GET runs, cases, proposals, actions and artifacts accept optional UUID registration_id and YYYY-MM period, matching existing import-list validation. Filtering occurs in bound SQL before ordering/cursor/page limit; it must not be a browser-only filter after pagination. Cases join their original result/run; proposals their run. Artifact filters resolve all four source kinds without broadening workspace access. Nonexistent registration yields an empty scoped page; a foreign workspace remains opaque 404. Existing callers may omit both filters and retain prior workspace-wide behavior. Cursor remains UUID, limit remains <=100 for runs and <=20 for cases/proposals/actions/artifacts.

GET /api/v1/workspaces/{workspace_id}/artifacts returns ArtifactListResponse: data.artifacts (existing ArtifactData metadata only) plus data.next_cursor. The response contains no BLOB, content, raw snapshot or server path. Expired/state/source-current labels follow the same detail semantics. Download still requires the private authenticated route and explicit historical opt-in for stale evidence PDF/row-error CSV; stale proposal CSV remains denied. No public link is introduced.

frontend/scripts/generate-contracts.mjs derives 76 DTO schemas from actual OpenAPI and the canonical importFields from app.domain.imports.FIELDS. check:contracts detects unintended drift, normalizing checkout line endings. No handwritten backend enum/schema substitute and no downloaded API SDK is required. Case facts remain backend-validated dictionaries; website inputs match the five concrete backend fact models and each phase's conservative observation rules.

HTTP failures stay error envelopes. Browser supplies cookies, in-memory X-CSRF-Token and UUID Idempotency-Key for mutations. It retains unchanged uncertain-write receipts for explicit retries and does not silently retry writes. Receipt memory is cleared on session reset; it is not a durable cross-refresh retry log. Read cancellation is separate from write uncertainty. Exact decimal amounts remain strings/BigInt formatting; unknown remains unknown. User preferences contain only identity-scoped selection IDs/month, are not access authority, and are cleared on sign-out/expiry. Error and stale-source labels never become false saved/sent/filed assertions.


## Phase 10 browser access and configuration alignment

No backend route, DTO or SQLite schema changed. VITE_API_BASE_URL remains the only public setting, with explicit exposure instead of the broad VITE_ prefix. Existing cookie/Origin/CSRF/version/idempotency requirements still apply. Read body/error and download completion checks reject obsolete sessions/scopes; report lookup requires UUID shape and backend ownership is rechecked. Access-denied cached data is discarded; visible workspace membership refresh runs every 15 seconds and changed roles reset screen state. Backend authorization remains immediate per request, while the UI learns external changes on polling/interaction. The Phase 10 record in 05 distinguishes real backend journeys, simulated privacy faults, strict built-preview checks and the retained full Phase 9 regression.


## Phase 11 internal alignment

Existing public routes, OpenAPI DTOs, HTTP envelopes, exact amount strings, expected versions,
Origin/CSRF/session requirements, idempotency rules and schema 5 stay unchanged. Generated
76-type alignment and the real website journeys pass against the optimized backend. There is
no frontend fallback/mocked calculation introduced by the performance work.

New private immutable report snapshots add action invoice, comparison_status, reason_codes and
recorded_tax summary fields alongside retained timeline/source-version tracking. New manifests
identify gstshield-reports-v2. A legacy snapshot without concise fields remains readable: the PDF
can obtain its latest source summary from retained DETECTED/SOURCE_REFRESHED/EVIDENCE_CHANGED
history. Existing stored PDF bytes are not rewritten. Meaningful/user events appear once; routine
SOURCE_REFRESHED entries use count and earliest/latest dates with explicit private-history labels.
REPORT_PAGE_LIMIT is the stable failure code, including when ReportLab annotates callback errors.

Bounded PDF coverage still explicitly identifies selected details versus full-run summary totals
and shown versus total actions. A successful report does not imply a filed return, delivered
message, legal entitlement, payment or recovery. Repeated maximum matching/tracking/report and
full-field golden equivalence evidence live in 05 and backend/benchmarks/results. Frontend
smoothness, conditional WhatsApp and combined rehearsal retain Phases 12–14.


## Phase 12 contract continuity — 2026-10-04

Public routes, generated 76 DTOs, schema, money strings and backend rules remain unchanged. Internal resource state now distinguishes an initial load from a same-identity/session/URL refresh; consumers preserve same-version drafts while refreshing and disable writes requiring current detail versions. Job detail reloads follow parent job identity/state/version changes instead of a second timer. Read errors honor bounded numeric Retry-After, but writes retain explicit retry/idempotency behavior.

History and candidate pages render 20 items at a time while preserving all retained evidence/ranking and access to every candidate. Currency formatting continues exact string/BigInt handling and fixes the display of negative sub-rupee values such as -0.50. No tax calculation moves into the browser. Six real backend website-contract checks, generated-contract comparison, 22 browser checks, two built-preview checks and the maximum real 2,000-row connected workload pass. Phase 13/14 remain pending; dated details and measurement limits are in 05.


## Phase 13 actual channel contracts — 2026-10-04

This section supersedes the earlier proposed phone-route catalog. Existing business routes/DTOs keep their units and semantics; generated contracts now contain 93 actual schemas. Browser channel mutations require session, Origin/CSRF and UUID Idempotency-Key. Link-code responses contain a fresh one-use secret and do not persist a raw response receipt; repeat requests replace previous codes. Context/unlink use expected_version and require refreshing after an uncertain response. Supplier queueing replays the same recipient delivery; phone business effects replay deterministic shared-service receipts.

| Method / workspace suffix | Actual request / response |
|---|---|
| GET /whatsapp | ChannelData with enabled/sending_enabled, masked own link, recent delivery states/history, remaining attempt budget; physical_phone_verified is false pending proof |
| POST /whatsapp/link-code | registration_id, period; LinkCodeData / 200 |
| POST /whatsapp/context | registration_id, period, expected_version, consent_alerts; ChannelData / 200 |
| POST /whatsapp/unlink | expected_version; ChannelData / 200 |
| POST /whatsapp/supplier-consent-code | action_id, draft_id, expected_version; ConsentCodeData / 200 |
| GET /whatsapp/supplier-recipients | Current actor/workspace's masked SupplierRecipientData[] / 200; OWNER/REVIEWER |
| POST /whatsapp/supplier-followups | action_id, draft_id, expected_version, recipient_id; DeliveryData / 200; queued is not delivered |

Global GET/POST `/webhooks/whatsapp` are provider-authenticated and hidden from browser OpenAPI. GET `/wa/reports/{43-character token}` returns a bounded PDF attachment or generic 404; bearer redemption rechecks live authority/current artifact. Disabled callbacks/creation return CHANNEL_DISABLED (503), zero-budget supplier queueing is unavailable, stale versions conflict, and ambiguous READY source selection returns SOURCE_SELECTION_REQUIRED without creating a run.

DeliveryData states: QUEUED, ATTEMPTED, ACKNOWLEDGED, DELIVERED, READ, FAILED, UNKNOWN, CANCELLED. Action automation channel_delivery now reports DISABLED/PAUSED/ENABLED according to runtime configuration/remaining attempt budget; ENABLED is not proof of physical-phone delivery. Report/raw code/token secrets never enter delivery history. See 05 for final regression/provider gates.
