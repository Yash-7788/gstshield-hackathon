# GST-Shield — build sequence, verification and hackathon readiness

> **Active local implementation (2026-10-04):** This is a website with a Python backend running on the PC. Authoritative storage is a private SQLite file under `backend/data/`; accounts are provisioned locally and browser access uses revocable sessions. No external database, hosted identity, cloud storage or application hosting is selected. Phases 1–12 are complete and locally verified. Phase 11 passed the full backend regression (343 passed, 1 Windows privilege-related skip). Phase 12 passed 22 browser checks, built-preview checks and real 100/2,000-row website measurements. See 05 for dated evidence. Phase 13 local WhatsApp integration is implemented with focused checks; Meta setup and physical-phone acceptance remain pending. Phase 14 is not started. Full Phase 13 regression was stopped at the user’s request. The landing page/design is pending. The user authorized a new internal website in Phases 8–9; real WhatsApp remains Phase 13.

## Active implementation phase plan

Read before coding: product scope (01), installed stack/configuration (02), backend/data behavior (03), website/WhatsApp connection (04), this plan (05), security/privacy (06), GST evidence boundaries (07), and API alignment (08). The original report/review and Engineering Headstart remain supporting context.

Latest user decisions: local PC execution and local PC storage; proceed one phase at a time; review each phase before starting the next; expand the full application plan with dedicated frontend improvement/connection/security/smoothness and backend security/performance phases. Do not create hosting infrastructure or external databases. The latest user instruction authorizes building the internal application now; the separately supplied landing page/design is later work. The phase order is a dependency order, not a ranking of importance. The user plans to finish all 14 phases before the hackathon starts; the two hackathon days are reserved for selectively scoped deferred additions with prerequisites prepared beforehand.

## Expanded application phase map

The active plan now contains **14 phases**. Phases 1–12 are complete and locally verified, including the Phase 11 backend regression and Phase 12 connected website/performance checks. Phase 13 local WhatsApp integration is implemented with focused checks; Meta setup and physical-phone acceptance remain pending. Phase 14 is not started. Full Phase 13 regression was stopped at the user’s request. Frontend work builds the authorized internal application; the landing page/design will be supplied separately later. Every phase has its own deliverables and a correctness/security/edge-case review gate.

| Phase | Work | Area | Status |
|---|---|---|---|
| 1 | Local runtime and HTTP foundation | Backend | Complete |
| 2 | Local storage and private access | Backend | Complete |
| 3 | File imports, checking and confirmation | Backend | Complete and locally verified |
| 4 | GST reconciliation and human review | Backend | Complete and locally verified |
| 5 | Backend reports, cases and evidence workflow | Backend | Complete |
| 6 | Business workflows for all six original problems | Backend | Complete and locally verified |
| 7 | Backend security and failure review | Backend | Complete and locally verified |
| 8 | Frontend inspection, cleanup and complete screens | Frontend | Complete |
| 9 | Frontend and backend connection | Both | Complete |
| 10 | Frontend security and privacy review | Frontend | Complete and locally verified |
| 11 | Backend performance and resource efficiency | Backend | Complete and locally verified |
| 12 | Frontend smoothness, speed and usability | Frontend | Complete and locally verified |
| 13 | WhatsApp connection and channel review | Both | In progress; physical-phone gate pending |
| 14 | Whole-application regression and hackathon rehearsal | Both | Not started |

The sequence is a dependency order, not a ranking of importance. Security and responsiveness are part of feature implementation from the start; Phases 7, 10, 11 and 12 are focused reviews of working code. Do not postpone essential safeguards or fixable blocking behavior to those later reviews.

### Verification cadence agreed during Phase 6

Continue coding one coherent phase at a time, with targeted review before the next phase. The user requested faster future delivery rather than repeating the full suite for every phase. From now on, run lint/format/syntax plus affected correctness, security, edge-case and previous-phase integration checks after each phase; run one full regression suite after a batch of two or three related phases. Do not skip focused checks until the batch ends.

Run full regression sooner for major shared storage/schema, authentication/session, core monetary/matching changes or a discovered regression whose scope is not contained. Run it once after final edits, rather than repeatedly during feature drafting. A failed full run requires diagnosis and a focused reproduction before another full attempt. Keep evidence explicit: passing targeted checks is not the same as a passing whole-suite gate. Phase 6 completed its full check under the original gate; subsequent phase batching uses this cadence. GitHub full-suite CI continues asynchronously on pushes; its remote results remain separate evidence and failures require diagnosis. The internal application is now authorized independently of the later landing page. Missing provider prerequisites prevent real channel activation and acceptance; the user authorized the local integration first.


## Capability status and remaining-work ledger

This ledger reconciles the original six business problems with the active eight MDs and the recorded Phase 1–6 backend implementation. IMPLEMENTED means locally verified backend functionality, not a finished website screen. PARTIAL identifies the delivered foundation and the missing operational behavior. PLANNED has no implementation proof yet. CONDITIONAL requires external setup/evidence. EXCLUDED is an intentional scope boundary, not a forgotten future phase. Update this ledger and the affected resource contract when an implementation gate passes.

| Existing planned capability | Current status and what is missing | Completion phase / acceptance owner |
|---|---|---|
| Local runtime, private PC storage, identities and workspace roles | IMPLEMENTED: local HTTP, private SQLite, sessions, ownership, offline backup/restore | 1–2 complete; whole-backend review 7 |
| Purchase CSV/XLSX and supported portal-table imports | IMPLEMENTED: bounded parsing, mapping, errors, explicit confirmation and retained sources | 3 complete; browser use 8–9 |
| Official GSTR-2B JSON/layout support beyond current adapters | CONDITIONAL: canonical JSON is synthetic; official layout/unsupported sections cannot be called supported without an authorized fixture | 6 must inventory actual coverage and validate a needed adapter only with a permitted sample; otherwise record the concrete pending sample, preserve supported demo path |
| Exact comparison, duplicate detection, fuzzy suggestions and human decisions | IMPLEMENTED: persisted explanations/totals, bounded matching and versioned review; fuzzy suggestions are not auto-accepted | 4 complete; browser use 8–9 |
| New snapshot/source supersession | IMPLEMENTED: retained-purchase actions compare later committed snapshots, retain history and require renewed review on meaningful change; unrelated purchases remain separate | 6; website 9 |
| Supplier missing/wrong-invoice investigation | IMPLEMENTED: discrepancy actions retain recorded GST, correction drafts, supplied contacts and operator attempt history | 6; website 9 |
| Work queue/action history for unresolved issues | IMPLEMENTED: scoped paginated actions, state/due filters, owners, dates, audit history and processing status | 6; screens 8, connected 9 |
| Supplier reminder draft and contact-attempt history | IMPLEMENTED: action-specific NOT_SENT drafts and dated unverified operator attempts; sending remains conditional Phase 13 | 6; website 9 |
| MSME/payment facts and reviewed payment proposal | IMPLEMENTED: recorded payment/classification facts, exact remaining balance/unknowns, linked review actions and recorded-date reminders; proposal remains non-executing | 5 complete for foundation; 6 for remaining workflow |
| Reversal/reclaim evidence case | IMPLEMENTED: original claim/reversal and matching supplier evidence drive conservative candidates; reviewed outcome and separately evidenced user filing observation remain distinct | 5 complete for foundation; 6 for remaining workflow |
| Reclaim review worksheet/preparation and filing-outcome tracking | IMPLEMENTED: authenticated JSON review worksheet, compact action-aware PDFs and separate dated user filing observations; no government execution or guarantee | 6: distinguish candidate, reviewed proposal, separately evidenced recorded filing and unresolved/rejected outcome |
| IRN format/evidence review | IMPLEMENTED: linked missing/malformed/unverified IRN actions and evidence history; format never means authenticity | 5 complete for foundation; 6 for action workflow |
| Trusted signed IRN authenticity/current status | CONDITIONAL/STRETCH: no trusted verification adapter/keys/contract proof | 6 records unsupported status; actual verification deferred until the prerequisite is validated, never a false green badge |
| Notice case and private evidence pack | IMPLEMENTED: notice facts/checklist, linked action, recorded-date reminder, preparation PDF, accepted review and documented user submission observation | 5 complete for foundation; 6 for remaining workflow |
| Automatic local due-review reminders and evidence-change alerts | IMPLEMENTED: bounded local monitor, persisted checkpoints/errors, deduplicated date events, startup and authenticated-read catch-up; PC/backend must run | 6: durable deduplicated tasks while backend runs, overdue catch-up after restart; visible in website 9 |
| Private reports and generic proposal/error exports | IMPLEMENTED: bounded PDF/CSV snapshots/private downloads plus compact action/history coverage, stale action-set checks and JSON worksheet | 5 complete; extend for 6, browser 9 |
| Internal website screens and real operations | IMPLEMENTED: six original business sections plus Phase 13 channel controls, real API journeys and browser privacy checks; supplied landing page/design remains pending | 8–10 complete; 12 measured usability |
| Whole-backend security/failure and measured performance review | IMPLEMENTED: bounded backend security review and measured local workload/efficiency checks | 7 and 11 complete; combined rehearsal 14 |
| WhatsApp linking, commands, imports, status, private report access and unlink | PARTIAL: local signed adapter, durable commands and website controls implemented; physical-phone integration unverified | 13: account/assets, permitted reachable callback and budget proof, real-phone gate |
| Owner/reviewer reminders and supplier follow-up through WhatsApp | PARTIAL/CONDITIONAL: opted-in linked reminders and draft-specific supplier consent/outbox implemented locally; real delivery unverified | 13: explicit enablement, linked/consented verified recipient, window/template/account entitlement and bounded outbox; pending if setup is unavailable |
| Government filing/IMS write actions, bank execution/escrow | EXCLUDED from corrected hackathon scope; an observation/proposal/export is not execution | No implementation phase; explicit unsupported state throughout 6/9/13/14 |
| Guaranteed recovery, guaranteed eligibility/compliance or notice dismissal | EXCLUDED claims; an outcome controlled by external facts/review cannot be guaranteed by adding a task | No implementation phase; actual recorded outcomes may be tracked in 6 |
| AI explanation/OCR, direct ERP sync, subscriptions and extra official tables | OPTIONAL/DEFERRED in existing pack; no dependency for the six-problem local workflow | Keep disabled/deferred unless scope and evidence are explicitly changed; do not call them completed |
| Combined six-problem demonstration and failure/restart proof | PLANNED: backend milestones are not overall product completion | 14; must expose conditional/unsupported integration status honestly |

No core Phase 6 automation may be dropped under the older general instruction to remove optional automation when time is tight. That instruction applies to the optional/deferred integrations above. This ledger, the Phase 6 acceptance matrix and implemented contract status govern the current build; the three foundation documents remain historical references.

### Phase 1 — local runtime and HTTP foundation (complete)

Deliverables:

- Reproducible Python 3.13 environment, minimal required dependencies and a committed lockfile.
- A single local launch command using the actual validated HOST/PORT/logging configuration.
- Complete, checked-in environment example aligned with every setting the loader recognizes.
- Fail-fast validation: strict booleans, positive bounds, finite exact decimals, cross-field constraints, single worker and local origins/paths.
- Public liveness and readiness endpoints with the agreed data/meta envelope.
- Consistent expected HTTP, validation and unexpected-error envelopes without private inputs or traces.
- Local Host/Origin restrictions, request IDs, security/no-store headers and CORS covering server errors.
- No uploads, customer data, authentication bypass, SQLite schema, provider requests or placeholder feature routes.

Review gate:

1. Install from the frozen lock and import/run the application on the local PC.
2. Test invalid config, template/loader drift, secret redaction and environment precedence.
3. Test real ASGI request handling: healthy startup/shutdown, unknown routes, method failures, validation failures and unexpected exceptions.
4. Verify local origin/Host controls, preflight behavior and CORS/security headers on errors.
5. Run lint, formatting, syntax compilation, regression tests and a real loopback HTTP smoke check.
6. Record what is implemented and what remains a future setting or feature. Readiness must not claim a database check before persistence exists.

Completed locally on 2026-10-03: 78 tests passed, including real local process/socket startup; Ruff lint/format, syntax compilation and frozen dependency installation passed. Configuration coercion, malformed dotenv handling, API port alignment and exception-log redaction defects found during review were fixed and covered by regressions. See the [verification record](../backend/README.md#phase-1-verification-record). GitHub workflow results are separate from this local proof. Phase 2 has completed its local review gate; its verification record is maintained in the backend README.

### Phase 2 — Local storage and private access (complete)

Owner: backend. Outcome: Store data and establish private access on the PC before any document-handling route is opened.

Deliverables:

- Use Python's built-in SQLite driver and one database file under backend/data; no external database service, ORM, Redis or hosted identity dependency.
- Design the initial tables and relationships from the shared resource contracts: sessions/identities, workspaces, registrations, resource ownership and version metadata. Define how later feature tables extend this baseline.
- Choose and document a simple local-demo sign-in/session mechanism, including bootstrap, expiry, logout and recovery. An unapproved browser origin, loopback address or DEMO_MODE flag must never grant private access.
- Use atomic transactions, parameterized SQL and foreign-key checks. Store financial amounts in an exact representation, with ownership checks in every applicable lookup.
- Keep database/source/artifact paths inside the private data directory; do not use uploaded filenames as filesystem paths. Define retained-data and disk-space limits before writes.
- Define backup, restore and corruption handling. Refuse unsafe or incompatible storage rather than silently creating a replacement empty database.
- Make readiness reflect the initialized local storage when this phase is implemented. Keep provider calls out of readiness checks.
- Document what survives restart, what expires, how users recover access, and how future schema versions are handled without losing existing files.

Review gate:

1. Prove retained data with an actual process restart and a backup/restore round-trip.
2. Use two independent identities/scopes and prove that changing IDs cannot expose the other's resources.
3. Exercise rollback, duplicate creates, invalid ownership relationships, expired/revoked sessions and refused unauthorized writes.
4. Check outside-directory paths, unavailable/corrupt storage, exhausted quotas and failed startup without exposing private data.
5. Record the chosen access/storage contracts for the frontend handoff; no private routes before these checks pass.

### Phase 3 — File imports, checking and confirmation (complete and locally verified)

Owner: backend. Outcome: Turn supported documents into checked, reviewable inputs without treating unsupported or partial data as a successful import.

Deliverables:

- Add only the parser libraries required for CSV/XLSX purchase inputs and explicitly labeled canonical-demo portal JSON.
- Enforce bytes, rows, columns, cell lengths, nesting depth, archive entry count and decompressed size at the actual reading/parsing boundaries.
- Inspect supported content and encoding; reject malformed archives, unsupported layouts and unsafe spreadsheet content according to the import policy.
- Preserve exact monetary values, source context, row numbers and unknown tax components. Do not convert an absent value to an invented zero.
- Implement mapping preview, rejected-row explanations, accepted/rejected counts and explicit confirmation when an import is partial.
- Hash source bytes and define duplicate/retry behavior without confusing identical filenames with identical content.
- Use bounded processing and truthful job states; keep health/status requests responsive during parsing. Handle interrupted jobs on restart explicitly.
- Persist checked imports and their ownership/context. Neither an upload nor a parser exception may leave a silently confirmed partial import.

Review gate:

1. Run independently prepared valid, malformed, ambiguous and unsupported fixtures.
2. Check byte limits including streamed uploads, oversized expansion, excessive rows/cells, unusual encodings and spreadsheet formulas.
3. Prove that a retry does not create duplicate confirmed data and an interrupted operation does not announce success.
4. Compare preview/confirmation counts with persisted rows, including errors and unknown tax components.
5. Measure parsing time and memory for the demo and maximum supported input sizes; record the initial baseline for Phase 11.

### Phase 4 — GST reconciliation and human review (complete and locally verified)

Owner: backend. Outcome: Produce explainable matching results and exact totals, with an explicit human decision for suggestions and ambiguity.

Deliverables:

- Implement exact matching gates using registration, period, invoice identity, dates and the selected monetary policy.
- Detect duplicates on both sides before assignment. Keep fuzzy candidates separate from accepted exact matches.
- Handle tied/competing candidates and unique assignment so one source row cannot be counted as matching several rows.
- Preserve missing fields and evidence limitations; do not describe a similarity score as a probability or legal approval.
- Keep monetary calculations exact and derive counts/totals from committed classifications rather than scattered route-specific calculations.
- Persist source IDs, matching policy version, run versions and review history so a result can be reproduced and explained.
- Use expected-version checks for review actions; reject stale decisions and make repeated operations safe.
- Expose paginated/filterable results and truthful job progress suitable for the website and later WhatsApp use.

Review gate:

1. Compare against independently calculated golden results rather than accepting the engine's own output as the expected answer.
2. Cover paise boundaries, missing values, duplicate invoices on either side, ties, competing candidates and shuffled input order.
3. Prove no double counting and agreement between the result list, category counts and financial summary.
4. Check concurrent/stale review decisions, retries and restart-visible run state.
5. Record matching timings and candidate counts at demo/maximum sizes without weakening correctness gates to get faster results.

### Phase 5 — Backend reports, cases and evidence workflow (complete and locally verified)

Owner: backend. Outcome: Provide the case/evidence, proposal and downloadable-report foundation. Operational follow-up and cross-snapshot business workflows belong to Phase 6.

Deliverables:

- Implement the bounded case/evidence timeline and proposal workflow already specified in the planning pack; preserve ownership, versions and audit history.
- Generate reports from the committed run and review state, including source context, sample-evidence labels and uncertainty.
- Support safe report/export text and filenames. Treat source/vendor text as untrusted content in report generation and spreadsheet-compatible exports.
- Keep generated files private and downloadable only through the selected authorized download flow.
- Store artifact status, versions and hashes so a failed generation cannot be shown as a ready download.
- Define repeated report requests, expiry, retention and cleanup behavior without deleting unrelated user files.
- Expose the completed backend operations through the shared contract, including errors and job state used by the website.
- Keep payment/proposal exports clearly labeled; producing a report or proposal never executes a payment or establishes legal eligibility.

Review gate:

1. Compare report figures and evidence against the committed result summary after a human review changes it.
2. Test denied cross-scope downloads, stale/expired downloads, unavailable artifacts and safe user-controlled text.
3. Exercise repeated generation, interrupted writes, cleanup and restart behavior.
4. Open generated artifacts and check layout/readability as well as content; empty or corrupted output must not pass.
5. Confirm the case/report/proposal foundation is complete; do not count manual case capture as completion of the original business workflows. Complete Phase 6 before the focused backend security review.

### Phase 6 — Business workflow completion for the six original problems (complete)

Owner: backend, with contract and future screen alignment. Outcome: Turn the existing import/reconciliation/case/report foundation into actionable tracking for every original business problem. The local review gate passed; the full-suite and final focused checks are recorded below. It is not functionality delivered by Phase 5.

The roadmap was corrected on 2026-10-03 because its previous later phases covered security, screens, integration and performance without explicitly assigning the missing operational workflows. Phases 1–5 retain their completed status and verification evidence. The former Phases 6–13 become 7–14. Adding this phase does not authorize starting another phase before its predecessor's review gate passes.

#### Required problem-to-workflow coverage

| Original problem | Existing foundation | Required Phase 6 behavior | Evidence of completion |
|---|---|---|---|
| 1. Missing or wrongly reported supplier invoice | Missing/mismatch results, manual review, source provenance | Automatically create a deduplicated investigation action from a committed qualifying result; record correction requests, responsible reviewer and next review date; compare later confirmed snapshots and propose follow-up when evidence changes | A synthetic invoice with INR 20,000 recorded tax is missing, receives a supplier follow-up draft, then appears in a later snapshot; the system proposes review without declaring the credit claimed or legally eligible |
| 2. MSME/payment timing risk | MSME review case, payment facts, non-executing proposal | Track classification, acceptance/terms evidence, paid/unpaid amounts and explicitly recorded review dates; surface due/overdue review tasks and missing facts | Partial payment updates remaining recorded balance and the pending task; unknown acceptance/classification stays unknown; no universal 45-day deadline, fixed penalty or guaranteed compliant tax hold is invented |
| 3. Forgotten reversal/reclaim review | Separate Rule 37 and Rule 37A cases and observations | Record original claim, reversal amount/reason/period and later observations; automatically create a deduplicated review task when supported facts change; record reviewer outcome and separately evidenced actual filing | A previously reversed amount with later supplier-filing evidence becomes a reclaim-review candidate; first-time missing credit is not mislabeled a reclaim, repeated observations do not produce repeated alerts |
| 4. E-invoice/IRN problems | IRN review case, format-only evidence | Route missing, malformed or unverified IRN evidence to a correction/review task with provenance and applicability uncertainty; request supporting evidence | A fabricated 64-character hexadecimal IRN remains unverified; a missing IRN creates a review action rather than a blanket declaration that the invoice is fake |
| 5. Notice/evidence readiness | Notice case and evidence PDF | Track notice reference, recorded response date, evidence checklist and reviewer action; create due-review reminders and an evidence-backed response preparation pack | Missing supporting facts remain visible; approaching recorded response date raises a task; a downloaded PDF does not mark the notice submitted, accepted or resolved |
| 6. Manual reconciliation and untracked supplier chasing | Bounded matching and human review | Provide a consolidated work queue, supplier reminder drafts, follow-up history, next-action dates and deduplication shared with the other five workflows | Reviewer can see outstanding actions and previous attempts without redoing matching; later evidence updates the same tracked issue without losing its history |

The original report's legal claims remain subject to document 07 and the foundation review. The INR 20,000 fixture is a recorded GST amount awaiting review, not an automatically recoverable amount or an income-tax calculation. No government polling, filing, bank execution or escrow integration is a prerequisite for this bounded local phase.

#### Deliverables and implementation order inside this phase

1. Read 01, 03, 07 and 08, inspect the real Phase 1–5 services, and map each required workflow to existing resources before changing code. Define independent scenario expectations before implementation.
2. Define an explicit business-action contract: affected invoice/result/case, reason, source versions, evidence provenance, owner/reviewer, next review time and reviewed outcome. Keep lifecycle separate from legal eligibility and actual filing/payment facts. Align exact fields/enums/errors in 08 before using them in routes or future screens.
3. Implement a bounded, paginated work queue and auditable action transitions. Automatically derive eligible tasks after a successful run, a reviewed case/evidence change and a due-time check; failed or stale processing must not publish a false alert. Reuse live membership/role checks, expected versions, atomic transactions and existing retry/idempotency rules. A stale run or changed case must require renewed review. Record a resolution reason; allow explicit reopen when new evidence contradicts it.
4. Implement cross-snapshot comparison with explicitly selected compatible registration/period/document context. Preserve earlier snapshots and decisions. Newly appearing, disappearing or changed rows are evidence changes, not automatic proof of supplier compliance. Reject ambiguous identity, duplicate rows and unsupported comparisons rather than automatically closing an issue.
5. Implement supplier follow-up drafts using recorded invoice facts and deliberately provided contacts. Keep drafts, operator-recorded attempts and eventual verified delivery statuses distinct. Never infer a contact from unrelated data or fabricate a successful send. Outbound WhatsApp sending belongs to Phase 13 with its recipient/consent checks.
6. Implement separate reversal/reclaim review tracking and MSME/payment review actions. Represent absent claim/reversal/payment/filing evidence as unknown. Use uploaded or explicitly recorded observations with source labels. A new 2B match alone cannot prove Rule 37A reclaim readiness. Rule 37 buyer payment facts and Rule 37A supplier filing facts must not overwrite one another.
7. Implement IRN evidence tasks and notice readiness/actions. Keep format checking distinct from trusted authenticity verification. Use an explicitly recorded, reviewed notice response date; do not impose a universal response period from the pitch. Keep drafted response, recorded submission and recorded resolution separate.
8. Implement automatic due-review checks while the local backend is running, plus bounded overdue catch-up on startup and fresh authenticated due queries. Use persisted dates, bounded batches and stable deduplication, and document the check interval and testable behavior. No reminder can run while the PC/backend is off. Startup must surface overdue actions without replaying outbound sends. Do not add a cloud scheduler, Redis or an external database.
9. Update reports and summaries to show outstanding actions, dated observations and uncertainty. Include the existing planned reversal/reclaim review worksheet and notice response preparation handoff. Separate a review candidate, a reviewed proposed amount, an operator-recorded actual filing/submission with dated evidence, and its observed outcome; never mark a worksheet download as a filed return. Completed tasks must retain history; stale historical reports must not appear to represent the latest action state.
10. Extend SQLite only with a validated additive upgrade, backup/restore proof and documented finite retention/quota behavior. Add environment settings only when implemented and update the example with validation/defaults. Use normal responsibility-named files and direct edits, following the established phase style.

Any computed statutory deadline or legal recommendation needs a verified, dated policy, sufficient case facts and explicit evidence labeling. Without that policy, expose a user-recorded review date and missing-information action; do not silently ship a guessed statutory engine. Trusted IRN authentication remains unavailable until its verification contract and evidence are established.

#### Tax filing and recovery scope clarification

The user asked to include automatic tax filing or guaranteed recovery in this phase if they are part of the existing plan. Checked against the corrected pack: 07 says the hackathon produces a review worksheet rather than a filed return and labels IMS/government writes simulated/read-only; the foundation review explicitly removes autonomous filing and guaranteed legal/recovery outcomes from the initial demo. Therefore neither is an omitted implementation task. The original pitch's autonomy/guarantee language does not override those corrected boundaries.

Include the supported filing workflow instead: retain original claim and reversal facts, automatically surface evidence-backed review candidates, prepare the review worksheet/evidence handoff, record an explicit reviewer decision, and separately capture actual filing/reclaim observations supplied by an authorized user. Track observed amounts/outcomes without calling proposed amounts recovered. Government submission stays unsupported; no portal credential collection or login automation is added. This implements the existing preparation/tracking plan without inventing a filing provider integration.

#### Review gate

1. Run all six independently prepared scenarios above through real backend APIs, not direct test database edits. Each must identify the affected record, persist the next action, accept new evidence and show an explained review outcome/report.
2. Include missing and contradictory facts, different periods, reused invoice numbers, duplicate/new snapshots, partial payment, original credit never claimed, reversal without amount, repeated filing observations, unverified IRN and missing notice documents. Unknown inputs must not become eligibility, compliance or successful filing.
3. Prove exact recorded amounts agree across result, case, work queue and report without double counting exposure or implying money saved. A proposal or reminder draft never modifies actual payment/return status.
4. Exercise two scopes, VIEWER denial, revoked membership, forged resource IDs, CSRF, concurrent/stale transitions and repeated commands. User text in drafts/reports remains safely rendered/exported.
5. Prove actual process restart and backup/restore preserve tasks, review dates, observations and audit history. Repeated startup/time checks must not duplicate tasks or claim external delivery.
6. Run affected Phase 1–5 regressions and full phase-completion checks once changes are final. Record actual dependency/lint/syntax/test results and bounds. Compare the completed operations against all six problems before marking Phase 6 complete.
7. Produce a screen-to-operation handoff for Phases 8–9 and a channel handoff for Phase 13. All planned routes become implemented authority only after code and tests exist; current OpenAPI remains the source of existing endpoints.

A generic case form or PDF alone does not pass this phase. Passing it demonstrates local evidence and action tracking for the six problems; it does not establish legal entitlement, guarantee recovered tax or complete the website/phone interfaces.

### Phase 7 — Backend security and failure review (complete)

Owner: backend. Outcome: Review the working backend as a whole for access loopholes, malformed inputs and recovery failures.

Deliverables:

- Map every implemented route and file operation to its required identity, ownership, state and limits; review real code paths rather than only checklists.
- Verify sign-in/session expiry/revocation, role or scope restrictions, download controls and changing resource IDs.
- Review SQL parameters, safe file paths, upload parsing bounds, generated exports and every private-data logging path.
- Check allowed website origins and the selected session mechanism together; add request-forgery protections appropriate to that mechanism.
- Exercise repeated requests, concurrent operations, stale versions, duplicate job creation and inconsistent source contexts.
- Verify failures on full/unavailable disk, interrupted processing and restart without silent success, data loss or unintended replay.
- Review actual locked dependencies for known applicable issues; change a dependency only with compatibility and regression evidence.
- Fix causes and add focused regressions. Keep this a bounded hackathon review with a written list of accepted limitations.

Review gate:

1. Demonstrate denied access with two scopes and deliberately altered IDs/session state.
2. Run malicious/malformed file cases and prove limits apply before unsafe allocation or processing.
3. Confirm responses, logs and public diagnostics reveal no credentials, document contents or private ownership details.
4. Rerun affected correctness/import/report regressions after security fixes.
5. Record findings, fixes and remaining restrictions; passing this phase is evidence for the implemented backend scope.

### Phase 8 — Frontend inspection, cleanup and complete screens (complete — 2026-10-04)

Owner: frontend. Outcome: Build the authorized internal application screens, ready for real backend connection. The user's landing page/design will be integrated later.

Deliverables:

- The user authorized a new internal application on 2026-10-03. Select and verify a compatible minimal client stack, lockfile, local build/start commands and public environment example. Landing-page assets are not required for this work.
- Use a restrained accessible internal layout. Record screens/actions and contract coverage; reserve the separately supplied landing page and final visual design for later integration.
- Complete the required screens: private access/context selection, imports, mapping/confirmation, job progress, results, review, cases, business work queue, supplier draft/history, due-review actions and reports. Expose every Phase 6 problem workflow with honest evidence/unknown labels.
- Make empty, loading, error, expired-session and unavailable-feature states explicit. Label any temporary sample/mock state clearly during this phase.
- Use consistent navigation, spacing, typography, tables, forms, feedback and mobile/desktop layouts.
- Add basic keyboard support, visible focus, usable labels and readable financial text; confirmations must distinguish a run, a review, a report and a reset.
- Keep one source for shared UI types/formatting and prepare a screen-to-operation map against document 08.
- Apply safe text rendering and keep credentials out of frontend code from the start. A later security phase does not authorize insecure placeholders.

Review gate:

1. Run the internal application's clean install/build using its lockfile and inspect every required screen.
2. Exercise navigation, back/forward behavior, keyboard controls, resizing and mobile layouts.
3. Document every remaining simulated operation; a mock reply cannot count as connected functionality.
4. Check that money/context/status labels align with backend meanings and unavailable actions cannot appear successful.
5. Record the inspected stack and frontend environment example without publishing backend secrets.

### Phase 9 — Frontend and backend connection (complete — 2026-10-04)

Owner: both. Outcome: Make each website action use the real local backend and display the same persisted truth.

Deliverables:

- Implement one API client using the actual frontend framework and the access contract settled in Phase 2.
- Align fields, routes, enums, exact monetary strings, date/period formats, pagination and error shapes with document 08 and the implemented backend.
- Replace mock operations incrementally with real private access, upload, preview/confirmation, run, progress, review, cases, business actions, supplier drafts/history, due-review tasks, reports and downloads.
- Keep state scoped to the active identity/workspace/registration/period; clear private state when logging out or switching scope.
- Handle expired access, version conflicts, invalid input, unavailable backend and interrupted requests with actionable recovery.
- Prevent duplicate mutations from double clicks/retries using the backend's operation rules. Do not treat an uncertain request as proof it failed.
- Cancel or ignore obsolete requests after context changes; an old reply must not overwrite newer selected-context data.
- Configure the actual local website/API addresses and browser permissions together. Keep large result lists bounded and poll only relevant active work.

Review gate:

1. Complete a real sign-in-to-import-to-review-to-report journey and each of the six Phase 6 business scenarios through the website without replacing replies with samples.
2. Compare displayed counts, money and report figures with the same backend run after a review change.
3. Exercise browser refresh, backend restart, logout, context switching and a delayed reply from an old context.
4. Check double submissions, failed requests, expired sessions, stale reviews and recovery without duplicate work.
5. Verify the website build and generated/shared types agree with the backend contract.

### Phase 10 — Frontend security and privacy review (complete and locally verified)

Owner: frontend. Outcome: Review the actual browser application and its connection for data exposure and unsafe user-controlled content.

Deliverables:

- Review every place that displays imported text, filenames, supplier names, backend errors and report links; render untrusted values safely.
- Avoid putting untrusted content into executable HTML/script contexts. Inspect any rich-text rendering rather than assuming a framework makes all uses safe.
- Check frontend bundles, public environment variables, logs and storage for privileged backend/provider credentials and private document data.
- Verify logout, expired access and scope changes clear private screen/cache state. UI hiding alone must never authorize or deny a backend operation.
- Review the chosen session storage/cookie mechanism with backend authorization; verify request-forgery protections where applicable.
- Restrict navigation/download URLs and avoid placing secrets or private records in query strings, public telemetry or copied debug output.
- Check browser framing/content policies appropriate to the actual website build; test them against real functionality instead of breaking the supplied site with guessed settings.
- Add focused browser regressions for the concrete exposure paths found, retaining the backend enforcement of all private actions.

Review gate:

1. Put script-like text into representative imported fields and prove it stays harmless display text.
2. Attempt private routes/actions after logout or expiry and after switching identity/workspace.
3. Inspect the built website and browser storage/network output for leaked privileged credentials.
4. Exercise cross-site request attempts appropriate to the selected session mechanism and verify backend rejection.
5. Confirm security changes preserve real uploads, reviews, navigation and authorized downloads.

### Phase 11 — Backend performance and resource efficiency (complete and locally verified)

Owner: backend. Outcome: Measure and improve the real local workload while preserving exact results and bounded resource use.

Deliverables:

- Use the actual demo PC and fixed synthetic datasets; record input size, backend commit, runtime, database size and test conditions.
- Measure upload/parse, matching, summary queries, review writes and report generation separately; include health/status responsiveness during work.
- Compare the 100-row demo with the supported maximum (currently 2,000 rows per source), repeated runs and competing requests within configured limits.
- Identify actual slow queries, excessive candidate comparisons, repeated work, unbounded result loading and file/disk churn before editing.
- Add targeted indexes/query changes or matching candidate reductions only after proving they preserve ownership and matching correctness.
- Bound returned pages, processing buffers, queues, temporary files and retained state; clean up resources on success and failure.
- Use controlled local processing/offloading where needed so expensive work does not freeze other requests. Do not add cloud workers or Redis for this hackathon.
- Repeat the same measured scenario after each justified change and retain the simplest change that meets an agreed local demo budget.

Review gate:

1. Record comparable before/after time and memory measurements, with first-run and repeated-run behavior distinguished.
2. Prove golden matching results, exact totals and access isolation remain unchanged after optimization.
3. Check health/progress responsiveness, queue backpressure, cancellation/restart recovery and repeated-run resource growth.
4. Exercise the largest supported dataset without uncontrolled memory, disk usage or silently dropped work.
5. State remaining bottlenecks and agreed operating limits; no unmeasured promise of zero lag or an arbitrary completion time.

### Phase 12 — Frontend smoothness, speed and usability (complete and locally verified)

Owner: frontend. Outcome: Make the connected website responsive and predictable during the real demo flow.

Deliverables:

- Profile the actual connected website on the demo PC/browser and a representative small-screen device; distinguish backend waiting from browser rendering delays.
- Measure initial load, navigation, result-table scrolling/filtering, review clicks, upload feedback and report initiation.
- Fix measured causes such as repeated rendering, overly large tables, duplicate requests, excessive polling, large assets and unnecessary startup code.
- Use bounded/paginated tables; add list virtualization, lazy loading or memoization only when the measurement demonstrates a need.
- Cancel obsolete work, pause irrelevant polling and avoid races when typing filters or switching context.
- Keep charts and financial totals tied to server truth; rendering optimizations must not introduce stale or invented results.
- Improve loading transitions, focus handling, confirmation feedback and error recovery without animations that hide slow or failed work.
- Check keyboard/mobile use, layout movement, readable tables and browser memory growth across repeated screen changes.

Review gate:

1. Save comparable browser performance recordings before/after the relevant fixes.
2. Rehearse the complete real website flow while processing the demo and maximum supported datasets.
3. Check fast filtering/context changes, repeated navigation, multiple tabs and interrupted requests for stale screens or duplicate work.
4. Verify scrolling and interactions remain usable on the chosen hardware; set explicit budgets after the baseline instead of promising universal zero lag.
5. Rerun affected frontend security, state-isolation and contract checks after performance changes.

### Phase 13 — WhatsApp connection and channel review (not started)

Owner: both. Outcome: Make the planned phone interface operate on the same authorized local backend data.

Deliverables:

- Real WhatsApp needs Meta's external API and an internet-reachable HTTPS callback. A loopback-only address cannot receive phone events.
- Record the account/recipient/version constraints and agree on a permitted callback method under the PC-only requirement before setting up one. Do not provision a tunnel or cloud server automatically.
- Implement GET callback verification and bounded raw-byte signature checking before processing POST events.
- Validate configured account/phone identifiers, deduplicate repeated events and distinguish inbound commands from delivery statuses.
- Implement expiring linking codes, context selection, unlink/revocation and the same live ownership checks used by the website.
- Reuse the website's import/run/status/report and business-action services rather than building a second calculation or storage path. Add consented supplier follow-up sending with recorded drafts, recipient checks, delivery/uncertain status and shared audit history; do not treat a provider acknowledgement as invoice correction.
- Connect the existing planned owner/reviewer due-review alerts and supplier follow-up drafts to a bounded outbox only when explicitly enabled for a linked/consented verified recipient and permitted message window/template. Persist queued/attempted/acknowledged/delivered/failed/uncertain states; channel outage keeps local tasks available. Scheduled outreach remains conditional on actual entitlement and budget proof.
- Bound media retrieval and outbound calls, enforce the reviewed send budget and handle uncertain transmission without blind resend.
- Keep the local website working if the channel is unavailable; display the limitation truthfully. An emulator is development evidence, not completed physical-phone integration.

Review gate:

1. Use a real phone to link, query status, upload supported sources, run, request a report and unlink.
2. Compare phone and website run IDs, context and results after actions on either side.
3. Prove wrong signatures/account IDs, repeated callbacks, expired link codes and revoked report access have no unauthorized effects.
4. Test invalid media, timeouts, provider failures, due-alert/supplier-draft recipient isolation and restart/dedup behavior without duplicate mutations or automatic spending. Prove physical-phone alert delivery for any enabled automation; an outbox row is not delivery proof.
5. If callback/account setup remains unavailable, keep this phase pending with the concrete blocker; do not mark it complete based on a mock phone flow.

### Phase 14 — Whole-application regression and hackathon rehearsal (not started)

Owner: both. Outcome: Verify the finished website, backend and planned phone channel together with honest completion evidence.

Deliverables:

- Reinstall/build from the committed frontend/backend locks on the demo PC and document the local launch/stop procedure.
- Rehearse from fresh private access and an empty synthetic workspace through upload, confirmation, run, review, business actions, cases and report. Demonstrate all six original problem scenarios from Phase 6 through the connected website; a matching table alone is insufficient.
- Repeat with retained data after an actual backend restart, checking that files, totals and scope remain correct.
- Check combined browser/backend behavior under maximum supported inputs, duplicate actions and delayed/failed replies.
- Rerun focused security regressions on the final build, including private access, unsafe source text, denied downloads and callback checks.
- Record the real frontend/backend versions, launch configuration, sample datasets and measured demo timings without including secrets.
- Prepare a safe synthetic-data reset and an openly labeled outage recording/report if needed; preserve real user files.
- Maintain a completion ledger: working, failed, pending input or unsupported. Create a later logical-correctness record from actual findings/regressions, following the user's earlier instruction.

Review gate:

1. An unaided presenter can launch and complete the demonstrated flow without editing stored data or swapping mock replies into live screens.
2. Website/backend counts, monetary values, action/reminder history, report contents and enabled phone replies agree. Show the six problem outcomes, including unresolved evidence and review limitations, rather than claiming automatic tax recovery.
3. Relevant restart, expiry, error-recovery, security and performance scenarios pass on the final build.
4. Any missing physical-phone capability remains explicitly pending; fallback materials do not replace acceptance evidence.
5. Only mark the requested overall scope complete when required phases and their gates are actually complete.

## Frontend handoff and measurable performance

Phases 8–10 and 12 apply to the authorized internal website. Inspect its actual manifest/build. The separately supplied landing page is later design work and does not block core screens or backend connection. Frontend completion means both a coherent interface and the verified real backend journey; screen appearance alone is insufficient.

Phase 11 measures the backend's contribution to delays; Phase 12 measures browser rendering/interactions and repeated requests. Use the same dataset/context and demo hardware when comparing changes. Define a concrete budget after the baseline and record actual results; a promise of zero lag on every PC is not an acceptance criterion.

Useful primary references for the applicable implementation reviews: [OWASP safe browser rendering](https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html), [OWASP request-forgery prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), and [Chrome runtime performance tooling](https://developer.chrome.com/docs/devtools/performance). Apply guidance to the actual framework/session mechanism rather than guessing one now.

## Phase completion ledger

| Phase | Evidence required before completion |
|---|---|
| 1 | Already recorded: 78 local tests, frozen installation, lint/format and syntax |
| 2–5 | Working backend features with persisted truth and independent correctness fixtures |
| 6 | All six problem scenarios reach a recorded next action and evidence-backed review outcome |
| 7 | Backend security/failure findings fixed and relevant regressions passing |
| 8 | Internal application built, required screens/actions mapped and interface reviewed |
| 9 | Real local website/backend journey and aligned data/status/errors |
| 10 | Browser data-exposure and request-security checks on the actual connected website |
| 11 | Measured backend improvements with correctness/security regression proof |
| 12 | Measured browser smoothness with preserved state/data correctness |
| 13 | Actual physical-phone proof, or explicitly pending callback/account dependency |
| 14 | Final combined rehearsal, installation/restart/recovery and honest scope record |

An unstarted phase has no new passed checks merely because its plan exists. Update status and evidence in the canonical plan as each implementation increment is completed; retain the Phase 1 history.

## Per-phase review discipline

Give configuration, correctness, security, edge cases and integration checks equal attention within each relevant phase. Read the changed code after tests, follow every real error path and fix failures at their cause. Tests cover behavior and risks, rather than simply mirroring helper functions.

Apply the user-requested [Ponytail rules](https://github.com/DietrichGebert/ponytail/blob/main/skills/ponytail/SKILL.md): understand the flow first, use simple native tools where appropriate, avoid speculative abstractions/dependencies, and preserve validation/security/error handling. This user's explicit phased review requirement remains authoritative.

Record actual commands/results after review. A green foundation is evidence for Phase 1 only; it does not certify future parsers, GST logic, authentication or phone integration as secure or correct.

## Phase 2 concrete implementation and gate

The local access choice is operator provisioned accounts, scrypt passwords, opaque cookie sessions, Origin/CSRF checks and scoped reads. SQLite is authoritative; browser localStorage is reserved for harmless UI preferences. No upload/reconciliation/report/phone feature has been added by this phase.

Implemented schema v1: metadata, users, workspaces, memberships, registrations, sessions and rate_windows. Future tables are added only with their phase and a backed-up schema upgrade procedure. Financial storage will use integer paise; Phase 2 has no monetary rows or tax calculations.

| Proof | Required observation |
|---|---|
| Phase 1 compatibility | Config/HTTP redaction, health and origin/Host regressions continue to pass |
| Browser access | Login -> session -> workspace -> registration -> logout works with envelopes and credentials |
| Identity isolation | Two local users cannot retrieve the other's registrations by changing UUID |
| Revocation | Expiry, logout, new login, inactive membership and password reset deny old authority |
| Role boundary | A VIEWER cannot pass an OWNER-only membership gate |
| Retention | Actual restarted process retains committed records and unexpired session |
| Backup/restore | Offline commands validate backup; restored sessions fail and accounts require recovery |
| Corruption/schema | Existing empty, corrupt, foreign, future-version or modified-schema DB is refused unchanged |
| SQL atomicity | Duplicate and foreign-key failures roll back the whole operation |
| Resource bounds | Body, account/session/list, disk/database and backup limits fail safely |
| Process ownership | Second runtime or maintenance command cannot acquire the active data lock |
| No leakage | Errors never contain password, session token, private filename or raw SQL |

Phase 2 completed locally on 2026-10-03: 118 tests passed, one Windows symlink-privilege test skipped; the actual Windows junction test and process restart/offline backup/restore proof passed. Frozen dependency installation, lint/format, syntax and diff checks passed. The Windows backup flush defect found during review was fixed, as were same-host browser-cookie alignment and bounded validation/prompt failure paths. Local verification and remote CI remain separate evidence. Phase 3 was explicitly authorized in the following increment; its verification record is maintained below.

## Future regression set to carry through the phases

Keep independently prepared expected counts/totals and deliberate bad cases. Import gates cover corrupt XLSX/JSON, nested/expanded bounds, malformed decimals, missing tax components, ambiguous headers and partial confirmation. Reconciliation gates cover duplicate identities, cross-year invoice numbers, paise tolerance, ties, competing candidates, unique assignment and shuffle invariance.

Review/case/report gates cover stale versions, transaction rollback, superseded snapshots, rejected candidates, missing evidence, report source manifests, safe formulas/markup and truthful proposal labels. No report claims official filing verification or payment execution.

Frontend connection gates cover same-host cookies, session reload, selected-context changes, denied IDs, cancellation, network failure, controlled Retry-After, double-click creates, private cache clearing and real committed responses replacing mocks.

Phone gates cover raw signatures, configured assets, link expiry/single consumption, event replay, media bounds, unlink revocation, ambiguous send UNKNOWN and exact agreement with website summaries. Real phone proof remains required; an adapter emulator is development evidence only.

Every later phase repeats affected earlier checks after edits. Test the enforcing layer with allowed adjacent cases, rather than asserting that a named helper exists. Performance work records measured time/memory and does not weaken exact matching, privacy or validation to achieve a faster number.


## Phase 3 implementation and verification record

Phase 3 uses direct edits to responsibility-named source modules. No phase-named code-edit helper scripts are part of the repository or the workflow. The new modules separate HTTP contracts/routes, exact canonical validation, bounded source adapters, application commands, import schema and the local dispatcher/disposable worker. Existing lifespan/configuration/HTTP boundaries and offline administration were connected rather than replaced.

Verified intermediate evidence: 34 initial parser tests passed; endpoint flows passed for upload/preview, partial acknowledgement, mapping, supersession, scope/role protection and idempotency. The first integration run caught a test-only unclosed SQLite connection; it was corrected with explicit closing. Additional cases cover blank records, reported tax totals and unsafe XML entities.

Resource verification found a Windows virtual-environment launcher spawning a second interpreter. The dispatcher now tracks combined process-tree RSS and stops all observed parser processes on timeout/memory failure. Real child-kill tests assert the observed PIDs no longer exist, not merely that an HTTP timeout was returned. Actual streamed upload counting, duplicate/invalid length headers, receive timeout, authorization-before-body-read, queue bounds and interrupted-job recovery are checked. Source/preview persistence is tested against actual backend process restart and offline backup/restore.

Measured local Windows baseline (Python 3.13.16, complete upload-to-persisted-preview time, includes process startup; not a universal performance guarantee):

| Adapter | Rows | Source bytes | Time (seconds) | Sampled combined child RSS (bytes) |
|---|---:|---:|---:|---:|
| CSV | 100 | 10,935 | 0.602 | 40,366,080 |
| XLSX | 100 | 10,084 | 0.619 | 40,980,480 |
| CSV | 2,000 | 221,935 | 0.877 | 48,648,192 |
| XLSX | 2,000 | 101,303 | 2.697 | 51,294,208 |

Inputs contain distinct synthetic vouchers/invoices and exact component amounts. Health requests are made during the parse and remain available. RSS samples cover the Windows launcher and actual parser; a sampled peak can miss between-sample spikes. Phase 11 will measure broader contention and whole-backend behavior. The full Phase 1–3 regression, frozen dependency, lint/format, syntax and Git checks are recorded after their final run.

Final boundary review also rejects all duplicate purchase copies when one copy has an unrelated validation error. Parser task descriptors use generated private bounded files rather than a blocking stdin pipe, so interpreter startup remains inside the monitored timeout. Both descriptor and result files are cleaned up. Queued-job restart, simultaneous identical command reservations and shipped example parsing are covered by the final tests.


Phase 3 completed locally on 2026-10-03. The full Phase 1–3 regression passed: 169 passed, one Windows symlink-privilege test skipped; the actual Windows junction test passed. A final reviewed retry identity fix was followed by all 77 affected import/parser/HTTP tests passing. Explicit unchanged-mapping recovery from an interrupted import now creates a derived job instead of returning the original failed import; source/context deduplication remains intact. Frozen dependency sync, Ruff lint/format, Python syntax compilation and final diff checks passed. The real-process proof connects Phase 1 health, Phase 2 sessions/scopes and Phase 3 upload/preview/confirmation across restart and offline source-inclusive backup/restore. Local verification does not claim GitHub CI has already run. Phase 4 remains unstarted.

## Phase 4 implementation decisions (2026-10-03)

Use the existing single killable child dispatcher for imports and runs, with shared workspace queue admission. Add SQLite schema v3 with an explicit validated, backed-up offline v1/v2 upgrade. Preserve confirmed source IDs, hashes, adapters, provenance and server policy settings in every run. Financial arithmetic stays in integer paise. RapidFuzz ratio on an explicitly normalized comparison key produces suggestions requiring review; exact keys preserve separators, zeroes and year tokens. Compare all eligible candidate edges before classification, quarantine duplicates, bound total comparisons/candidates and fail explicitly rather than truncate ambiguous results. Review transactions recheck role, source freshness, expected version and unique assignment; commit result, summary, idempotency response and audit together. A replacement supersedes older completed runs only after its results commit. Interrupted running jobs fail visibly; queued jobs resume. At Phase 4 completion, Phase 5 had not started; its completed implementation is recorded below.

## Phase 4 initial measured baseline

Actual disposable reconciliation workers on this Windows PC, including run admission, child startup and database publication, with valid confirmed CSV source pairs:

| Accepted purchase rows | Exact results | Run seconds | Sampled combined child-tree RSS bytes |
|---|---|---|---|
| 100 | 100 | 0.635 | 32,739,328 |
| 2,000 | 2,000 | 1.584 | 50,720,768 |

These are initial local observations for exact-match workloads, not universal latency guarantees or worst-case fuzzy workloads. Twenty-millisecond RSS sampling can miss short spikes. Ambiguous candidate workloads are bounded separately; exceeding pair/candidate limits fails instead of silently truncating the graph. Full Phase 1–4 regression is the final completion gate.

## Phase 4 completion and verification record

Local Windows verification on 2026-10-03: the complete Phases 1–4 regression suite passed **198 tests, with one Windows symlink-privilege skip**, in 423.21 seconds. The separate actual Windows junction-denial test passed. Final review then fixed equal top similarity scores when an operator configures the minimum score gap to zero; ties remain ambiguous. All **21 affected reconciliation/golden-run/concurrent-review tests** passed after that final change, including two new zero/default-gap regressions. The repository now contains 19 reconciliation unit cases and 12 run integration cases. This is not a claim that a new complete 200-test suite was rerun after the bounded final fix.

Frozen installation checked the selected runtime; Ruff lint/format, syntax compilation and diff checks passed. Golden expected counts and amounts were prepared independently. Tests cover paise tolerance, component cancellation, unknown values, credit-note separation, rejected duplicate evidence, same-number other-year gates, score threshold/gap rounding, input permutations, exact reservation, candidate/pair exhaustion, actual child processing, shared queue/retention quotas, two-user scope isolation, VIEWER denial, CSRF, malformed reviews, stale versions and request keys.

Concurrent tests prove one winner per contested portal row and per result version; rejected assignments release correctly. Late audit failure rolls result/summary/history/idempotency back together. SQLite tests reject invalid assignments, cross-source candidates, completed runs without summaries and running jobs without leases. Queued work resumes; interruptions fail truthfully; stale lease output is ignored; failed replacements retain earlier output. Source supersession blocks reviews and historical results remain readable.

An actual local HTTP process run was reviewed, stopped, restarted, backed up and restored: result status/assignment/timeline, saved source/policy and job success remained consistent. Restored sessions/accounts stayed revoked until explicit operator recovery. Tests used isolated synthetic storage; no real backend/.env or backend/data was created. GitHub workflow results are separate evidence.

Phase 4 was developed directly in responsibility-named modules: api/runs.py, contracts/runs.py, domain/reconciliation.py, services/runs.py, jobs/run_worker.py and storage/run_schema.py. Existing main/dispatcher/import-job/admission/storage hooks were extended and inspected against their previous versions. No phase/helper editing scripts are retained. All eight active MDs and the environment example now describe the implemented run/review contracts and local schema/queue decisions. At that Phase 4 milestone, Phase 5 had not started; see its completion record below.


### Phase 5 implementation status

Completed: additive schema 4, bounded evidence cases, human-approved payment proposals, private PDF/CSV artifacts, expiry cleanup and integration checks. Reports use immutable committed snapshots; proposals never execute payments. Previous schema definitions remain unchanged for validated offline upgrades.


## Phase 5 completion and verification — 2026-10-03

Implemented directly in responsibility-named files: contracts/workflows.py, domain/workflows.py,
services/workflows.py, services/cases.py, services/proposals.py, services/reports.py,
adapters/reports.py, jobs/report_worker.py, api/workflows.py and storage/workflow_schema.py.
The existing main/dispatcher/import-job/queue-admission/storage code connects these services
with Phases 1–4. No phase-named runtime module or retained patch/helper script was introduced.

Decisions: private report BLOBs and source snapshots in SQLite rather than separate cloud/files;
one existing monitored processing child; additive schema 4 with preserved v1/v2/v3 fingerprints;
server-generated filenames; approved/current proposal CSV only; explicit historical PDF/error
CSV downloads; seven-day artifact expiry and owner-only content cleanup. Financial comparisons
remain integer paise. Cases/proposals preserve uncertainty and require human observation/review.
No bank transfer, statutory computation, government filing, IRN authenticity adapter, frontend
or WhatsApp connection is implemented by this phase.

Complete local Windows Phases 1–5 regression: **234 passed, 1 skipped**, in **508.73 seconds**.
The skip requires Windows symlink privilege; the actual junction-denial check passed. Checks
cover all five case kinds, current-version transitions/reopen, same-scope observations/hash
snapshots, invalid money, missing facts, evidence edits requiring renewed observations,
proposal overdraw/rejection/staleness, generic review-only export, and unchanged amount_paid.

Report checks cover private login/role/scope boundaries, CSRF through the shared middleware,
shared queue limits, active request deduplication/idempotency conflicts, failed/interrupted
jobs, invalid/obsolete leases, invalid base64/hash, unavailable/stale/expired downloads,
explicit historical PDF behavior, stale proposal CSV denial, formula/markup neutralization,
unsupported glyph failure and bounded pages/bytes. An audit fault rolls back the case command.
A real HTTP process restart preserves cases, proposal snapshots and byte-identical reports;
SQLite backup/restore retains them while revoking restored sessions/accounts until offline
password reset. Explicit old schema 2/3 upgrades retain validated original backups; existing
schema 1 checks also passed in the full suite.

Final presentation changes group normal invoice entries, keep headings with following text
and display UTC timestamps readably. All **24 affected report-rule/end-to-end checks passed**
after those changes; the full suite is the earlier 234-test run, not an unclaimed second full
run. The 200-row PDF baseline is **41 pages / 68,286 bytes**, clearly showing 200 of a 2,000-row
run. All page text bounds were inspected programmatically; rendered first/middle/final sample
pages and all actual HTTP-generated evidence PDF pages were visually reviewed for clipping,
rupee rendering, footers, readable facts and page continuation. Temporary synthetic QA files
are outside the repository and are not private user documents.

Frozen uv sync (37 resolved packages), Ruff lint/format, Python compilation and Git whitespace
checks passed. GitHub CI timeout increases from 10 to 15 minutes because the local full suite
already takes 8.5 minutes; remote Windows/Linux CI results are separate from local evidence.
All eight active MDs, both READMEs and .env.example now describe the actual schema/stack/wire
fields and caps. Original foundation documents remain historical context.

Accepted hackathon limits: localhost/single-PC availability; finite histories including expired
artifact history; cleanup is logical deletion and old backups retain bytes; PDF glyph coverage
is limited to the bundled font and unsupported scripts/emoji fail visibly; PDFs may show a
bounded selection with full totals and fail rather than truncate when a snapshot/page cap is
exceeded. One reviewer can approve a non-executing draft; production maker/checker, bank/provider
integrations and legal decision engines are outside this phase. At the Phase 5 milestone, the added Phase 6 had not started; its current implementation record follows below. Phase 7 remains the subsequent focused backend review. Passing tests does not establish zero defects or production security certification.


## Phase 6 implementation and verification record

Responsibility modules: `storage/action_schema.py`, `contracts/actions.py`, `domain/actions.py`, `services/actions.py`, `jobs/automation.py` and `api/actions.py`. Existing main/config/storage/report modules connect the new service to the Phase 1–5 authority; no phase-numbered scripts or patch helper files were added. Schema 5 is additive, with exact old fingerprints and offline backup-first upgrade. No dependency or provider infrastructure was introduced.

The six API scenarios cover missing INR 20,000 GST across later snapshots, unknown/partial payment review, supported reversal/reclaim observations, unverified IRN, notice preparation/submission observations and retained supplier follow-up history. Additional tests cover background processing without queue reads, event deduplication, actual HTTP restart and offline backup/restore, two accounts, forged draft IDs, role/revocation, stale sources, idempotency, competing versions, full history/action quotas and independent progress after a failed source. Pure rule/input checks cover absent/contradictory amounts/periods, credit notes, unclaimed credit, exact paise, future dates, invalid contacts/commands and duplicate references.

Frozen sync, Ruff lint/format and syntax compilation passed. Forty-five new Phase 6 scenario/rule checks plus five targeted storage regressions are included, with exact full-run versus final-focused evidence distinguished below. Repeated full checks exposed transient import/report polling failures; these failed runs are not completion evidence. Initial handling of disappearing scanned entries was insufficient: a three-thread reproduction found Windows final-path resolution could falsely label an ordinary short-lived journal file as linked. Existing lstat/type/reparse checks already reject file links, so final-path resolution is now restricted to directories, preserving intermediate-directory/traversal validation. Scans also tolerate vanished entries without recreating the primary database. The original stress reproduction failed twice before this correction; afterward 200 committed writes and 800 concurrent quota scans completed without errors, followed by SQLite integrity/fingerprint validation. All storage checks passed: 23 passed, 1 Windows-privilege skip, including file disappearance, ordinary-file resolution, missing-database refusal, traversal and actual junction denial. Private diagnostics retain only internal category, failure type and numeric code. The complete local Windows suite passed **281 tests, with 1 Windows symlink-privilege skip**, in **951.44 seconds (15 minutes 51 seconds)**. A final bounded date-validation refinement then rejected future filing observations and future claim/reversal periods from current reclaim review. All **32 affected rule/reclaim/incomplete-evidence checks passed** afterward (13 unrelated integration checks were deselected). The three added date cases were verified in that focused run; this is not a claim that an expanded full 284-test suite was rerun. Frozen sync checked 37 packages; Ruff lint/format and Python syntax compilation passed after the final edit. Actual junction denial remains covered by the passing full run.

The updated notice/action PDF was rendered and inspected; the compact history retains user/system dates and unverified execution labels while full snapshots remain private. Old source/action versions and added actions invalidate historical reports. Worksheet/PDF generation does not close an action or perform a submission. No official GSTR-2B JSON fixture was supplied: supported CSV/XLSX tables and synthetic canonical JSON remain the explicit adapter inventory; a real unsupported layout is still pending an authorized sample.

Future ownership remains Phase 7 whole-backend security/failure review, 8 supplied website screens, 9 connection, 10 frontend privacy/security, 11 backend measurement, 12 frontend usability, 13 conditional real WhatsApp and 14 combined rehearsal. Automatic authorized fetching, government filing and legal decision integrations are deferred separately; guaranteed recovery is not an implementation promise. Phase 6 is complete for the local backend business workflow scope. Website and phone delivery remain separate later gates.


### Phase 6 final source size and CI allowance

Measured physical Python source lines at completion: **8,287 application lines** in 50 files, **5,169 test lines** in 17 files, **13,456 total**. This includes comments and blank lines, excludes docs/configuration/dependencies/generated files and does not count a frontend that has not yet been supplied. The GitHub job allowance increases from 15 to 25 minutes because the passing local full suite alone took nearly 16 minutes; dependency setup and remote hardware variability need headroom. This changes the timeout, not test coverage. Remote CI results are separate from the local proof above.


### User-authorized Phases 7–9 batch (2026-10-03)

Finish and verify Phase 7 and push it before Phase 8. Build the core internal website in Phase 8; the user supplies the landing page/design later. Complete the Phase 8 build, screen/accessibility and contract gate, push it, then complete and verify the real Phase 9 backend connection. After Phase 9, run the full backend regression plus the frontend build/browser suite. Retain targeted checks after each phase. This replaces the earlier supplied-website prerequisite only for the core internal application; real WhatsApp and external fetching/filing remain later work.


## Phase 7 completion and verification — 2026-10-03

Reviewed the implemented request/authentication/service/storage/job/export boundary across Phases 1–6. The independent workspace access inventory covers **33 operations (18 reads, 15 writes)**; adding a route without an explicit scenario fails the inventory assertion. Tests verify signed-out denial, another workspace, live VIEWER mutation denial, allowed adjacent reads, membership revocation and inactive-account denial without publishing business mutations. Existing source/evidence/report/action checks provide actual-resource isolation, stale-write and atomic rollback proof.

Fixed reproduced ordinary-request defects in shared HTTP middleware: declared/received byte mismatch, unbounded body waiting, ambiguous repeated JSON keys (including nested/escaped equivalents), non-standard constants, malformed encoding and duplicated Content-Type. All small mutation bodies have the existing byte cap and a new **MAX_API_RECEIVE_SECONDS=20** total receive deadline (strict integer 1–60). Multipart retains its separate authorization-first receiver and deadline. Invalid bodies never reach the downstream handler. Safe 400/408/413/422 replies preserve request IDs, no-store and permitted-origin headers; receive exceptions log only request ID/type. Response transmission occurs outside the receive timer, avoiding a second response on a slow error send.

Fixed shutdown ownership in main: the OS data lock is released only after **both** dispatcher and action-monitor threads have stopped. A timed-out worker previously could leave its thread alive while storage ownership was released. Four lifecycle checks prove parser/monitor/both-timeout lock retention and normal release. A real HTTP process test proves an incomplete JSON upload receives 408 while concurrent liveness/readiness stays usable. Reused shared duplicate-object validation in multipart mappings; no phase-named runtime modules, temporary patch helpers, new runtime dependencies or schema migration were added.

**Targeted Phases 1–7 gate: 230 passed, 1 skipped in 367.94 seconds (6 minutes 7 seconds).** The skip requires Windows symlink privilege; actual junction denial passes. The selection covers configuration/environment drift, HTTP/session/CSRF/rate/revocation, malformed structured parsers, storage quota/page limits and missing/linked data, child kill/deadline/RSS and interruption, upload/mapping/retry scope, contested result review, audit rollback, report leases/expiry/escaping/privacy, private action commands/quotas/failure fairness and actual action restart/backup/restore. Unrelated benchmarks and unchanged business golden cases are reserved for the full post-Phase-9 regression. Frozen uv sync checked 37 packages; Ruff lint/format, Python compileall and Git whitespace checks passed. This is a targeted passing gate, not a claimed full-suite run.

On 2026-10-03, the [OSV batch API](https://google.github.io/osv.dev/api/) returned **no known advisories** for all **38 registry package/version entries** in backend/uv.lock (including platform-specific/development entries). Only public package metadata was sent. No dependency changed without cause. This database check is time-bound and does not audit the operating system, native interpreter/SQLite implementation or unpublished vulnerabilities.

Accepted limits: local/single-PC execution and OS-account trust; unencrypted private database/backups; finite histories, fixed-window budgets and one shared heavy worker; sampled child RSS rather than a kernel sandbox; PC-off reminders cannot run; body deadlines do not make the local HTTP listener a public Internet abuse defense; user observations do not certify external filing/IRN/legal facts. Browser security, measured backend performance, conditional physical WhatsApp and whole-product rehearsal retain Phases 10/11/13/14. No production security certification or zero-defect guarantee is made.

## Phase 8 completion — 2026-10-04

Created the authorized internal React website, with six navigation sections: sources; reconciliation; cases/evidence; persistent work queue and supplier follow-up history; evidence-backed payment drafts; private reports. No product mock fallback and no landing-page dependency. Login, workspace/registration/month selection, visible roles, bounded pagers, mapping into derived previews, confirmation, job states, exact financial strings, stale-history labels, explicit evidence support, review reasons and report expiry are represented. Shared API DTOs are generated from the actual backend OpenAPI. Credentials remain in HttpOnly cookies; CSRF is memory-only. Reads cancel/ignore obsolete scope replies and polling pauses in hidden tabs and stops on terminal jobs. Sign-out clears private screens immediately, including on backend unavailability, without pretending the server cookie was revoked.

Client tests cover local-origin configuration, CSRF/cookie headers, stable retries after lost replies/500, explicit-conflict receipt renewal, double-submit deduplication, obsolete responses, invalid envelopes/401 and bounded report MIME/stream downloads. Six passed. Two Playwright screen tests passed using installed Chrome; all six sections, empty/error/viewer states, back navigation, keyboard focus, malformed hash recovery and 390px/1440px layouts were inspected. Screenshot review found no clipped navigation or page overflow. These two tests use explicit synthetic API fixtures and do not count as real backend journeys. Strict TypeScript compilation and Vite build passed; generated contracts are independently checked. Npm audit reported zero known advisories for the selected frontend lockfile before adding the formatter; rerun with final lock at the final gate.

Verified minimal stack: React/DOM 19.3.0, Vite 8.3.2, React plugin 6.1.1, TypeScript 7.0.2, React types 19.3.0, Playwright 1.63.0, Prettier 3.9.9; exact versions and pnpm 11.19.0 lockfile. Node 24.19.0 used. All tooling is local; no cloud service or external database was introduced. The browser binary download timed out, so the verified installed Chrome channel is used. Final visual design remains deferred.

Phase 9 connection gaps identified explicitly: add authorized saved-artifact listing so reports survive navigation/reload; apply registration/month filters in backend SQL before list pagination, including case/proposal joins to their originating runs; complete real six-scenario browser journeys and failure/restart checks. The existing report-by-ID/download paths remain visible and truthful while the listing is absent. Backend cases/proposals page size remains 20; the website follows it. No mocked screen success is recorded as connected functionality. Full backend regression remains scheduled after Phase 9 under the user's batch authorization.

## Phase 9 connection verification — 2026-10-04

All browser operations use the real local API. The six real Playwright journey tests passed in 1.7 minutes using an isolated temporary SQLite/backend and installed Chrome. The tests exercise the six original business problem categories across several persisted months: missing ₹20,000 supplier invoice → private draft → explicitly unverified contact attempt → newer confirmed 2B → reuse the original purchase import and action/history; MSME acceptance and payment observations → reviewed balance → proposal approval → private CSV; recorded prior credit claim/reversal and later supplier filing evidence → reclaim candidate → human review → explicitly unverified external observation; IRN format-only review; notice document support and evidence PDF; and ongoing queue/history/reminder/report access. Generated reports download through authenticated bounded endpoints and remain discoverable after browser refresh.

Additional browser checks use actual role-scoped workspaces, month selection, delayed replies from the prior selection, sign-out when the backend is unavailable, a forced real backend process restart with the same private temporary storage, server session revocation, a contested result version (409), explicit reload/retry, updated recorded-tax summary and a reconciliation PDF. No API reply is replaced with a sample in the six real journeys. One delayed-response test holds and then forwards the actual server reply; one sign-out fault aborts the request deliberately. The two separate screen tests still use explicitly declared empty fixtures and are not business-integration proof.

Connection fixes: backend list queries accept optional registration_id/period and apply them before UUID pagination. Cases derive accounting period through their originating result/run; proposals through their run; actions retain their own registration/month. The new GET artifacts list joins the actual originating import/run/case/proposal and returns only metadata, with live workspace authorization and page size <=20. It selects IDs then processes one snapshot at a time, without fetching report BLOBs. All other endpoint semantics and schema version 5 remain unchanged. The independent endpoint access inventory now covers 34 workspace operations (19 reads, 15 writes). Twelve targeted backend tests passed, including all four report source kinds, two registrations/two months, page size 1, opaque missing scope, invalid filters and the complete access matrix.

Browser correctness fixes: source upload details no longer collapse when a delayed source list arrives; choosing a derived mapped preview selects its actual new ID; reviewer refresh also updates comparison summaries; stale reviews have an explicit reload path; evidence checkboxes show the recorded observation kind, avoiding blind UUID selection. Upload mapping fields are generated directly from the backend canonical field set, eliminating unsupported mapping options. A user-scoped sessionStorage preference stores only selected workspace/registration IDs and month for refresh; it holds no invoice, credentials or CSRF and is cleared on sign-out/expiry. Reads use scope-keyed state and abort old requests. Mutations use live expected versions and stable UUID receipts for interrupted unchanged explicit retries; double clicks share one in-flight request. Report downloads remain inside the body deadline/session cancellation boundary and validate MIME plus the 5 MiB byte cap. Visible work queues refresh every 10 seconds; pending job polling stops on terminal states and pauses while hidden. Preview's CSP includes the validated configured local API port.

Added pinned website CI checks for frozen install, generated contract drift, formatting, unit tests, strict build and real isolated browser journeys. Linux CI is a temporary test runner, not Ubuntu hosting or a change to the Windows local deployment. Backend retains its existing Windows/Linux regression job. The combined eight-browser-test suite passed in 1.7 minutes. A separate built-preview smoke test passed in 18.5 seconds, proving actual sign-in/upload/parse/confirm/sign-out under CSP with the configured API port. Client unit tests passed (6), frozen install, 76-schema/canonical-field drift checks, strict build and formatting passed, and npm audit returned zero known advisories for the locked 72 entries. Full backend regression passed: 314 passed, 1 skipped in 699.66 seconds (11 minutes 39 seconds). The skip needs Windows symlink privilege; the junction check passes. Frozen uv sync checked 37 packages, Ruff lint/format checked 71 files, Python compileall and Git whitespace checks passed. Phase 9 is complete for this scope. Landing-page design, broader frontend security/performance, measured backend performance, real WhatsApp and the final rehearsal remain Phases 10–14 as previously planned. No government fetch/submission, bank transfer, guaranteed recovery or legal/IRN certification was introduced.

## Post-Phase-9 final verification and source size — 2026-10-04

Full backend: **314 passed, 1 skipped, 699.66 seconds**. Combined browser: **8 passed, 1.7 minutes** (six real journeys plus two explicit screen fixtures). Built CSP preview: **1 passed, 18.5 seconds**. API-client tests: **6 passed**. Frozen dependency install/sync, generated 76-schema and canonical mapping-field alignment, strict TypeScript/Vite build, Ruff/Python compilation, frontend formatting and Git whitespace checks passed. Frontend audit: zero known advisories, 72 locked dependency entries. Build JS was approximately 282.65 kB / 83.56 kB gzip; this is a build size, not a latency benchmark or performance certification.

Application physical source lines: backend/app Python plus frontend/src TS/TSX/CSS, including blanks/comments and the generated DTO file. Tests include backend/tests, frontend/tests and the isolated test-server harness; the generator is development tooling. Documentation, lockfiles, vendor code, virtual environments, binaries/build outputs and repository configuration are excluded from these source counts. Exact final counts are recorded below. More lines are not a quality metric; the browser/backend contracts and passing journeys are the evidence.

Phases 7, 8 and 9 are complete. Phases 10 frontend security/privacy, 11 backend measurement, 12 frontend efficiency, 13 conditional physical WhatsApp and 14 whole-product rehearsal remain pending. User landing page/design is still separate later work. These passing gates do not promise zero defects, production certification or guaranteed tax recovery.

Final physical source counts: **12,743 application lines excluding tests; 6,947 test/support lines; 19,690 including tests.** Generated DTOs are 80 of the application lines. Generator/build configuration remains outside those counts.


## Phase 10 completion and verification — 2026-10-04

Frontend privacy review is complete for the implemented local website. Direct changes went into the existing client, shared resource hook, workspace shell, queue and reports screen. There is no backend schema change, added dependency, provider connection or new tax capability.

Three new client regressions first failed against the previous implementation: percent-encoded request paths reached fetch; a delayed 401 error body could expire a replacement session; a cancelled report scope could reach file exposure. Request paths now accept only the fixed API pathname alphabet and reject traversal, encoded segments, fragments, backslashes and controls. Every response-body branch rechecks session generation and read cancellation. Report downloads additionally recheck immediately before creating a blob URL and use a component-lifetime abort signal, so leaving a section, changing registration/month/workspace/role or signing out cancels the pending download. Report lookup accepts UUID-shaped IDs; backend UUID/ownership validation remains the authority.

The resource hook clears cached data on 401/403/404. A denied queue response also unmounts its open action detail; ordinary refresh/temporary failure preserves the detail's existing workflow state. Permitted workspaces refresh every 15 seconds while visible, with roles included in the screen identity so role changes discard old forms. These polls do not replace authorization: the backend already checks active account, session, membership and role for every operation. Changes made elsewhere become visible on the next successful poll or interaction, not through instantaneous push notifications.

Only VITE_API_BASE_URL is exposed as public configuration. Other VITE_ variables are no longer automatically exposed. Synthetic privileged/provider canaries test development transformation and built assets. Dev serving is restricted to the frontend root, keeps Vite's environment/key/Git deny rules and additionally blocks tests, scripts, traces and screenshots. Automatic public-directory copying is disabled; future design assets should be explicitly imported from reviewed source. Preview retains strict script/style/connect policies, disables objects and framing, and uses no-store/nosniff/no-referrer. Development hot reload retains its working configuration and framing header; the strict built CSP is a preview policy, not a claim that developer tooling is a hardened public host.

Verification on the final code:

- **10 Node client/configuration tests passed**, including the three reproduced failures, public-setting allowlist and HTTP denial of test/server/backend source files.
- **14 browser tests passed in 2.5 minutes**: the six existing real business journeys, two existing screen fixtures, four explicitly mocked privacy/failure cases, and two additional real-backend security journeys. They cover denied queue/detail clearing, role refresh, UUID lookup, download cancellation, HTML-shaped CSV display, storage/cookie inspection, logout/identity isolation and request forgery.
- **2 built-preview tests passed in 25.0 seconds**: real login/upload/parse/confirm/logout under CSP, actual blocked framing/unconfigured connections, shipped-asset canary/test-password scans and absence of source maps.
- **25 targeted backend checks passed in 246.27 seconds**, covering access, endpoint security and website contracts. Backend code was unchanged. The full 314-pass/1-skip suite recorded after Phase 9 was not rerun for these frontend-only changes.
- Generated 76-schema/canonical-field alignment, Prettier formatting, strict TypeScript/Vite build and Git whitespace checks passed. Existing pinned dependencies and lockfiles remain unchanged.

The hostile invoice text is verified in a real parsed CSV preview/raw-field display; no image element, dialog or attacker-resource request appears. Browser storage contains selection IDs/month only, with no invoice, password, session token or CSRF. HttpOnly/Strict/API-path cookie flags are inspected. Missing CSRF is refused with 403; a cross-site browser logout with the Strict cookie withheld is refused with 401; an explicitly foreign Origin is refused with 403 even using the authenticated test request context. The original session remains active after refused logout attempts. Successful logout leaves private API reads at 401, and the next identity receives opaque 404 for the previous user's workspace.

Phase 10 does not certify production security or every possible browser/OS attack. Local HTTP and OS-account trust remain the agreed hackathon boundary; private PC files/backups are not newly encrypted, screenshots/downloads intentionally saved by the user cannot be revoked, and server sign-out failure remains explicitly reported. Phases 11–14 and the supplied landing page/design remain future work. No government fetching/filing, legal approval, payment execution, real WhatsApp delivery or guaranteed recovery was added.


## Phase 11 completion and measured verification — 2026-10-04

Phase 11 is complete and locally verified. The final isolated workload gate and full backend
regression passed: **343 passed, 1 Windows symlink-privilege skip in 733.76 seconds (12:13)**.
Actual junction denial passes. Website alignment, strict TypeScript/Vite build and all 14
existing browser tests passed against the final backend. No Phase 12 work has started.

### Demonstrated causes and direct fixes

1. Dense fuzzy matching repeatedly normalized each portal invoice number for every pair.
   A 100-by-100 profile made 10,100 normalization calls; the optimized version makes 200.
   Accepted portal comparison strings are prepared once inside one reconciliation call.
   Clear similarity negatives bypass expensive Decimal creation, while survivors still pass
   the original Decimal floor threshold and raw-score gap rules. Financial arithmetic remains
   integer paise/Decimal. The pair counter, graph contests, candidate limits and ordering remain.
2. Action source lookup omitted the leading workspace key of the existing import-row index.
   A large tracking batch therefore repeatedly scanned retained invoice rows; [the diagnostic
   action-source profile](../backend/benchmarks/results/action-diagnostic.json) spent about 32.8 seconds across 2,000 calls. Purchase tax, assigned
   portal evidence and candidate joins now use workspace-scoped indexed lookups. This improves
   scope clarity and avoids a new index or schema migration. Run provenance/source manifests
   are computed from transaction-local snapshots, without repeating the whole run-detail query
   for each invoice or caching membership/eligibility across requests.
3. Monitor and HTTP catch-up could observe the same pending source before either acquired the
   writer transaction. Refresh now rechecks the successful source/version checkpoint inside
   that transaction. A competing refresh skips completed work; failures/new versions still retry.
   The whole source derivation, action events and checkpoint remain atomic.
4. The matching child retained its read transaction during CPU comparisons. It now closes the
   database after loading scoped immutable rows/policy and computes from memory. Parent publish
   still checks the lease and current source versions atomically. Local read transactions now
   use actual SQLite read-only connections, avoiding writable connection setup during health
   checks and rejecting accidental writes through read paths. Write durability/quota settings
   and ordinary-file/process-lock protections remain unchanged.
5. Reconciliation PDFs printed the complete nested action history and then printed a second
   compact history. Even a bounded request could exceed the page cap or time out. The nested
   duplicate is removed. New private snapshots retain concise invoice/date/type/supplier,
   comparison reasons and recorded tax alongside the complete stored audit timeline. PDFs print
   meaningful evidence changes, reviewer decisions, follow-up and filing/notice observations
   once. Routine SOURCE_REFRESHED events are summarized by count and earliest/latest date;
   individual events/raw snapshots remain in private history. Long meaningful histories/notes
   still obey the page/byte limits. ReportLab callback annotations are normalized back to the
   exact public REPORT_PAGE_LIMIT code. New requests identify generator gstshield-reports-v2;
   existing stored report bytes and source records are not rewritten.

### Reproducible evidence and limits of the comparison

- [Benchmark instructions](../backend/benchmarks/README.md) and
  [reusable workload](../backend/benchmarks/workload.py) use real loopback HTTP, disposable
  Uvicorn/processing children, temporary synthetic accounts/storage and current private APIs.
  They never read the real `.env` or taxpayer database and never call providers.
- [Before](../backend/benchmarks/results/before.json) records the Phase 10 commit
  `085cd746eda7d7ce19f771f00f404614c5d34e91`. It is explicitly partial: its first normal
  2,000-row result pagination stopped on HTTP 503 STORAGE_UNAVAILABLE. The three completed
  100-row trials and dense-domain measurements are preserved. Complete baseline health/memory
  percentiles and maximum HTTP timings do not exist and are not invented. Its old small-sample
  p95 estimator is flagged; median/max remain usable.
- [After](../backend/benchmarks/results/after.json) is complete and passed all workload gates.
  It records normalized application hash
  `d9487d27f98190f0f1b06ed4088deb134d4018655cedb3615e9d6c3b2cef1076`, base commit and uv-lock
  hash because the measured final edits were not committed yet. Final source must match that
  hash. Same actual Windows 11 PC: AMD64 family 23/model 104, 16 logical CPUs, about 16.5 GB
  physical RAM, Python 3.13.16, SQLite 3.53.1. Other background work can affect wall times.
- Normal sources: 100 rows/13,445 bytes or 2,000 rows/269,045 bytes each, 95% exact and 5%
  separator-only suggestions. Dense sources: 2,000 rows/259,935 bytes each, one identity group,
  four million dissimilar pairs and no eligible candidates. The tool first derives tracking,
  then records one human review, checks exact summary totals and refreshes tracking again.
- Only synthetic-server request budgets are raised for rapid repeated polling: reads 5,000/min,
  mutations 1,000/min and imports 100/min. Application budgets remain unchanged. All other
  storage/worker/history limits remain defaults. Per-operation stages include accepted-to-final
  polling delay and child startup; they are not pure algorithm timings.

| Measured stage | Recorded result |
|---|---|
| Dense domain computation, before | 35.69 / 36.43 seconds |
| Dense domain computation, after | 4.72 / 4.75 seconds |
| 100-row complete HTTP run, before | 0.627–0.681 seconds, three saved trials |
| 100-row complete HTTP run, after | 0.579–0.631 seconds, three trials |
| 2,000-row normal complete HTTP run | 1.53–1.75 seconds, three trials |
| 2,000-row dense complete HTTP run | 5.77 / 6.04 seconds, two trials |
| Upload acceptance | 41–58 ms for these CSVs |
| Parse after acceptance | 1.11–1.16 seconds for 100; 1.43–1.50 seconds for 2,000 |
| Confirmation | 29–42 ms |
| Run-summary HTTP median | About 20–22 ms across each five-query sample |
| Initial tracking catch-up | 71–87 ms for 5 actions; 249–292 ms for 100; 1.57–1.91 seconds for 2,000 |
| PDF creation-to-ready | 2.10–2.18 seconds for 100 details; 3.41–4.02 seconds for 200 details plus 100 actions |
| PDF download | 24–92 ms, verified actual PDF bytes |
| Concurrent readiness | 371 successful probes; median 20.98 ms, nearest-rank p95 58.11 ms, maximum 1.70 seconds |
| Readiness / application storage failures | Zero failed probes; zero 503 responses in the final run |
| Maximum backend process-tree RSS | 184,229,888 bytes, about 175.7 MiB; includes server/launchers/children |
| Retained database after eight runs | 54,038,528 bytes, about 51.5 MiB; intentional retained history/reports |
| Integrity and completion | integrity_check=ok, zero FK violations, eight completed/superseded runs, zero active jobs |
| Tracking/result coverage | Complete unique result pagination; retained action counts 5 / 100 / 2,000; no pending automation/error after catch-up |
| Scratch files | Zero parser descriptor/output files after every trial |

The benchmark also proves opaque 404 for a foreign workspace and stable repeated-run logical
hashes. [Equivalence evidence](../backend/benchmarks/results/equivalence.json) independently
loads the actual Phase 10 reconciliation source from Git and compares every result field,
canonical row, candidate, rank, reason, assignment, candidate count and compared-pair count
against the final implementation for 100 normal, 2,000 normal and 2,000 dense inputs. All are
identical. Its timings overlap regression work and are diagnostic, not the isolated HTTP table.
The final dense exposure remains INR 360,000.00, with all 2,000 invoices unresolved.

### Local rehearsal budgets and retained boundaries

Chosen margins for these fixed datasets on this PC: upload accept under 1 second, parse under
5 seconds, 100-row matching under 2 seconds, normal maximum matching under 5 seconds, dense
maximum matching under 15 seconds, initial action catch-up under 5 seconds, and ordinary
bounded reports under 15 seconds. Concurrent readiness target: no failed probes, p95 under
100 ms and maximum under 3 seconds. These are local acceptance budgets with margins, not
universal performance guarantees or permission to increase limits. The final measurement fits.

Database growth is retained business history, not a memory/disk leak. Capacity can be exhausted
before the numerical run/import quotas: eight stress runs already use about 51.5 MiB of the
64 MiB DB limit. Preserve a backup and use existing reviewed maintenance; do not silently delete
history or recreate a database. Maximum input rows remain 2,000, file size 5 MiB, pair cap four
million, candidate cap 10,000, one active child, five pending jobs per workspace, 60-second child
deadline and sampled 256 MiB child-tree RSS. A candidate-heavy graph can fail its explicit cap;
large meaningful report histories can still fail REPORT_PAGE_LIMIT, byte or snapshot caps.

No cloud worker, Redis, external DB, dependency update, new environment switch, public/private
route change or SQLite migration was introduced. New ordinary report snapshots carry internal
source-summary fields; existing public API DTOs stay aligned. The 81-page/146,378-byte synthetic
maximum repeated-history report was rendered and inspected at pages 1, 41 and 81; first/last
selected invoices remained present, text/footer spacing was readable and no overlap/clipping
was observed. It is local synthetic QA, not a new legal-verification capability.

The focused new regressions cover linear normalization effort, Decimal floor boundaries,
competing successful checkpoints, report context/follow-up preservation, summarized routine
refresh dates, stable page-limit codes, real readonly/write coexistence, and a real SQLite
commit while matching computes from its copied inputs. Full backend/security/restart/backup,
worker backpressure/cancellation and website gates are recorded below after their final result.


Engineering references supporting the lock-lifetime/query work: [SQLite rollback-mode locking](https://www.sqlite.org/lockingv3.html),
[SQLite cache-spill behavior](https://www.sqlite.org/pragma.html#pragma_cache_spill),
[Python profiling](https://docs.python.org/3/library/profile.html) and
[RapidFuzz ratio](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html#ratio).
Measurements and correctness claims above come from the local code/tests, not those reference documents.


Final review gates on the same measured application source:

- **Full backend: 343 passed, 1 skipped in 733.76 seconds.** The platform skip needs Windows
  symlink privileges; ordinary junction rejection passed. Coverage includes access/CSRF/revocation,
  parser and malformed-body boundaries, exact matching/review races, source supersession,
  audit rollback/quotas, report content/expiry/leases, case/proposal/action workflows, worker
  deadline/RSS/queue/interruption handling, actual restart and offline backup/restore.
- **14 browser checks passed in 2.1 minutes**: six actual business journeys plus existing screen,
  privacy/failure and real security scenarios. **2 built-preview checks passed in 20.7 seconds**
  under actual CSP, including real upload/confirmation and framing/configuration restrictions.
- **10 Node client/config checks passed.** Canonical-field/76-type generation remained aligned;
  strict TypeScript/Vite build passed. No frontend application source changed.
- Frozen offline uv sync checked 37 installed packages; Ruff lint/format across app/tests/benchmarks,
  compileall and Git whitespace checks passed. Locks and existing environment settings are unchanged.
- The complete final load measurement passes with six actual PDF downloads, eight completed runs,
  correct result/action coverage, no processing scratch files/active jobs, zero health failures,
  zero 503s, valid database integrity and opaque foreign-workspace 404. Full-field matching
  equality to the Phase 10 source also passes. Visual report review is recorded above.

This is local verification, not a claimed GitHub CI result or production/zero-defect guarantee.
Phases 12–14 remain pending: frontend profiling/smoothness, conditional real WhatsApp and the
whole-application hackathon rehearsal. The separately supplied landing page/design remains pending.


## Phase 12 completion and measured verification - 2026-10-04

Scope is the existing connected internal website. All earlier business workflows, exact amounts, live backend authorization, scoped state, CSRF/version/idempotency and private report rules remain authoritative. No Phase 13 provider implementation or landing-page redesign is included.

The built Phase 11 baseline at 4ff43fe successfully ran real 100-row and 2,000-row uploads, confirmation, comparison, review, pagination, work queue/history, PDF generation/download, repeated navigation, mobile layout and a second authenticated tab. Both lost their selected result filter after saving review because a same-URL reload removed the comparison subtree. The successful baseline is retained in frontend/benchmarks/results/before.json; the initial selector-error attempt is not completion evidence.

Phase 12 retains loaded data only for the same client identity, session epoch and URL during explicit refresh, marks it refreshing and disables affected save/approval/download operations while versions reload. Changed context/URL/session hides old data synchronously and aborts old reads; 401/403/404 discard data. Same-version unsaved fields and open panels remain; existing version-keyed evidence forms reset on changed versions. There is no persistent business cache or automatic write retry.

Active processing reads start at two seconds and back off to five seconds when jobs take longer. Job status is read on parent state/version changes instead of running a second independent poller. Routine membership refresh remains 15 seconds, queue refresh remains 10 seconds, and backend default request limits are unchanged. Hidden tabs clear polling timers and resume one current check when due; read failures back off and honor bounded numeric Retry-After hints. Denial stops automatic retry. Started reads remain cancellable by scope/session; mutations are never automatically resubmitted.

Collapsed evidence history renders only its summary. Opening renders the first 20 retained events; explicit Show more history reaches every retained event, and closing removes hidden descendants. Candidate details and acceptance options use 20-item pages with every server candidate still reachable, preserving ranking and evidence. Existing source/result/list pagination stays 20. Currency formatting reuses Intl.NumberFormat and preserves the minus sign for exact -0.xx decimal strings; money is not recalculated in the browser.

Keyboard changes add a skip link, move focus to the main heading on section/context navigation, and give tables named focusable scroll regions. Small-screen tables retain readable columns with horizontal scroll inside the region. No browser-wide horizontal overflow or replacement landing design is intended.

Eight focused usability regressions cover unchanged-version draft retention and disabled saves during refresh, denial clearing, 100-event lazy history/all-event access, processing request budget/terminal errors, hidden visibility, server retry hints, delayed filter replies, mobile keyboard use and 60-candidate access/exact negative sub-rupee formatting (the last two are combined scenario checks). The real journey helper now opens evidence panels only when closed and waits for refresh before editing; it no longer assumes every save destroys/collapses the detail. This changes the test's navigation assumption, not backend expected outcomes.

Final verification: **22 browser checks passed in 2.7 minutes**: six real business journeys, two real security journeys, four explicitly simulated privacy faults, two screen fixtures and eight usability checks. **11 Node client/configuration checks passed**, including bounded retry hints and denial of benchmark files through Vite dev serving. **Two built-preview checks passed in 19.2 seconds** under the actual content security policy. **Six backend website-contract checks passed in 72.94 seconds**. Strict TypeScript, formatting, the generated 76-type contract comparison and Git whitespace checks passed. The real-workload measurement passed in 54.8 seconds against the final application source. The initial fixture/selector/helper failures were corrected and are not counted as passing evidence; notably the retry-hint fixture needed the same CORS-exposed header as the real backend, and retained panels needed conditional opening in the journey helper.

Full backend regression remains the 343-pass/one Windows privilege skip Phase 11 evidence, rather than a newly claimed Phase 12 full run. Phase 12 has no backend runtime/schema/dependency changes; the agreed focused/batched cadence applies, with combined full regression due in Phase 14. All six real business journeys continue to cover original workflows, reports, role/context changes, actual delayed replies, restart, revocation and stale-write recovery. These results support connection to earlier phases within the tested local scope.


### Recorded website performance and visual review

[Before](../frontend/benchmarks/results/before.json) measures committed Phase 11 frontend source at `4ff43fe`; [after](../frontend/benchmarks/results/after.json) measures final Phase 12 source SHA-256 `d6138a7c858964db41dd85335d610aadb1246a1994061fc98f40fc357c3850fc`. Both use the same installed stack, synthetic datasets and isolated real local API. Runtime source hashing normalizes LF and sorts filenames case-sensitively. [The measurement instructions](../frontend/benchmarks/README.md) explain how to repeat it. No real taxpayer records or presenter configuration are read.

| Observation | Phase 11 baseline | Phase 12 final |
|---|---|---|
| Initial login UI | 907 ms | 884 ms |
| Navigation median, 100 / 2,000 rows | 153.56 / 167.00 ms | 149.54 / 149.98 ms |
| Navigation maximum, 100 / 2,000 rows | 217.80 / 217.17 ms | 200.38 / 232.68 ms |
| Result filter after saving review | Lost in both workloads | Preserved in both workloads |
| Collapsed action-history descendants | 38 / 38 | 1 / 1 (summary only) |
| Main measured page API requests | 89 / 90 | 86 / 88 |
| Retained JS heap change after repeated navigation | 188,616 / 24,888 bytes | 202,872 / 45,952 bytes |
| Compiled JS / CSS resource bytes | 283,404 / 3,776 | 286,343 / 4,282 |

All final local budgets pass, with no API/browser errors: ordinary measured interactions below one second, parsed previews 2.52–2.59 seconds, comparison readiness 2.38–2.42 seconds, PDF readiness 2.42 / 4.50 seconds, and private downloads 0.37 / 0.30 seconds. The 100-row initial comparison contains 95 exact and 5 suggested matches; the 2,000-row comparison contains 1,900 exact and 100 suggestions. One reviewed suggestion moves to REVIEW_ACCEPTED and remains present in retained results. Three complete navigation rounds give 18 navigation observations per workload. Long tasks remain (55/62/68 ms in the final run); the change does not promise zero lag.

This is one observation per dataset, including automation overhead, not a statistically established general speedup. Startup and navigation remain broadly similar, and the small bundle increase is explicit. The measured practical improvements are preservation of filters/forms, fewer redundant requests, bounded hidden-history/candidate rendering, and controlled polling under the separate long-job/visibility/retry tests. Heap measurements cover garbage-collected JavaScript, not full browser-process memory or a proof against every long-lived leak. Budgets are margins on this Windows PC, not guarantees for all devices or network conditions.

Final 390px screenshots for both workloads were inspected: controls and summaries remain readable, tables scroll inside their named regions, and the page stays within the viewport. Separate automated 320/390px keyboard tests verify no page-wide horizontal overflow and access to offscreen table columns. These are installed-Chrome viewport checks, not physical-phone, Safari or external-network evidence. Screenshots are ignored under frontend/benchmarks/screenshots; synthetic JSON measurements are committed. Benchmark files are denied by development serving. Real WhatsApp/device/provider setup remains Phase 13.

No new dependency, migration, backend endpoint, environment switch, external database, hosted service or landing-page design is introduced. Default backend limits stay unchanged. The isolated measurement server raises its test-only request budgets for rapid synthetic setup; those settings are not application defaults. Phases 13–14 and the supplied landing page/design remain pending.


## Phase 13 implementation started — 2026-10-04

Work proceeds locally while Meta account, recipient entitlement, send budget and an approved HTTPS callback method remain pending. No tunnel, cloud host or real provider send is provisioned automatically. The existing default send budget stays zero. The implementation will add durable linking/inbox/outbox/capability tables through a backed-up explicit offline schema 5-to-6 upgrade, preserving all existing business tables; startup will not silently migrate the presenter database. Browser services keep their session/CSRF boundary. Trusted linked identities will use the same live user/membership checks with user-version revocation. Channel commands capture context and replay deterministic operation keys after interruption; external sends have separate recorded acceptance/delivery/uncertainty. Local tests and adapter fixtures do not meet the physical-phone completion gate.


## Phase 13 local implementation and verification record — 2026-10-04

The user answered: **“Not set up yet; build local integration first.”** The backend and internal website now have the local integration described below. Phase 13 remains **in progress**, because there is no configured Meta account, permitted recipient proof, approved HTTPS callback or physical-phone result. Phase 14 has not started. No live provider message was sent and no tunnel, hosted server, external database or new dependency was created.

### Delivered connection to previous phases

| Existing workflow | Channel behavior now implemented | Human or external gate |
|---|---|---|
| Locally provisioned accounts and roles | One-use browser-generated LINK code; phone identity checks live user version/membership | Account and permitted phone setup |
| Private purchase and portal imports | UPLOAD PURCHASE/2B reserves a short intent; document bytes enter the existing import/parser/job service | Explicit website mapping/review/confirmation; actual Meta media-format acceptance |
| Reconciliation and review | RUN reuses saved READY sources and deterministic operation receipts | Multiple confirmed sources require website selection; no silent guess or phone legal approval |
| Retained business work queue | STATUS reads saved context, source counts, run state/totals and stale-evidence warning | Website remains the rich review interface |
| Supplier follow-up drafts | Existing draft-specific consent proof, explicit reviewer queueing, durable outbox and action timeline reference | Exact supplier must send CONSENT; actual delivery/window/account entitlement |
| Recorded review reminders | Opted-in OWNER/REVIEWER links can receive deduplicated due-date alerts | Open permitted reply window and remaining configured attempt budget |
| Existing report jobs and PDFs | REPORT requests the existing report service; readiness watch creates an expiring capability | Current source, active link/membership and download limits |
| Previous security/privacy rules | Browser Origin/CSRF/session boundary retained; signed callback boundary separately validated | Physical callback/proxy configuration and provider gate |

Normal phone commands do not automatically confirm imports, accept fuzzy suggestions, approve legal credit, file a return, transfer a payment or guarantee recovery. They execute the same local application services as the website. A received/queued message, Meta acknowledgement, delivered callback and read callback remain distinct facts.

### Durable behavior and boundaries

Schema 6 adds only channel tables to schemas 1–5. Existing installations must stop the backend and run `python -m app.manage storage-upgrade` from backend/. The operation validates the old version and creates a validated backup before transactional additions. Startup refuses an old or incompatible database; it never resets customer data. A synthetic populated v5 test verifies every pre-existing table row unchanged, the v5 backup and repeated upgrade behavior. The presenter database was not upgraded by this coding session.

Callback POSTs validate HMAC over bounded raw bytes before JSON parsing, then verify configured WABA/phone IDs across the batch. Duplicate keys, excessive depth/body/event counts and malformed fields are rejected. Accepted events are committed before acknowledgement. A callback replay creates one durable event. Unknown supported account status strings are ignored without inventing delivery success; non-string malformed status values are rejected.

Phone tasks capture link/context version, source identities and deterministic operation keys. Restart recovers interrupted local work using original shared-service receipts. A reserved document intent cannot be consumed by another event. Media transport checks approved public HTTPS destinations, TLS, MIME, byte size and provider digest before using the existing bounded parser. CSV transport acceptance on a physical Meta account remains unverified; XLSX is the preferred acceptance file until proved.

Replies reserve their attempt budget and ATTEMPTED record before external I/O. Ambiguous responses become UNKNOWN; startup does not automatically resend them. Delivery callbacks can reconcile uncertainty by opaque logical ID/provider ID and recipient. Lower status callbacks cannot turn READ back into acknowledged/failed. An in-flight external send cannot be recalled after revocation; queued work and future authority are rechecked/cancelled.

Link/consent codes are hashed in storage, last ten minutes at most and are used once. Browser controls keep returned codes only in component memory and clear them on expiry or denied access. Report tokens have 256-bit strength, are derived only at send time, and only their hashes are retained in capabilities. They expire within ten minutes and allow at most three downloads. Unlink/context changes revoke them; redemption checks membership, link version, current artifact and bytes again.

The configured send budget defaults to zero and is a persistent cumulative attempt cap, not a billing guarantee. Failed and uncertain attempts still count. Alerts also account for queued work. Free-form sending requires a current 24-hour inbound window; no approved template adapter or out-of-window outreach is implemented. Supplier consent is specific to the draft/contact and gives no access to the buyer’s account or reports. STOP revokes supplier consent and cancels its queued messages; UNLINK separately revokes a buyer link.

### Checks actually completed; regression deliberately pending

- The initial extended channel/provider set passed **29 tests in 86.70 seconds**, including actual local imports, XLSX parsing, confirmed-source reconciliation, generated PDF download limits, crash replay, supplier consent/STOP, due reminders, password revocation, schema preservation and bounded fake transport.
- Final review added refusal of ambiguous READY sources, rejection of non-string callback statuses and malformed provider ports/hosts. The new real-import ambiguity test passed after using distinct source bytes; repeated identical uploads correctly reuse the existing import. The malformed-status check and adapter changes await the final regression/affected rerun. Earlier fixture/setup/selector failures are not passing evidence.
- A browser run passed **24 of 25 checks**: all three new channel checks passed (real default-disabled API plus two explicitly simulated channel-control cases). One existing real journey opened a blank page and failed before login. A subsequent journey rerun failed server startup. These failures remain unresolved verification items; there is no complete green browser-suite claim.
- Full backend regression was stopped when the user said **“dont do a regression run now.”** No Phase 13 whole-suite result is claimed. Do not resume regression without the user authorizing it. The last completed whole-backend result remains the separate Phase 11 evidence.
- Final lightweight checks passed: Ruff lint/format on 80 files, Python syntax compilation, Git whitespace, frontend formatting, strict TypeScript, generated contract alignment (93 DTOs) and Vite production build. No dependencies/lockfiles changed. No regression was restarted after the user stopped it.

### Remaining Phase 13 acceptance work

1. Resolve the recorded browser startup/blank-page verification failure; rerun affected checks and the final regression only when authorized.
2. Configure actual Meta app/WABA/sender/test recipients, permissions, token expiry and currently supported Graph version. Fixture version strings do not establish account support.
3. Choose an approved HTTPS forwarding method. Forward only `/webhooks/whatsapp` and `/wa/reports/*`, preserve the expected Host and disable capability/token query logging. Keep local browser/auth/business routes private.
4. Complete subscription challenge and signed POST delivery from Meta; verify actual media MIME/size/hash behavior and both account identifiers.
5. Check current pricing/entitlement in the actual account and explicitly choose an attempt budget. Keep zero until that is done; never promise free usage from old report text.
6. On a physical permitted phone, prove LINK, STATUS, purchase/2B XLSX attachments, website confirmation, RUN, REPORT, repeated callback, restart, expired capability and UNLINK against the same persisted website records.
7. If supplier outreach/reminders are enabled, prove correct recipient consent, fresh source/draft, role revocation, STOP, window expiry, real delivery callback and exact attempt accounting. Record provider acceptance independently of supplier invoice correction.
8. Update the phase status only after real acceptance; Phase 14 combined rehearsal remains a subsequent phase.

## Expansion implementation started — 6 October 2026

User authorized coding the selected thirteen priorities, AI invoice intake and configured automation, with a thirty-minute delivery target and focused checks rather than a full regression now. Start with the connected demonstration: document extraction/reviewer confirmation; four-way evidence; three-clock Gate; controlled partial approval and correction request; new 2B evidence making an old approval stale; source-backed audit. Reuse existing scope, imports, cases, proposals and channel protections. Schema additions use explicit backed-up local upgrades. No real GST fetching/filing or bank execution is claimed from a simulator. Credentials remain backend-only.

Implementation groups: (1) Passport/intake and source links, (2) commercial/GST findings and clocks, (3) decisions/resolution and stale approval, (4) vendor/IMS/anomaly/CFO/dossier, (5) scenario/outcome/notice extensions, (6) focused endpoint/workflow checks and website build. Status is in progress, not completed.


## Invoice expansion gap completion — 7 October 2026

The selected thirteen priorities already had initial implementations. This follow-up completes the four reported code gaps: item-level commercial matching, the invoice-to-WhatsApp connection, broader observed vendor/risk patterns, and a retained four-action GST review workflow. It does not mark the full 36-feature roadmap or the externally integrated product complete. Changes remain local and unpushed at the user's request.

### Item-level records and the payment Gate

Confirmed invoice, purchase-order and receipt records now retain up to 100 individual items. Each item has a description, optional item code, quantity, unit and goods value. Item values must sum exactly to the record's goods value. An invoice imported through the earlier CSV/XLSX path can receive item details through the same desk without rewriting its original canonical purchase source.

Matching uses the item code when every line in both records has one; otherwise it uses normalized exact descriptions. Split lines for the same item are aggregated. Product identity, quantity, unit and value must agree. A different product with the same invoice total fails. Missing items or unknown units require review; matching header totals alone cannot establish a commercial match. Per-item differences are visible in the desk.

Recorded disputes, shared bank accounts, invalid reference formats, missing references explicitly classified as required, and future invoice dates route the Gate to review/escalation. Required-reference classification is a reviewer fact, not an assumed legal conclusion. Bank details and invoice references remain saved evidence; the application does not verify bank ownership or government IRN authenticity.

Payment recommendations and saved approvals remain separate from bank execution. Pay/part-pay approval requires confirmed payment facts. Changed items, sources or recorded risk facts change the evidence fingerprint and make an old approval stale. The same imports, reconciliation, cases, proposals, reports and membership/CSRF/version boundaries remain in use.

### Vendor history and review signals

Vendor profiles use up to the latest 250 confirmed invoices in the same workspace/registration across periods, with the limit and limited-history status visible. The base score explains GST matches (40%), order items (20%), receipt items (20%) and duplicate checks (20%). Recorded missing required references and disputes apply bounded penalties; observed correction durations above seven days also affect the score. Missing facts remain listed rather than treated as verified facts.

Signals cover duplicate identities, record mismatches, reference formats, required-but-missing references, shared recorded bank accounts across suppliers, repeated gross amounts across at least three distinct invoices, future dates, amounts exceeding three times the vendor's observed median, and tax ratios differing materially from observed history. Amount/tax-ratio outliers require at least five history samples. These are explainable review signals, not fraud findings or statutory rate determinations.

Correction duration measures time between local observations of conflicting and aligned saved evidence. It does not claim to measure the supplier's actual government filing time. Historical exposure, current exposure, recorded disputes, coverage and score factors are available alongside the vendor score. Monetary dashboard totals still deduplicate the same invoice identity.

### Connected supplier corrections and continuous watch

Invoice corrections now use the existing signed Meta callback, durable outbox, delivery history, attempt budget and worker. No second server, external database or messaging service was added.

A reviewer creates an invoice-specific, ten-minute opt-in invitation. Only the intended supplier phone can consume `PCONSENT code`; the code is hashed in storage and gives no buyer account or report access. Invitation use checks current evidence, live role and user version. Browser codes clear on expiry or invoice switches.

Consent can queue the prepared correction automatically. Watch mode prepares and queues a new request when received evidence changes, provided consent, current sender authority, the inbound response window and configured send budget allow it. Sending rechecks evidence and authority before reserving its attempt; network I/O runs outside the database transaction. Stale or revoked work is cancelled. An uncertain send is retained as UNKNOWN and is not automatically resent.

Supplier replies use the scoped `PCASE reference ACK`, `PROMISE YYYY-MM-DD`, `CORRECTED` or `ESCALATE` protocol. Signed events are deduplicated and checked against the consenting phone; a supplier cannot change another invoice or upload invented GST evidence through a reply. A reported correction stays awaiting verification until the saved four-way records align. A watched invoice can then resolve automatically, with retained source and event history.

STOP revokes supplier consent and cancels queued invoice messages; it remains effective even when ordinary invoice history has reached its cap. Revoked invitation authority stops further sending. Actual provider acknowledgement, delivery, read, failure and uncertainty remain distinct from supplier acknowledgement/correction. Delivery events are included in the invoice dossier.

Physical WhatsApp acceptance remains pending the user's Meta app/WABA/sender/recipient and HTTPS callback setup. The local connection is exercised through signed callback and fake transport tests; that evidence does not establish live Meta delivery. Send budget remains zero unless explicitly configured. Out-of-window template outreach is not implemented.

### Four-action GST review workflow

The reviewer can save ACCEPT, REJECT, PENDING or HUMAN REVIEW with a reason and current evidence fingerprint. ACCEPT requires aligned records without recorded risk concerns. REJECT requires explicit confirmation. ACCEPT/REJECT/PENDING require an actual selected matching GST record to act on; a missing record goes to human review. Changing evidence makes the saved GST review stale. Recording a GST review alone does not change the evidence fingerprint or invalidate a payment approval.

Every saved action remains NOT_SUBMITTED. Real government fetching and filing still require an authorized adapter, credentials and supported submission/acknowledgement workflow. The demo fetching controls remain clearly marked synthetic statement creation; real uploaded statements continue through the existing reviewed import path.

### OCR and supported files

Gemini now proposes individual items and printed bank details alongside invoice header fields. The provider receives a portable inline schema; local Pydantic validation still enforces all array, text and field bounds. This fixes the live provider rejection found with the expanded nested schema. The approach was checked against [Google's structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output) and the configured provider.

Live controlled PDF, PNG and JPEG samples all extracted the invoice header and item correctly after the fix. Multiple-invoice responses and more than 100 extracted items are refused. PDF/PNG/JPEG uploads remain limited to 4 MB and require consent and reviewer confirmation. These sample checks do not guarantee arbitrary document layouts or poor scans. CSV/XLSX imports still require supported columns and mapping.

### Focused verification

Final checks completed:

- **10 focused invoice/item/OCR-boundary tests passed in 48.52 seconds.** They cover the connected invoice-to-part-pay/source-change flow, exact item identity/split lines/units, all four retained GST actions and stale reviews, historical vendor patterns, signed supplier consent/replies, correction verification, revoked authority, uncertain sends, scope denials and preservation of a populated v6 installation during the existing v7 upgrade.
- **5 affected legacy WhatsApp checks passed in 45.03 seconds**, covering signature boundaries, delivery ordering/budget, old inbound events, consent isolation and STOP.
- **2 real Chrome workflow checks passed in 28.4 seconds** at 1280px and 390px, using an isolated real local API. The screens saved individual receipt items, refused a same-total wrong-product match and retained a PENDING GST review. All four desk tabs had no page-wide horizontal overflow. The mobile screenshot was inspected.
- **Live configured Gemini PDF, PNG and JPEG samples passed** after the provider-schema repair, including header and individual-item extraction. The browser server intentionally had no AI credentials; its seeded records are not independent live-OCR evidence.
- Strict TypeScript, production Vite build, generated **116-type** API alignment, changed-backend Ruff checks and Git whitespace checks passed.

One earlier invoice test raced the real background monitor while retaining an old expected version; the version guard correctly rejected that write. The connected test now advances the monitor explicitly for deterministic version assertions, while watched resolution is separately exercised. Initial provider-schema and browser-selector failures were corrected and are not counted as passing evidence.

No full regression was run. No commit/push was made. Physical Meta/GST/bank integration acceptance remains separate from these local checks.


## Hackathon demo bank gateway — 7 October 2026

The user requested a visible bank-payment blocker for the hackathon. The invoice desk now includes a collapsed **Demo bank** panel connected to a persistent simulated transfer ledger. It never calls a bank or changes recorded real payments. Both the API response and the screen label this distinction.

Each simulated transfer checks workspace write authority, Origin/CSRF, an idempotency receipt, current invoice version/evidence, confirmed payment facts and the current approval. Missing/stale approvals, conflicting commercial evidence, recorded risk concerns, excessive amounts and exhausted permitted balances are blocked. A denied attempt is recorded as BLOCKED; permitted simulated money is recorded as RELEASED with its amount, approval and evidence fingerprint.

While tax evidence is missing, a part-payment approval can release only the remaining recorded base value. Cumulative simulated releases are deducted; a second approval cannot be used to release the held tax. Replaying the same request cannot create a second transfer. Changed GST evidence makes the old approval stale before any further release.

The intended demo is:

1. Confirm the invoice, its individual order/receipt items and the already-paid amount.
2. With missing GST evidence, attempt ₹1,18,000: blocked.
3. Approve a ₹1,00,000 part payment; attempting ₹1,18,000 still blocks.
4. Release the permitted demo amount: ₹1,00,000 released, ₹18,000 remains held/protected.
5. Upload/select corrected 2B evidence or explicitly use the sample-fetch correction control.
6. The old approval is stale; attempting the remaining ₹18,000 still blocks.
7. Save a fresh aligned-record approval and release the remaining ₹18,000 in the demo.
8. Inspect the retained transfer/source history. Actual bank transfers and real payment facts remain unchanged.

Real bank enforcement would require the company to route payment initiation through an authorized bank/payment connector. This simulated gateway demonstrates the decision and enforcement contract; it does not intercept transfers initiated elsewhere. Similarly, real automatic GST acquisition is an authorized-adapter roadmap item, and physical WhatsApp sending requires the separately recorded Meta setup.

Demo gateway final verification: **11 connected backend checks passed in 57.30 seconds**, including the complete ₹1,18,000/₹1,00,000/₹18,000 sequence, duplicate receipts, cumulative part-payment protection, stale approvals and unchanged real payment facts. **Two real Chrome desktop/mobile checks passed in 29.4 seconds**, including visible payment blocking. Strict TypeScript, Vite build and **117-type** generated API alignment passed. The earlier five affected legacy WhatsApp checks and three live OCR format samples remain the separate evidence recorded above. No full regression or Git push was performed.


## 2026-10-07: invoice workflow handoff completed

Invoice desk is now the default section. A confirmed invoice has Cases for this invoice and Payment drafts for this invoice links. Navigation retains its exact source document, company and accounting month in memory; switching context clears the selection. Back to this invoice restores the selected saved invoice. Show all records exits the focused view.

A read-only, authenticated workflow endpoint resolves the exact purchase import row, the selected ready GST statement, its current comparison, related evidence cases and drafts. It reuses existing tables and permissions. Reading workflow data does not create cases, drafts, evidence observations or approvals. Confirmed source changes now start comparisons automatically; the focused screen also catches up older confirmed invoices whose selected sources are ready but have no comparison. Cases and drafts are preselected where their prerequisites exist; otherwise the interface explains the next step. New or updated related records refresh after saving. Drafts from another comparison remain visible as history and cannot be approved through the focused current-invoice flow.

Verification: one connected backend integration test passed (14.69 seconds), covering a non-first source row, unrelated invoice exclusion, related cases/drafts, unchanged approval state, changed GST selection, unknown resource/workspace and unauthenticated denials. Two focused Chrome browser tests passed at 1280 and 390 pixels (6.2 seconds), covering the default screen, case/draft preselection, return navigation, no automatic mutations, context clearing and horizontal overflow. TypeScript, frontend build, scoped Ruff checks and Git diff whitespace check passed. Existing Sources-oriented browser fixtures now request that section explicitly. No full regression run, commit or push was performed.


## 2026-10-07: automatic confirmed-record comparison completed

Confirmed invoices and selected GST statements now start the existing comparison automatically. Confirming a new statement rechecks the affected confirmed invoices; selecting another statement updates the selected invoice. The focused website polls queued work and shows the completed result in its case and payment-draft screens. Older saved invoices with ready sources can catch up through the existing authenticated refresh action. Missing actual records remain required; the application does not invent them.

Automatic requests reuse an existing job for the same exact sources and policy under the database write lock. Repeated requests do not queue duplicate work. Publishing a replacement comparison supersedes older comparisons for the same purchase source, preserving current comparisons for other invoices in the same month. Failed or delayed work remains visible rather than repeatedly retrying in a loop. Existing approvals are never created automatically; changed evidence still requires a fresh deliberate decision. No schema change was needed.

Focused verification: three backend integration checks passed in 35.29 seconds, covering exact invoice handoff, missing-source behavior, concurrent duplicate prevention, independent invoices, updated statements, authorization boundaries and existing source-replacement history. Two desktop/mobile Chrome workflow checks passed in 14.7 seconds, including queued-to-completed updates without a Start comparison click, current-record preselection, explicit approvals, context clearing and layout. TypeScript, the production frontend build, generated 119-type API alignment, scoped Ruff and whitespace checks passed. Both local services returned HTTP 200 after restoration. No full regression, commit or push was performed.
