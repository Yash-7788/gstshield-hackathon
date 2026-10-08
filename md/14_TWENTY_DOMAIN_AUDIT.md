# GSTShield: 20-domain code and security audit

Started 8 October 2026. Scope: current working source, cross-file contracts, local startup, SQLite and browser/API boundaries. This is a source-led audit, not a promise to find every defect or achieve a reviewer score. Heavy test suites are excluded. Existing user preferences for freely chosen credentials and local PC storage stay in force.

## Domain map, from micro to macro

| # | Domain | Code / security questions | Status |
| --- | --- | --- | --- |
| 01 | Input contracts and canonicalization | Amounts, identifiers, dates, enums, null/zero and Unicode | Reviewed in selected source; coverage limits below |
| 02 | Authentication and credentials | Password storage, session scope, portal and account lifecycle | Reviewed in selected source; coverage limits below |
| 03 | Team and role authorization | Tenant/role reads, mutation checks, shared accounts and secrets | Reviewed in selected source; coverage limits below |
| 04 | HTTP and website origins | Host/origin, cookies, CSRF, request parsing and URL boundaries | Reviewed in selected source; coverage limits below |
| 05 | Limits and concurrent admission | Body size, slow clients, login/AI slots, rate windows and pools | Reviewed in selected source; coverage limits below |
| 06 | SQLite integrity and transactions | Foreign keys, rollback, disk limits, locks and busy behavior | Reviewed in selected source; coverage limits below |
| 07 | Storage privacy and recovery | Paths, backups, WAL, file permissions and safe deletion | Reviewed in selected source; coverage limits below |
| 08 | Imports and parser isolation | CSV/XLSX/JSON, malicious archives, duplicate rows and workers | Reviewed in selected source; coverage limits below |
| 09 | Invoice/OCR lifecycle | Upload, provider response, confirmation, retry and provenance | Reviewed in selected source; coverage limits below |
| 10 | Order/delivery/item comparisons | Item identity, quantity/price/unit, missing evidence and mismatch | Reviewed in selected source; coverage limits below |
| 11 | GST reconciliation and monthly scope | Matching, fuzzy acceptance, source revisions and tenant/month | Reviewed in selected source; coverage limits below |
| 12 | Vendor risk and anomaly logic | Duplicate identity, weights, missing data and money aggregation | Reviewed in selected source; coverage limits below |
| 13 | Payment gate and approvals | Current evidence, bounded amounts, parallel writes and simulated bank | Reviewed in selected source; coverage limits below |
| 14 | Cases, evidence and reports | Private reads/downloads, versioning, fingerprints and output limits | Reviewed in selected source; coverage limits below |
| 15 | Supplier/WhatsApp integration | Consent, callbacks, replay, provider side effects and report links | Reviewed in selected source; coverage limits below |
| 16 | Workflow and tax review | Exit conditions, stale downstream states, explicit review and completion | Reviewed in selected source; coverage limits below |
| 17 | Assistants and business privacy | Saved facts, scoped data, AI injection boundaries and salary privacy | Reviewed in selected source; coverage limits below |
| 18 | Frontend state and navigation | Account/context switches, aborts, stale replies, forms and downloads | Reviewed in selected source; coverage limits below |
| 19 | Startup, workers and efficiency | Shutdown ownership, queue admission, cache keys and SQL/query costs | Reviewed in selected source; coverage limits below |
| 20 | Dependencies, build and deployment | Versions, secrets, static assets, local exposure and reproducibility | Reviewed in selected source; coverage limits below |

## Method and continuity

Infigraph tools are unavailable in this session, so direct source searches are the fallback. The Jainune logical-correctness document and representative auth/boundary code are being read as references for cross-component and failure-order reasoning, not copied wholesale into this local architecture. Codex Security was discovered but is not installed; installation was suggested and does not block the local audit.

Evidence entries will record source, trigger, consequence, fix, focused verification and remaining limits. A requested feature gap is distinguished from a confirmed defect. File/invoice deletion will require role authorization, expected versions, audit history and safe handling of referenced evidence; silently deleting audit or payment history is not an acceptable shortcut. Findings are saved immediately as the audit progresses. No push or commit is authorized for this task.

## Continuity note (2026-10-08)
The requested twenty-domain source audit is in progress. The audit plan exists; no fixes have been applied yet. Infigraph is unavailable in the exposed tool catalog, so source and document inspection are the fallback. Confirmed finding: LocalHTTPBoundary recognizes import and original invoice upload paths but omits the supporting evidence-document upload path, so its 64 KB JSON ceiling rejects larger supporting PDF/photo uploads before their bounded upload handler. Removal must preserve financial decisions and audit history while invalidating affected evidence and approvals. No heavy regression suite has run. Existing unrelated and earlier uncommitted work must be preserved. The Codex Security plugin was suggested but is not connected; no plugin scan has occurred. Jainune logical-correctness guidance and representative security code were read as references, not proof of GSTShield correctness. Remaining work: fix the confirmed upload boundary, inspect all twenty domains, implement authorized safe removal, run focused verification, and record exact findings and limits.


## Concrete review order and cross-file handoffs
Each numbered domain includes correctness, security and efficiency; this is one twenty-domain audit, not forty unrelated checklists.

| # | Principal source anchors | Handoff to trace |
| --- | --- | --- |
| 01 | contracts/*; domain/imports.py, commercial.py | browser values → validated model → canonical stored facts |
| 02 | api/access.py; services/access.py; contracts/access.py | login → portal-scoped session → revocation/reset |
| 03 | security/roles.py; services/business.py; TeamWorkspace.tsx | owner-created account → single team role → server permission |
| 04 | security/http.py; api/access.py; client.ts; vite.config.ts | browser origin → cookies/CSRF → endpoint |
| 05 | api/imports.py; config.py; access/passports services | byte/chunk limits → admission slots → rate limits |
| 06 | storage/local.py; storage/*_schema.py | transaction → foreign keys → rollback → disk exhaustion |
| 07 | local storage; imports/passports APIs and Sources/Invoice desk | uploaded bytes → references → removal → stale decisions |
| 08 | adapters/imports.py; jobs/import_worker.py; services/imports.py | untrusted archive/CSV/JSON → isolated parser → confirmed source |
| 09 | adapters/gemini.py; services/passports.py; InvoiceReview.tsx | upload → AI proposal → human confirmation → saved source |
| 10 | domain/commercial.py; passport evidence contracts/service | item evidence → four-way result → payment constraints |
| 11 | domain/reconciliation.py; services/runs.py; Reconciliation.tsx | active month/source revisions → matching → review |
| 12 | domain/vendor_intelligence.py; passports intelligence | saved invoice history → scores/signals → amounts |
| 13 | services/proposals.py; passports decisions; domain/actions.py | evidence fingerprint → approval → simulated release |
| 14 | services/cases.py, reports.py; adapters/reports.py | private facts → immutable history → bounded report download |
| 15 | WhatsApp adapter/services/jobs and passport_channels.py | signature/consent → replay checks → remote side effect |
| 16 | services/processes.py; domain/workflows.py, tax_guidance.py | node exit check → downstream staleness → completion |
| 17 | services/product_guidance.py, business.py; Assistants/Owner views | role-scoped saved facts → explanation → salary privacy |
| 18 | App.tsx; client.ts; shared.tsx; workspace.ts; role desks | account/company/month switch → request cancellation → screen |
| 19 | main.py; __main__.py; jobs/*; storage/local.py | startup lock → worker ownership → bounded shutdown |
| 20 | dependency manifests/locks; scripts; Vite config; README | clean checkout → build → local exposure → secret exclusions |

User confirmed Codex Security is now installed. Its Standard scan skill and tools are available. The earlier uninstalled note records the earlier state only. First the domain split, then Jainune references, then the plugin source audit. No heavy suite or push is planned.

## Reference review and scan start
Jainune references inspected: docs/LOGICAL_CORRECTNESS.md sections on failure ordering, state invalidation, bounded memory, startup/package integrity and concurrent ownership; backend/app/core/security.py; backend/app/workers/worker_pool.py; representative payment-service and security-test source. Their important transferable patterns are consumer-level contract checks, atomic state changes, precise resource ownership and safe retries. This is not a claim that the entire Jainune repository was read.
Codex Security Standard scan started: 84b965e8-786e-4e11-b0ff-5270c7a9df6b. Dedicated read-only preflight returned ready; independent baseline and architecture reviews are active. Four session slots are available. Daybreak account advisory was not_granted, which does not block source auditing. No heavy suite has run.
Confirmed upload defect evidence: backend/app/security/http.py private_upload permits only imports and passports/documents, while backend/app/api/passports.py defines passports/{id}/evidence-documents using bounded_upload. Requests over 65,536 bytes are therefore rejected at the JSON boundary before supporting-document validation. Planned exact-route fix and focused middleware/auth checks; not yet applied.
Removal design under review: original bytes may be purged independently; invoice removal must leave a read-only historical tombstone, exclude active totals, invalidate approval fingerprints and workflow exits, stop follow-up outbox eligibility and forbid later mutations. Historical purchase-source facts and prior financial events must be explicitly retained rather than silently erased.

## Resumed audit checkpoint
The two independent frontend/workflow reports have now been read. Applied source changes, awaiting focused verification: supporting-document upload boundary, DELETE body ceiling, bounded ASGI admission/keep-alive/shutdown, SQLite secure_delete for live deletion, malformed Gemini response handling, WhatsApp command/report role checks and write-transaction rechecks. No heavy suite, push, deletion feature or complete twenty-domain result yet.
Confirmed remaining findings: logout/login cookie race; multipart identities omit company/month; cross-invoice supplier drafts; cross-node workflow drafts; generated inline markup conflicts with preview CSP; missing payment observations default to zero; purchase supersession does not invalidate copied passport facts; independently attached case observations are not checked against current imports; partial-payment suggestions/approvals disagree with release limits; unknown vendor tax exposure shown as zero. The baseline scan's source-reviewed WhatsApp role finding has source fixes but still needs focused verification. Report claims must retain these limitations.

### Additional independent findings and approval constraint
Confirmed source findings: credential retry request hashes provide a fast password-guess verifier to a database/backup reader; supplier consent/watch authority survives CA/FOLLOWUP reassignment because actor_valid checks only coarse REVIEWER membership. Both require remediation and focused checks. Independent review also caught two regressions in unverified parent changes: absent payment amount must be guarded before money conversion, and optional empty supplier/IRN text must normalize before purchase-source comparison. Those are being corrected before verification.
Automatic approval rejected one proposed combined patch because it contained deletion of credential retry rows across all workspaces. The command did not execute. No retry history was deleted. A preserving/narrower credential binding approach is required; existing legacy receipts/backups must remain an explicitly recorded limitation until safely migrated.

### Verification checkpoint
Frontend type check and production build passed. Twelve small API-client tests passed, including different month/content upload identity and rejection before reading oversized bytes. New isolated backend audit checks: payment unknown/caps/purchase supersession/invoice removal passed; preserving credential receipt migration passed; future payment observation rejection passed. Supplier-role/upload check initially exposed a parent implementation error: background actors lack a browser session, so require_role could not be used with SimpleNamespace. Replaced that path with persisted actor_role; focused rerun pending result. Independently caught missing-payment conversion and optional empty purchase text regressions were corrected before the above checks. Original file removal retains financial history and blocks active invoice mutations. Legacy receipt migration command preserves rows/responses, is scoped to a supplied workspace and still needs application to the current local workspace. No heavy suite, live provider calls, push or whole-audit completion.

### Focused checks passed
The corrected supplier/upload test and two existing connected checks now pass: 3 passed in 40.02 seconds. Together with the earlier successful audit checks, verified paths cover a 100 KB supporting-document upload, FOLLOWUP denial of RUN, supplier authority revoked on reassignment to CFO, unknown payment facts staying unknown, controlled-payment cap with prior payment, purchase-source supersession staling approval, archived invoice hidden/immutable with retained payment history, preserving/scoped credential receipt transformation, future observation rejection, the original connected invoice workflow, and owner team/profile behavior. All modified backend source passes Ruff; frontend types/build and 12 API-client tests passed. The first supplier rerun exposed an incorrect test invocation after the application defect was corrected; that invocation was fixed and the successful result is above. No heavy suite ran. These are specific checks, not proof of zero bugs.

## Continuity checkpoint: finalization
Confirmed source fixes are complete. Seven distinct focused backend cases and twelve client checks passed across bounded runs; TypeScript and production build passed. The live backend was restarted and eight legacy credential retry records were migrated with history preserved. Remaining work is report finalization, not another heavy test run. Source coverage is partial (selected cross-system files), browser privacy fixtures were updated but not executed, and independent backup copies retain their own data. No commit or push was performed.


## Final result: 8 October 2026

The planned source-led audit and confirmed repairs are complete within the bounded scope below. Earlier checkpoint entries describe the state at that time; this section supersedes their pending status. Codex Security was subsequently installed and used with delegated frontend, workflow and security source reviews. Findings were assessed individually; report paragraphs describing existing controls or hypothetical attacks were not treated as confirmed bugs.

This is not exhaustive coverage of all 347 inventoried files. Selected cross-system source coverage is partial, with over 80 files examined across the reviews. No heavy regression suite or full browser role-by-role run was performed. No external AI score or zero-bug guarantee is asserted. No commit or push was made.

### Confirmed findings and repairs

| Finding / trigger | Consequence | Applied repair | Verification and limits |
| --- | --- | --- | --- |
| Supporting invoice evidence upload omitted from multipart route classification | PDFs/photos above the JSON ceiling failed before their upload handler | Classified supporting evidence as bounded multipart; bounded DELETE bodies too | Focused supporting-upload boundary test passed |
| Logout completes after a new login | Old logout could remove the new session cookie | Login stays gated until logout settles | TypeScript/build passed; full browser race reproduction not run |
| Upload retry identity lacked company/month and file contents | A changed upload could reuse the wrong request identity | Snapshot multipart data; bind metadata and SHA-256 file content to scoped retry identity; reject oversize before reading bytes | Twelve client tests passed, including scope/content/oversize checks |
| Supplier form survives invoice switch | Another invoice could inherit a contact/message draft | Key supplier form by invoice ID | Source reviewed and production build passed; manual navigation remains to check |
| Workflow form survives node switch | Notes or assignments could carry to another node | Key transition and assignment forms by node | Source reviewed and build passed; browser interaction not executed |
| Landing inline styles conflict with restrictive CSP | Dynamic book presentation could lose its styling | Use stylesheet classes for generated static book labels | Build passed; CSP retained |
| Missing payment observation defaults to zero | Unknown payment appeared confirmed as unpaid | Nullable paid amount plus observed date; future dates rejected; explicit observed facts required | Focused payment/date tests passed |
| Passport omits current purchase source from fingerprint | Superseded purchase evidence could leave an approval current | Bind source state/version/hash and canonical accepted facts; stale source invalidates approval and downstream process | Existing connected source-change test and focused checks passed |
| Case observations remain usable after source changes | Case closure, payment drafts or reports could rely on stale evidence | Recheck attached source fingerprints; show effective evidence-required state; propagate to dependent proposals/actions/reports | Cross-file source review; not a complete case/report regression run |
| Suggested or approved partial amount exceeds current release basis | Recommendation, approval and release could disagree | Cap by known base less paid and already released amounts; enforce same constraints on approval | Focused controlled-payment checks passed |
| Unknown vendor exposure converted to zero | Dashboard understated uncertainty | Preserve unknown exposure; show known subtotal and unknown count | Source reviewed; financial decisions still require known facts |
| WhatsApp command/capability relies only on coarse membership | Linked staff could perform work outside their assigned role | Current assigned role checked before command preparation/execution and report capability creation/download | Source checks and focused role boundary checks; no live Meta send |
| Supplier consent remains valid after reassignment | Queued automatic supplier work could continue under a disallowed role | Recheck persisted actor's current CA/follow-up role at consent, scan and dispatch boundaries | Focused reassignment check passed; already in-flight external send cannot be recalled |
| Credential retry receipts use fast password-derived hashes | A stolen SQLite copy offers a faster offline guess check than password storage | Use scrypt-bound receipt identities and versioned routes; preserving workspace-scoped upgrade | Migration test passed; eight existing live retry records protected; old backups remain independent |
| Malformed AI provider response escapes expected error handling | Unexpected server error instead of controlled unavailable response | Include malformed attribute shape in sanitized provider failure handling | Source and syntax/lint checks; live provider availability not guaranteed |
| Evidence changes while AI explanation runs | Answer could describe outdated decisions | Recheck current source/version after provider returns for intelligence and notice answers | Cross-file source review; AI still cannot approve or determine legality |

### Requested removal options

- **Remove original invoice file:** authorized account/CA role, explicit confirmation, expected version, idempotent operation and audit history. Removes stored original bytes; invalidates affected evidence and approvals. Saved financial history remains available.
- **Remove invoice from active work:** archives the active invoice, removes original bytes, revokes future supplier contact work and invalidates current approvals/process completion. History remains available; later ordinary mutations reject the removed invoice.
- **Delete unused source upload:** rejects processing or referenced sources, then deletes only unused parser records and unshared raw bytes. Checks references across runs, passports, cases, reports and WhatsApp. Retains deletion receipts/audit facts; old upload retries return source-removed instead of recreating deleted data. A focused removal/reference/retry test passed.
- SQLite secure deletion is enabled on write connections. This does not encrypt SQLite or erase previously copied backups, OS snapshots, browser downloads, WAL remnants or independently retained exports.

### Twenty-domain completion ledger

| Domain | Result / boundary checked | Remaining limit |
| --- | --- | --- |
| 01 Contracts | Nullable payment facts, future observation dates, matching removal contracts | No exhaustive generated-input/property suite |
| 02 Credentials | Receipt hardening and preserving migration; portal/session source reviewed | User-chosen short passwords remain allowed; backups not migrated automatically |
| 03 Roles | Current browser, WhatsApp and persisted supplier authority reviewed | No fresh exhaustive endpoint matrix execution |
| 04 HTTP | Upload route classification and request bounds corrected; origin/cookie controls reviewed | External tunnel/proxy configuration is operator responsibility |
| 05 Concurrency | Server concurrency 64, keepalive 5 s, graceful shutdown 30 s; existing admission/rate controls reviewed | No throughput, exact-millisecond or stress guarantee |
| 06 SQLite | Transaction/lock/foreign-key/write behavior reviewed; secure deletion enabled | No encrypted database, disk-failure campaign or host ACL installer |
| 07 Storage/removal | Versioned authorized removal, retained history and source reference guards | Copies/backups need separate retention handling |
| 08 Parsers | Existing fixed workers and bounded archive/parser admission inspected | No comprehensive adversarial document fuzzing |
| 09 OCR | Malformed response handling, upload identity and confirmation boundaries | Unknown facts stay unknown; no promise every scan/file extracts perfectly |
| 10 Four-way check | Item evidence path and connected purchase-source freshness reviewed | No exhaustive item/unit combinations run |
| 11 GST/month | Context identity and current purchase source invalidate stale decisions | Real GST fetching/filing remains unavailable |
| 12 Vendor risk | Unknown tax separated from known subtotal | Scores are rule-based signals, not verified vendor solvency |
| 13 Payment | Known observation and partial caps aligned with approval constraints | Bank remains simulated; no legal guarantee from matching alone |
| 14 Cases/reports | Source freshness propagated to cases, decisions and artifacts | Full notice/report lifecycle suite not run |
| 15 WhatsApp | Assigned roles, capability reads, supplier reassignment checked | No live Meta account round-trip in this audit |
| 16 Process/tax | Current purchase exit condition and stale downstream signatures | Legal references still require CA review |
| 17 Assistants/privacy | Saved-fact scopes and post-AI freshness reviewed | No broad prompt-injection campaign or legal validation |
| 18 Frontend | Logout/upload/context/form/CSP fixes; privacy fixtures updated | Updated browser fixtures not executed; visual/manual review remains |
| 19 Startup/efficiency | Live backend restarted; readiness and local website respond | No sustained load, browser memory or crash-injection benchmark |
| 20 Dependencies/build | Frozen project manifests inspected; TypeScript/contracts/build pass | No fresh advisory database scan or guarantee against unknown vulnerabilities |

### Checks actually completed

- Seven distinct focused backend test cases passed across the bounded runs: upload/role boundary, payment/current-source/removal behavior, preserving credential migration, future-date rejection, connected source-change workflow, team/profile workflow and unused-upload removal.
- Twelve lightweight frontend client tests passed.
- TypeScript no-emit check passed; 140 contract types regenerated; production frontend build passed.
- Ruff checked changed backend source, contracts and focused test code. Browser fixture syntax/format checks passed; these are not browser execution results.
- Existing workspace credential migration protected eight retry records without deleting their response/history records.
- Restarted backend reports ready on localhost:8000; localhost:3000 responds successfully.

### Independent review outcome and honest limits

The frontend review's five principal findings and the workflow review's five principal findings were repaired. An additional upload hashing memory issue was caught and corrected with pre-read size checks. Obsolete browser fixture assumptions were updated, but those browser tests were not run. Three principal security findings were confirmed: alternate-channel role bypass, weak credential receipt verifier and persisted supplier role reassignment. Other review notes described existing controls, requested additions or follow-up work; they were not all distinct proven exploits.

Selected inspected paths did not establish SQL injection, path traversal, arbitrary outbound URL injection or command injection. That is a bounded observation, not proof those bug classes are absent everywhere. Same-user OS access can read an unencrypted SQLite database. Old backups remain separate private copies. Financial truth still needs genuine purchase, delivery, GST and payment facts; automation cannot invent missing evidence.

A proposed broad credential-receipt cleanup was rejected by automatic approval review and did not run. It was replaced by the authorized, preserving workspace-scoped migration above. No pending approval or destructive cleanup remains.

## Completion checkpoint
The bounded twenty-domain source audit, confirmed repairs, safe removal features, focused verification and live restart are completed. Remaining manual/browser, stress, legal, integration, advisory and uninspected-source work is explicitly recorded above. Codex Security canonical report finalization is the final reporting step. No staging, commit or push was performed.

### Final reporting milestone
Codex Security accepted the final semantic draft and successfully validated/indexed the completed scan (84b965e8-786e-4e11-b0ff-5270c7a9df6b): three repaired security findings, twenty domain surfaces and explicitly partial coverage. The initial draft was rejected for a candidate-link field; it wrote nothing, and the accepted draft binds the retained WhatsApp candidate ID correctly. Canonical report: C:\Users\yashk\.codex\state\plugins\codex-security\scans\gstshield\04b2b42f880c54fa17bf24f9f65081c6d8de20a8_20261008T025625Z_2tpmz4g7\report.md. Reporting is finished. The broader unexecuted/manual/stress/advisory checks remain disclosed, rather than being represented as passed.


### Publication checkpoint
User authorized pushing the complete current codebase to the previously created new repository. Confirmed destination: Yash-7788/gstshield-hackathon, main; target checkout was clean. Publication scope includes application source, tests, plans and synthetic test documents. Local private database, backend .env, runtime logs, temporary screenshots and browser artifacts are excluded. Publication file scan found no configured-secret or recognizable provider-key matches. No heavy tests requested or run for this publication.

### Publication verified
Pushed main successfully to https://github.com/Yash-7788/gstshield-hackathon.git. Remote main verified at c40192c61e7ea925473525ea1858e243a41c5b86; publication checkout clean. Commit includes the complete current public source, tests, plans, synthetic testing documents and audit repairs. The final index scan covered 242 files and found no publication-secret/private-path matches. No heavy test suite was run. The new checkout C:\Users\yashk\Downloads\gstshield-hackathon is the clean baseline for Claude's second-round diff; the original working project and its local database remain in place.


### Round-two corrective milestone
User authorized repairing review regressions, publishing, starting both services and a full role walkthrough. Restored supported Gemini 3.1 model fallback; restored only GET shaped public report capabilities while keeping private routes blocked; imported sqlite3 for sanitized storage failure handling; fixed the line-length error. Updated shutdown test double to represent Thread.join/name. Twelve focused checks passed in 2.65s; backend source lint passed. No heavy suite or live provider calls. Initial harness lifespan mismatch was corrected before final passing run. Added matching fictional five-file test pack and role-by-role guide; no private database or credentials are published. Remaining work: sync/commit/push, restart/verify local services and present usage guide.
