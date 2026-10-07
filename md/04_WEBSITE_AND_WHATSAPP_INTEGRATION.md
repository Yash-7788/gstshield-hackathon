# GST-Shield — existing website and WhatsApp integration

> **Active local implementation (2026-10-04):** This is a website with a Python backend running on the PC. Authoritative storage is a private SQLite file under `backend/data/`; accounts are provisioned locally and browser access uses revocable sessions. No external database, hosted identity, cloud storage or application hosting is selected. Phases 1–12 are complete and locally verified. Phase 11 passed the full backend regression (343 passed, 1 Windows privilege-related skip). Phase 12 passed 22 browser checks, built-preview checks and real 100/2,000-row website measurements. See 05 for dated evidence. Phase 13 local WhatsApp integration is implemented with focused checks; Meta setup and physical-phone acceptance remain pending. Phase 14 is not started. Full Phase 13 regression was stopped at the user’s request. The landing page/design is pending. The user authorized a new internal website in Phases 8–9; real WhatsApp remains Phase 13.

Baseline 2026-10-03. Future implementation instructions. [08](08_CONTRACTS_AND_ALIGNMENT.md) owns API contracts; [03](03_BACKEND_AND_DATA_SPEC.md) owns shared behavior; [06](06_SECURITY_AND_PRIVACY.md) owns authentication, signatures and linking safeguards.

## Active channel implementation phases

Follow the expanded [14-phase plan](05_BUILD_AND_VERIFICATION_PLAN.md): Phase 8 builds the authorized internal website, Phase 9 connects real backend operations, Phase 10 reviews browser security, Phase 12 measures smoothness, Phase 13 proves WhatsApp and Phase 14 rehearses both channels. Backend reports are Phase 5; backend security/performance are Phases 7/11. Safe rendering, scoped state and bounded requests apply when functionality is introduced, not only in later review phases. Phase 2 selects local accounts, HTTP-only browser cookies and CSRF-protected mutations. No hosted auth SDK is needed.

## Internal application and later landing-page integration

The user authorized a new internal application while reserving the separately supplied landing page/design for later. The connected React/Vite/TypeScript workspace and exact pinned versions are recorded in 02. When the landing page arrives, inspect its actual files and routing before integration; preserve compatible design assets. The original Next.js 14 suggestion does not override the implemented stack.

Build one API client around the actual framework. Generate TypeScript types from the backend OpenAPI document after contracts stabilize. Keep monetary values as strings; use decimal-aware display or server-formatted values. A JavaScript Number must not become the source of financial calculation.

Local accounts are provisioned with the offline operator command. POST /api/v1/auth/login sets an HttpOnly SameSite=Strict cookie. The API client uses credentials:include on requests, obtains CSRF state with GET /api/v1/auth/session, and sends X-CSRF-Token on private mutations. A 401 clears private state and returns to sign-in; there is no refresh-token flow. Keep CSRF state in memory and never copy the session cookie into localStorage. Clear scoped state on logout or account change.

| Website feature | Contract / result |
|---|---|
| Workspace picker | GET /api/v1/workspaces |
| Registration picker | GET /api/v1/workspaces/{workspace_id}/registrations |
| Import upload | POST /api/v1/workspaces/{workspace_id}/imports |
| Mapping preview | PATCH /api/v1/workspaces/{workspace_id}/imports/{import_id}/mapping |
| Import confirmation | POST /api/v1/workspaces/{workspace_id}/imports/{import_id}/confirm |
| Start analysis | POST /api/v1/workspaces/{workspace_id}/runs |
| Progress | GET /api/v1/workspaces/{workspace_id}/jobs/{job_id} |
| Result summary/list | GET run and paginated run results |
| Candidate review | POST result review with expected_version |
| Case timeline | GET/POST cases and POST case evidence |
| Download PDF/proposal | Artifact creation job, then authorized artifact download |
| WhatsApp linking | POST link-code; display expiry and linked status |

## Current browser connection handoff

Use the same HTTP hostname for website and API: localhost:3000 and localhost:8000 by default. Different ports are permitted; mixing localhost and 127.0.0.1 breaks the intended SameSite cookie flow. CORS allows exact configured origins and credentials; it never grants membership by itself.

Phases 1–9 now implement the local import/run/review/case/proposal/action/report operations and connected website listed in the completion map below. WhatsApp catalog entries remain future contracts. Current OpenAPI and the recorded real browser tests define delivered routes, not earlier planning tables alone.

On initial load, recover the session once. If authenticated, load workspaces and only then registrations for the selected permitted workspace. A 404 on a scope picker should remove the stale selection and refetch allowed context. A 429/503 follows Retry-After without an unbounded retry loop. Failed sign-in does not expose which usernames exist.

Local administrator commands run with the backend stopped. They create accounts/workspaces, add registrations, set/revoke membership and reset passwords. Do not invent public signup or membership editing screens in Phase 8 from this operator mechanism.

## Website state model

Show source import readiness separately from run readiness. A uploaded file may still need parsing, mapping or confirmation. Disable `Run` until both sources are READY and contexts agree. Row validation errors are downloadable and actionable; never disappear behind a generic failure toast.

Poll active jobs approximately every two seconds while the relevant view is visible; back off after repeated network failures. Pause polling when hidden. An unavailable local backend shows “Start GSTShield on the PC” with controlled retry; it does not claim a cloud server is waking. A slow request retains a truthful pending state. Use idempotency keys when retrying creates, so a network timeout does not create duplicate runs.

Filter results by server enum rather than label text. Counts come from the committed summary. Display fuzzy score as similarity, not probability or legal confidence. Show sample-evidence badges near relevant facts rather than only in a footer.

Review mutation waits for the committed server result before changing financial totals. A 409 VERSION_CONFLICT triggers refetch and asks the user to review changed evidence. Cross-workspace cached data is keyed by user/workspace/registration/period/run. Clear it when scope changes.

## WhatsApp as a second working interface

Use Meta Cloud API directly; avoid introducing a paid messaging aggregator or an unofficial browser-session bridge as the core setup. WhatsApp is not only a `wa.me` link: success requires a reachable HTTPS callback, real phone input, authorized processing and a real response.

Meta's official collection describes WABA/phone assets, access tokens, message requests and test-message setup. Dashboard user tokens have a short lifetime, so the demonstration must verify token validity beforehand. Exact account/test recipient restrictions and free entitlements must be checked in the actual dashboard. [Meta collection](https://www.postman.com/meta/whatsapp-business-platform/collection/wlk6lh4/whatsapp-cloud-api)

Required assets: developer app, WABA, sender phone-number ID, enabled recipients in test mode, scoped token, app secret, verification token and HTTPS URL. App subscription must target the intended WABA and event fields. Receiving the dashboard's test callback is not proof real recipient messages reach the integration.

## Linking and active context

1. Website authenticates a user and checks their active workspace membership.
2. Backend creates a random 12-character code (>=60 bits entropy), stores only its hash, limits active codes, and sets ten-minute expiry.
3. Website displays `LINK <code>` and the selected registration/period. User sends it to the configured bot.
4. Verified callback supplies sender wa_id. Transaction atomically consumes the unexpired code and creates that user's link. A consumed/expired code cannot be replayed.
5. Website displays linked status and masked phone. The bot echoes the active context and available commands.
6. Every command rechecks current membership. `UNLINK` or website revocation immediately deactivates the link and its download capabilities.

Never link merely because a phone number appears in an uploaded spreadsheet or user profile. An unaffiliated supplier cannot read the buyer workspace. Initial version supports one active workspace/context per linked phone. Change context through authenticated website controls and display the new context before subsequent commands.

## Command contract

| Command | Response / behavior |
|---|---|
| HELP | Available commands, supported file types and sample-mode notice |
| LINK code | Bind current sender to the authorized context or a generic failure |
| STATUS | Latest selected-context run/job state, counts and review exposure |
| UPLOAD PURCHASE | Set next-file intent; echo registration/period and expiry |
| UPLOAD 2B | Set portal intent; explain canonical versus supported official format |
| RUN | Create/reuse same reconciliation operation as website |
| REPORT | Create PDF for current run; reply when an artifact is available |
| UNLINK | Revoke sender link and download capabilities |

Next-file intent expires after ten minutes and is consumed by one document message. On ambiguous unsolicited attachment, ask whether it is purchase or 2B; do not infer correctness from a filename. A JSON attachment is not automatically official portal evidence. Accept only supported file types with bounded bytes and show the import preview/confirmation flow.

Example response:

```text
GST-Shield · SAMPLE DATA
Acme Demo · GSTIN ending 1Z5 · 2024-05
Run R-104 complete: 84 exact, 8 suggestions, 8 missing.
Recorded tax awaiting review: ₹18,000.00.
This is reconciliation of the uploaded snapshot, not confirmed ITC eligibility.
Reply REPORT for the evidence summary or open the website to review suggestions.
```

These numbers are illustrative copy, not the fixture's required output. Derive actual responses from persisted summaries. Do not expose full GSTINs, bank accounts or vendor ledgers unnecessarily in notifications.

## Callback and processing flow

GET `/webhooks/whatsapp`: check subscription mode and verification token; return challenge only on exact match. POST: read bounded raw bytes, validate `X-Hub-Signature-256` using the app secret, then parse JSON. Meta's archived official SDK documents the GET and SHA-256 validation distinction; use current HTTP APIs rather than adopting that archived SDK. [Official SDK reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/)

Validate account/sender phone-number IDs against configuration. Iterate all entry/change/message elements rather than assume the first element is the sole event. Distinguish inbound commands from message delivery/read/error statuses. Persist a minimal event and enqueue jobs in one transaction before acknowledging. A temporary DB failure returns a retriable error; a duplicate valid event returns success without new effects.

Use inbound message ID as part of the operation's dedup key. Delivery events may repeat/change over time; key them by provider ID, status and event timestamp or stable event hash. Do not create a command for a status event or an outbound echo.

For document messages, fetch media metadata using the configured Graph origin and ID, then retrieve from the validated returned provider location. Never fetch an arbitrary URL from message text or let redirects reach private addresses. Stream with the 5 MB project bound and a timeout, validate type, compute hash, store private bytes, and create the same import lifecycle.

## Sending and download delivery

Persist outbox intent before sending. A response containing provider_message_id marks API acceptance, not delivery. Delivery/read/failure statuses update the record later. A timeout after transmission is UNKNOWN and cannot trigger blind resend. Website can show the uncertainty and offer a deliberate retry with a new audited intent.

For the demo, prefer user-initiated replies within the account's permitted messaging window. Scheduled supplier outreach requires opt-in, template/category compliance and verified account pricing. Keep it disabled until that proof; draft copy is always available. Do not promise the original report's “100 free alerts” as an account fact. [WhatsApp pricing](https://whatsappbusiness.com/products/platform-pricing/)

REPORT returns an opaque expiring capability rather than a permanent public file URL. Generate at least 128 random bits, store a hash, bind to artifact/link, expire after ten minutes, limit download count, and check active link/membership on redemption. This intentionally permits the recipient browser without an additional login, so treat it as a bearer secret. Do not put raw phone numbers or session tokens in the link. Revoke it on unlink; return a generic expired/not-found page without leaking file ownership.

Sending a PDF as a Meta document is optional and must be separately tested; Meta then receives a copy. The link-based flow keeps report delivery simple and controllable for the first demo.

## Verification and failure UX

Test a physical phone: LINK, STATUS, purchase attachment, portal attachment, RUN, REPORT and UNLINK. Refresh website after phone upload; compare imported IDs and counts. After unlink, STATUS and old capability both fail. Repeat a callback and confirm one import/job. Expired token, wrong signature, unsupported file and local backend stop/restart have useful outcomes.

If account setup is blocked, keep an internal adapter emulator for development and mark it clearly. It is not the final WhatsApp proof. Record the blocker and preserve website functionality; never quietly replace the promised phone workflow with a visual mock.

## Frontend handoff inspection

When the website arrives, record rather than assume:

- Framework/version and package manager/lockfile.
- Client-only versus server-rendered routes.
- Existing auth library/session storage and redirect behavior.
- Mock datasets and fields used by each screen.
- Existing API base URL and error handling.
- File-upload controls and currently accepted formats.
- Charts whose totals are computed locally.
- Buttons that currently do nothing or return fixture results.
- Report/download mechanism and popup behavior.
- Responsive layout for mobile browsers.
- Build environment variables actually exposed publicly.
- Deployment output directory and any server functions.

Create a mapping from existing component to contract operation. Replace mocks incrementally so one whole journey becomes real before expanding. Preserve visible design unless it contradicts actual behavior; change misleading labels such as “paid” to “proposal exported.”

## Screen behavior matrix

| Situation | Website response | WhatsApp response |
|---|---|---|
| No selected registration | Context picker | Link/select context instruction |
| No purchase import | Upload instruction | UPLOAD PURCHASE prompt |
| Parse queued | Job status and source filename | Import received; job reference |
| Mapping missing | Preview mapping controls | Open website to map fields |
| Rejected rows | Error details and explicit partial confirmation | Counts + review link; no automatic partial run |
| Ready sources | Enable Run | RUN available |
| Run queued | Pending operation ID | Analysis queued |
| Run complete | Category cards and drilldown | Concise same-run summary |
| Ambiguous candidate | Display alternatives and reasons | Summarize, direct to review screen |
| Source superseded | Historical badge/new-run selector | State latest applicable run/context |
| Expired auth/link | Sign-in/link recovery | No private data; LINK instruction |
| Provider send unknown | Pending/uncertain delivery status | Avoid duplicate automatic message |

Do not move complex mapping or legal evidence adjudication into a brittle sequence of chat prompts. WhatsApp handles convenient uploads/status/report retrieval; website handles rich review. Both still operate on the same domain services.

## Detailed phone upload exchange

```text
User: UPLOAD PURCHASE
Bot: Next document will be a purchase register for Acme Demo, 2024-05.
     CSV/XLSX only, up to 5 MB. This selection expires in 10 minutes.
User: [purchase_demo.xlsx]
Bot: Received import I-12. Parsing is queued.
Bot: Preview: 98 valid rows, 2 rejected rows.
     Review the errors and confirm the accepted rows on the website.
User: STATUS
Bot: Import I-12 is awaiting confirmation. Analysis has not started.
```

The second bot reply is generated by a persisted outbox intent after parsing, subject to the account's permitted reply window and send budget. If sending then is unavailable, the website retains the state and STATUS can retrieve it. A durable job is not a guarantee that outbound messaging will be permitted indefinitely.

## Context changes during processing

A job captures registration/period/import IDs when created. If the user changes context while it runs, its output stays attached to the original context. Completion messages include the original registration/period and cannot update unrelated current screen state.

An upload intent captures context as well. Changing linked context invalidates an unused next-file intent so a later document cannot land in the old period without notice. Unlink cancels pending user intents and revokes capabilities; existing already-authorized non-messaging processing remains visible to authorized workspace members.

## Button actions and confirmation rules

Every mutation has a distinct intention. `RUN` starts analysis; it does not approve suggestions. `REPORT` creates an artifact; it does not approve payment. `UNLINK` revokes access; it does not delete the entire workspace.

If interactive buttons are implemented, the callback payload references a server-generated operation and current version. Reject arbitrary payload strings that name a tenant/resource without authority. Text commands remain the fallback so the demonstration does not depend on rich interactive message support.

## Setup troubleshooting

| Symptom | Check next |
|---|---|
| GET challenge fails | Public HTTPS URL, mode, verification token and plain challenge response |
| Dashboard callback succeeds but phone input does not | WABA subscription, messages field, correct sender asset and recipient/test restrictions |
| Signature invalid | Correct app secret, raw byte preservation, prefix and constant-time check |
| Outbound 401/permission error | Token expiry, required permissions and phone/WABA ownership |
| Message API accepts but phone sees nothing | Provider delivery/error status; acceptance is not delivery |
| Document retrieval fails | Media ID flow, token permission, expired URL, allowed redirect host |
| Callback duplicated | Event key uniqueness and acknowledgement after persistence |
| Response delayed after inactivity | Local backend availability and queued job status |
| Cross-context summary | Link context, job captured context and result lookup scoping |
| REPORT link expired | Generate new capability from current authorized link |
| CSV upload from phone unsupported MIME | Validate content/type mapping, not only filename |

Keep errors observable with request/event/job IDs. Redact tokens, full phone numbers and link codes in troubleshooting output.

## Physical-device acceptance script

1. Sign into the website and create a linking code.
2. Send the code from the intended phone and inspect linked status on the website.
3. Try the same code from another phone; it must fail after consumption.
4. Send HELP and verify the available commands match implemented features.
5. Send STATUS before any run and check the useful empty state.
6. Upload purchase and portal fixtures through the supported flows.
7. Confirm imports and start RUN.
8. Compare phone/website counts and source context.
9. Generate REPORT and open its private capability on the phone browser.
10. Revoke/unlink and prove old commands/downloads cannot retrieve data.
11. Re-link, change period, and confirm old results do not appear as current.
12. Record one successful flow for an honestly labeled outage fallback.

## Safe development emulator

An emulator can inject domain commands into a test adapter without Meta credentials. It uses test identities/fixtures and produces visible SIMULATED_CHANNEL status. Keep it behind local/test configuration and authenticated developer access; never add a public endpoint that accepts arbitrary sender IDs.

Use signed synthetic webhook payloads to test byte/signature behavior locally. Separately perform the physical-device flow. The former verifies our handler; the latter verifies account subscription and actual provider delivery.

## Integration completion record

Record deployed frontend/API origins, frontend build commit, backend build commit, selected Graph API version, callback path, date of physical-device rehearsal and redacted provider message IDs. Never record the access token/app secret.

The integration is complete when an unaided presenter can move between website and phone without editing the database, invoking terminal scripts or replacing messages with fixtures. Any remaining missing provider capability is displayed as unavailable rather than silently synthesized.

## Available Phase 4 backend handoff

The site can eventually create runs from its chosen confirmed import IDs, poll scoped jobs/runs, paginate results, load candidate detail and submit explicit review actions through the contracts in 08. A reload recovers run history from GET /runs. Changing context must clear selected imports/results; retain run_id, workspace_id, registration_id and source IDs together rather than combining stale responses.

Show a pending/failed run without invented totals. Render known tax subtotals with their unknown-row counts and separate credit-note exposure. Display provenance and source hashes/adapters on detail. Scores are formatted similarity strings, and candidate IDs differ from portal-document IDs. Disable a review if the run is historical or sources_current is false; refresh after STALE_VERSION/ASSIGNMENT_CONFLICT and rely on the server decision.

Create/review retries reuse the same UUID key for the same intended command. Idempotency replays the original committed response, so GET current run/result afterward. A newly intended rerun gets a fresh key. Poll about every two seconds with backoff; rapid polling would exhaust the default 60 reads/minute. No WhatsApp webhook, link, send, report or frontend implementation was introduced in Phase 4.

## Phase 5 website-facing flow

Use the same cookie session, credentials:include, exact Origin and in-memory X-CSRF-Token as imports/review. Every mutation sends a UUID Idempotency-Key. Fetch the selected result before creating a case, including its result ID and stable purchase document ID. Add kind-specific facts and observation events with expected_version; show missing_facts and explicit transition actions.

For a proposal, send expected_run_version, expected_result_versions, matching balance_observations and allocations. Display remaining_balance, evidence case/version, source provenance and PROPOSAL_ONLY. Approval is a separate reasoned command. Refresh detail on 409; never retry a changed payload with the previous request UUID. Effective STALE blocks approval/export.

POST /artifacts returns 202 and job_id. Poll the existing scoped jobs endpoint or artifact detail until READY/FAILED/EXPIRED. Download only through the authenticated artifact URL; no public blob/static path exists. For historical PDFs/error CSV, require a visible explicit choice using historical=true; stale proposal CSV is always denied. Content-Disposition and X-GSTShield-Historical are exposed through exact-origin CORS. Downloads are no-store attachments.

Phase 5 workflow timestamp fields are UTC Unix seconds (created_at, updated_at, expires_at), whereas earlier typed run/import timestamp responses use ISO strings. Normalize deliberately in the eventual website adapter. Monetary inputs/outputs are decimal strings, never JS floating-point authority. All endpoint schemas are in the local OpenAPI document. WhatsApp capabilities, callbacks, messages and linking remain deferred to Phase 13.


## Business action screen and channel handoff

Phase 6 first implements the local six-problem workflows. Phase 8 must provide a work queue and invoice/case details showing reason, missing evidence, next review date, supplier draft/history and reviewed outcome; Phase 9 connects them to actual APIs. Distinguish newly observed invoice presence, suggested reclaim review, actual recorded filing and closed business action. Never show a draft or PDF download as successful tax recovery or notice submission.

Phase 13 connects WhatsApp to these existing actions. A supplier draft requires deliberately provided recipient details and consent/verified-recipient checks before a real send. Keep prepared, attempted, provider-acknowledged, delivered, failed and uncertain states truthful; retries must not blindly duplicate an uncertain send. No working supplier-send UI is implied before that integration passes its real-phone gate. Phase 14 rehearses the six problem scenarios through the real website and enabled channel.


Current scope/status is reconciled in the [capability ledger in 05](05_BUILD_AND_VERIFICATION_PLAN.md#capability-status-and-remaining-work-ledger). Phase 6 now has local business-action APIs, automatic deduplicated evidence-change and due-review tracking, private follow-up drafts/history, a review worksheet and separately evidenced user-recorded filing/submission observations. Browser presentation/connection remains 8–9 and conditional WhatsApp delivery remains 13. Automatic fetching, government filing and legal decision integrations are deferred; guaranteed recovery is not a software promise.


## Phase 6 screen and channel handoff

The backend operations and connected internal website now exist through Phases 8–9; the separately supplied landing page/design remains later work. Use one credentialed API client against the live OpenAPI and the exact models in 08. Display recorded GST needing attention, missing facts, provenance, source freshness and the local processing status separately from legally recoverable money. A pending derivation/error cannot be displayed as an empty all-clear queue.

| Website flow | Shared backend authority | Required UI behavior |
|---|---|---|
| Outstanding work / recorded dates | GET actions, state and due_only filters, UUID cursor | Bound pages to 20, show pending checks/errors and stale history |
| Invoice correction / source changes | Existing run/result/import APIs plus action source/timeline | Keep retained purchase identity; display old/new evidence without automatic eligibility |
| Owner and review date | POST action update | Submit expected version, explicit nullable fields, reason and idempotency key |
| Supplier request | POST followups DRAFT | Display private draft and NOT_SENT; deliberate contact, no implicit sending |
| Operator contact attempt | POST followups ATTEMPT_RECORDED | Require same action draft/contact/request plus observed date; show unverified user report |
| Payment / reversal / IRN / notice evidence | Existing case/evidence API plus linked action | Preserve unknowns, matching evidence references and separate operational/legal states |
| Review decision / recorded submission | POST outcomes, then explicit update CLOSED | Distinguish accepted review from dated user observation and external verification |
| Reclaim review handoff | GET worksheet and private PDFs | Label not a filed return; downloading changes no payment/submission status |

New writes require the same cookie, Origin/CSRF, live OWNER/REVIEWER role and UUID idempotency key as existing workflows. Handle 409 by fetching fresh state; replaying a receipt is not a fresh status read. An update is a complete command: omitted nullable assignment/date defaults clear them. Retain values deliberately when only changing state. VIEWER is read-only; frontend hiding is not backend authorization.

Phase 13 must adapt to these same action IDs, drafts, versions and audit history. It must add recipient consent/linking, provider credentials, reachable callback, account/window/template/budget proof and a bounded outbox before sending. Phase 6 has no phone send endpoint and no delivery acknowledgement. Future provider events must remain separate from USER_REPORTED_ATTEMPT_UNVERIFIED and from invoice correction or legal recovery.

## Internal website completed in Phases 8–9

The new frontend is a React/Vite/TypeScript internal application. The user's separately supplied landing page/design is still later work. There is no product mock fallback. All six sections use shared private backend sessions and workspace/registration/month context:

| Website section | Real operations and persisted truth |
|---|---|
| Private access/context | Login/session/logout, live permitted workspaces/registrations, role label, selected accounting month, safe refresh preference |
| Sources | Scoped paged sources, bounded multipart upload, live job/preview/errors, derived column mapping/sheet choice, explicit partial-row and replacement confirmation |
| Reconciliation | Confirmed purchase/2B pair, durable processing, current/historical run, paged/filterable results, eligible candidate/rejection review, reload conflict and refreshed exact GST totals |
| Cases/evidence | Five case kinds, typed fact inputs/unknowns, supported dated observations and confirmed sources, support selection, guarded reasoned transitions and evidence history |
| Work queue | Scoped state/due pages, automation-pending/error coverage, current source/facts, private NOT_SENT supplier drafts, user-reported attempts, reviewer assignment/date/state, recorded outcomes and not-filed worksheet |
| Payment drafts | Paged accepted invoices/reviewed cases, up to 200 allocations from at most 100 selected invoices, current versions and recorded balances, reasoned approval, stale labels; no payment execution |
| Reports | Discover retained private metadata after navigation/refresh, source-versioned PDF/CSV generation, progress/error/expiry, bounded authenticated download, explicit historical evidence opt-in and owner-only expired-content cleanup |

The full six business journeys use actual HTTP/cookies/private storage in browser tests. Separate empty-screen mocks are test fixtures only. Active jobs poll while visible and stop at terminal state; queue checks refresh every 10 seconds while visible, leaving the local backend monitor authoritative for reminders. Restart tests retain the original private SQLite file and recorded history. Website .env.example contains only the public API origin; secrets stay in the backend/private operator setup.

Real WhatsApp delivery is still Phase 13. Draft saving and operator-reported attempts do not send messages. This site does not fetch government data, file returns, transfer payments, guarantee recovery or certify evidence/legal entitlement.


## Phase 12 connected website behavior — 2026-10-04

Same-client/session/URL refreshes keep loaded content and same-version drafts visible with refreshing feedback; affected save/approval/download controls wait for refreshed versions. A new workspace, registration, month, role or session still clears obsolete scope, and access denial clears private content. Processing reads use one parent-driven status schedule with two-to-five-second delays; hidden tabs pause timers. History and match candidates render in batches of 20 with all retained records reachable. Named table regions, heading focus and a skip link support keyboard and small-screen use.

The final 22 browser checks include all six real business journeys; built-preview checks and 100/2,000-row real workflows also pass. No sample-response fallback, API contract change or automatic mutation retry is added. Physical-device/provider verification and real WhatsApp remain Phase 13; whole-application rehearsal remains Phase 14. Landing-page design is still supplied later.


## Phase 13 implemented local exchange — 2026-10-04

The internal website now has a seventh WhatsApp section: masked link/context, one-use code, selected registration/month update, explicit reminder opt-in, unlink and delivery history. Work-queue action details have lazy supplier-consent/draft sending controls. No landing redesign is included. Phone commands reuse the actual backend services described in 03; the local fixture tests are not a real WhatsApp deployment.

LINK codes have 12 base32 characters and at most ten minutes; only hashes persist. HELP/STATUS read existing state. UPLOAD PURCHASE/2B reserves one document intent; CSV or correctly typed XLSX enters normal parsing and awaits website confirmation. RUN requires unambiguous confirmed sources. REPORT uses existing PDFs with a ten-minute, maximum-three-download bearer capability. UNLINK revokes the buyer link. CONSENT verifies the exact saved supplier draft/contact without giving account access; STOP revokes supplier outreach consent separately.

Signed POST callbacks and subscription GET use `/webhooks/whatsapp`. Report links use `/wa/reports/{token}`. An approved forwarder must restrict those paths, preserve the configured Host and avoid token/query logging; changing Host to localhost defeats the extra channel Host restriction. Never expose all browser/auth/business routes through a tunnel. No forwarder was provisioned.

Default sending is zero. Free-form send checks the current 24-hour inbound window, consent/live role/context/source and budget immediately before reservation/transmission. No approved template/out-of-window outreach is implemented. Provider accepted/delivered/read/unknown remain separate; revocation cannot recall already in-flight messages. Pending Meta setup and the unresolved browser/full-suite checks are listed in 05.

Research references: [Meta webhook signature sample](https://github.com/fbsamples/whatsapp-api-examples/blob/main/signature-validation-with-webhooks-payloads/app.py), [Meta-owned Cloud API collection](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api), [Meta pricing](https://whatsappbusiness.com/products/platform-pricing/). These do not prove this account's entitlement, current Graph version or physical media format. Validate those during provider setup.
