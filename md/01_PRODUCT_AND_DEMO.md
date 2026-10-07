# GST-Shield — product and hackathon demonstration

> **Active local implementation (2026-10-04):** This is a website with a Python backend running on the PC. Authoritative storage is a private SQLite file under `backend/data/`; accounts are provisioned locally and browser access uses revocable sessions. No external database, hosted identity, cloud storage or application hosting is selected. Phases 1–12 are complete and locally verified. Phase 11 passed the full backend regression (343 passed, 1 Windows privilege-related skip). Phase 12 passed 22 browser checks, built-preview checks and real 100/2,000-row website measurements. See 05 for dated evidence. Phase 13 local WhatsApp integration is implemented with focused checks; Meta setup and physical-phone acceptance remain pending. Phase 14 is not started. Full Phase 13 regression was stopped at the user’s request. The landing page/design is pending. The user authorized a new internal website in Phases 8–9; real WhatsApp remains Phase 13.

Planning baseline: 2026-10-03. Status: Phases 1–6 implemented and locally verified; later capabilities remain specifications until their gates pass. This is an independent GST project. The existing website will be supplied later; preserve its design and adapt its data integration.

## Active whole-application phase scope

The implementation sequence now has 14 phases, owned by [05](05_BUILD_AND_VERIFICATION_PLAN.md). It gives separate attention to backend features/reports/security/performance, internal frontend completeness, real website/backend connection, frontend security/smoothness, WhatsApp and combined rehearsal. Phases 1–12 are implemented and locally verified; Phase 13 has a local implementation with provider acceptance pending; Phase 14 remains ahead. The original product capabilities and evidence boundaries below still apply.

## Read this pack

| Document | Owns |
|---|---|
| [02_TECH_STACK_AND_DEPLOYMENT.md](02_TECH_STACK_AND_DEPLOYMENT.md) | Technology decisions, installed dependencies, local setup and recovery |
| [03_BACKEND_AND_DATA_SPEC.md](03_BACKEND_AND_DATA_SPEC.md) | Persistence, processing, reconciliation and service architecture |
| [04_WEBSITE_AND_WHATSAPP_INTEGRATION.md](04_WEBSITE_AND_WHATSAPP_INTEGRATION.md) | Channel behavior and connection instructions |
| [05_BUILD_AND_VERIFICATION_PLAN.md](05_BUILD_AND_VERIFICATION_PLAN.md) | Build sequence, acceptance checks and demonstration rehearsal |
| [06_SECURITY_AND_PRIVACY.md](06_SECURITY_AND_PRIVACY.md) | Essential security requirements |
| [07_RULES_AND_INTEGRATION_TRUTH.md](07_RULES_AND_INTEGRATION_TRUTH.md) | Legal/data evidence and provider capability boundaries |
| [08_CONTRACTS_AND_ALIGNMENT.md](08_CONTRACTS_AND_ALIGNMENT.md) | Authoritative fields, enums, routes, errors and wire examples |

Read 01, 07 and 02 first; align 03 and 08 before implementing either channel. This pack deliberately contains no LOGICAL_CORRECTNESS.md. Create that later from actual implementation findings and regressions, following the user's instruction.

## Foundations and their authority

The three foundations are [GST_ITC_SHIELD_REPORT.md](GST_ITC_SHIELD_REPORT.md), [GST_ITC_SHIELD_REVIEW.md](GST_ITC_SHIELD_REVIEW.md), and [ENGINEERING_HEADSTART.md](ENGINEERING_HEADSTART.md), included in this directory. The user confirmed that the headstart is the third document. The report supplies product ambition; the review supplies reproduced defects and corrections; the headstart supplies transferable implementation lessons and their limitations. All three were read for this pack.

Jainune supplies engineering lessons: verify provider fit and dependency combinations early; define shared contracts before wiring screens; preserve unknown states; trace work across database, storage and callbacks; prove the foundation through a running local flow. Jainune's application features and early infrastructure choices are not copied here.

## The product we will build

GST-Shield helps a business or accountant compare its purchase register with an uploaded GSTR-2B snapshot, understand discrepancies, coordinate follow-up through WhatsApp, and produce a traceable review pack. The website and WhatsApp are two interfaces to the same persisted workspace.

The strongest demonstration is a real uploaded dataset becoming explainable results, followed by a real WhatsApp message querying those same results. A reviewer can inspect why a record was matched, what evidence is missing, and what changed when a new snapshot arrived.

Use the positioning: **“Reconcile, explain, follow up, and prepare evidence before acting.”** Monetary cards show recorded tax exposure or amounts awaiting review, not money saved merely because a CSV was generated.

## Audience and bounded scope

Primary user: one business owner/accountant working on one GST registration and period at a time. A workspace can contain multiple registrations, but the demonstration uses one selected registration. Secondary user: another invited reviewer. Supplier follow-up is a narrowly scoped message/link, not membership in the buyer's workspace.

The initial dataset target is 100 purchase rows. Hard application limit: 2,000 rows per source, 5 MB per uploaded file, one active processing child globally, with up to five queued/running jobs per workspace. These are chosen project limits, not provider guarantees. Measure performance and lower limits if the local demo PC cannot meet them.

This table describes target behavior, including pending functionality. The [status ledger in 05](05_BUILD_AND_VERIFICATION_PLAN.md#capability-status-and-remaining-work-ledger) separates existing backend features from the remaining workflow/channel work.

| Feature | Hackathon behavior | Completion evidence |
|---|---|---|
| Purchase import | Real CSV/XLSX parsing, column mapping, preview and row errors | A file uploaded through either supported channel persists valid rows |
| Portal snapshot import | Canonical demo JSON; official-file adapter only after fixture validation | Unsupported layout fails visibly; uploaded snapshot metadata remains accessible |
| Reconciliation | Unique exact matches, fuzzy suggestions, ambiguous/missing/mismatch categories | Explanations and counts agree with an independently prepared fixture |
| Review actions | Accept/reject candidate with version checks | Website refresh and WhatsApp summary show the committed decision |
| Payment planning | Reviewed proposal CSV with zero bank execution | Download contains accurate amounts and explicit proposal label |
| MSME timing review | Evidence-based reminder fields; unknown when facts are absent | Missing acceptance/terms data never produces invented compliance |
| Reversal/reclaim case | Real persisted case workflow using clearly marked sample evidence | A new observation proposes review; it never marks a return filed |
| E-invoice check | IRN presence/format and evidence status | Fabricated hexadecimal IRN is never described as authenticated |
| Evidence pack | Real PDF and manifest generated from persisted facts | File hashes, snapshot IDs, unresolved issues and sample labels included |
| WhatsApp companion | Real link, command, upload and reply flow on approved test recipients | Physical phone receives a response from the connected integration |
| Supplier reminder | Draft always; send only through explicitly enabled verified recipient flow | Correct invoice details, opt-in conditions and delivery state |

No government credentials, bank credentials, real escrow, autonomous filings, subscriptions or ERP OAuth are prerequisites. The demonstration can show an illustrative allocation, but cannot call it a legally established safe harbour. Use fixture observations for supplier filing status until a documented authorized integration exists.

## User journeys

### Website

1. Sign in using a pre-created demonstration account. Select workspace, registration and reporting period.
2. Upload purchase file. Choose the sheet and mapping when needed. Review accepted/rejected rows before confirming.
3. Upload portal snapshot. Display recipient, period, source type and generation time. Require confirmation if superseding an earlier snapshot.
4. Start reconciliation. Show a durable job ID and progress; do not manufacture progress percentages.
5. Open result categories. Inspect original numbers, exact amounts, candidate scores and evidence source.
6. Review fuzzy suggestions or investigate missing records. Save a decision with its reason.
7. Prepare a supplier reminder or download a proposal/evidence pack.
8. Link WhatsApp and query the same run from a phone.

### WhatsApp

1. Authenticated website user generates a short-lived linking code and sends `LINK <code>` from their phone.
2. Bot offers concise commands: `HELP`, `STATUS`, `UPLOAD PURCHASE`, `UPLOAD 2B`, `RUN`, `REPORT`, `UNLINK`.
3. User selects the active registration/period on the website; the bot echoes that context before an upload or run.
4. A document becomes an import preview. The bot reports accepted/rejected counts and asks for confirmation where required.
5. `RUN` creates the same reconciliation job as the website. `STATUS` reports persisted job/result state.
6. `REPORT` produces a report and a scoped expiring download capability. No full purchase ledger is dumped into chat.

Natural-language synonyms may map to these commands deterministically. An LLM is optional polish, not a dependency for reconciliation, permission checks or monetary calculations.

## Three-minute demonstration

| Time | Action | What the judges actually see |
|---|---|---|
| 0:00–0:25 | Explain the operational problem | One concrete invoice and missing evidence, without unsupported market claims |
| 0:25–1:05 | Upload 100-row purchase and portal fixtures | Genuine parsing, category counts and rupee totals |
| 1:05–1:40 | Inspect and accept one fuzzy suggestion | Original numbers, explanation, unique assignment and updated state |
| 1:40–2:15 | Send `STATUS` from a linked phone | Live WhatsApp response referencing the same run |
| 2:15–2:40 | Open a reversal/reclaim sample case | Source evidence and proposed next action; conspicuous sample status |
| 2:40–3:00 | Download evidence/proposal | Working artifact with provenance, limitations and no execution claim |

Do not force the original 84/8/8 distribution into the engine. The fixture designer must establish expected categories first and the engine must reproduce them. Use an easier confirmed typo example if the original `INV/24-25/0942` versus `INV-942` cannot meet the actual scoring policy. Never change thresholds solely to make one staged example pass.

## Quality bar and priorities

Must ship: working import, persistent reconciliation, transparent review, six-problem action tracking and local reminders, aligned website/WhatsApp access, private artifacts, local restart/backup persistence, and a rehearsed demo. The Phase 5 case timeline, useful PDF and proposal CSV are delivered foundations; the supplier reminder draft is now required in Phase 6. Conditional: real supplier sending and scheduled WhatsApp alerts after account/recipient/window/template/budget prerequisites pass in Phase 13. Stretch: signed e-invoice verification, richer natural-language explanations, validated additional portal tables.

The architecture stays small: one backend, one database, one file store, one durable job mechanism. Security must protect accounts, documents and callbacks, but the hackathon does not need enterprise SSO, Kubernetes, distributed caches or extensive compliance machinery.

Definition of done: a clean checkout can be installed using committed locks; local startup reaches readiness; a real website action creates persisted results; a linked phone sees those results; unauthorized users cannot retrieve them; restarting the backend does not erase imports; demo fixtures produce the expected results.

## Decisions awaiting evidence

The separately supplied landing page/design, real portal sample layout and Meta account/test-number entitlements remain external inputs; the internal website/backend stack and dependency proof are recorded in 02. These do not prevent implementing the deterministic core, but they prevent claims that the complete connected integration is already verified.

## Feature-level product requirements

### P01 — workspace and selected context

The header always shows business, registration and period. A user can change context without mixing results from another registration. The bot repeats context before processing documents.

- Entry condition: authenticated active member.
- Successful action: authorized context selected and persisted for the current channel.
- Invalid state: inaccessible workspace, missing registration or malformed period.
- User recovery: choose an available context; do not silently create a business.
- Acceptance: changing context updates lists, summary and upload targets consistently.

### P02 — purchase upload and mapping

The user must understand which rows entered analysis. Provide a downloadable template and show source columns next to canonical fields. Retain the source filename, hash and sheet name.

- Entry condition: selected registration/period and import permission.
- Successful action: accepted rows confirmed after preview.
- Invalid state: wrong file type, ambiguous dates, duplicate vouchers or unknown mandatory amounts.
- User recovery: correct mapping or download errors and upload a corrected file.
- Acceptance: a row excluded from preview confirmation never contributes to summary totals.

### P03 — snapshot provenance

Show whether data is a synthetic demo, user-provided export, or validated provider observation. A user cannot label an arbitrary upload as authenticated government evidence.

- Entry condition: supported portal adapter and selected recipient.
- Successful action: immutable snapshot persisted with period/generation metadata.
- Invalid state: recipient mismatch, unsupported table, unknown layout.
- User recovery: upload supported data or choose explicit demo mode.
- Acceptance: both report and bot preserve source status and generation time.

### P04 — reconciliation explanation

The result must answer “what differed?” rather than only display a color. Show invoice identity, field differences, match score where applicable and the original source rows.

- Entry condition: two confirmed compatible imports.
- Successful action: one committed result per accepted purchase document.
- Invalid state: unconfirmed import or superseded source context.
- User recovery: confirm/select sources and rerun explicitly.
- Acceptance: no portal row is assigned to two purchase documents.

### P05 — human review

Review is a deliberate action with a reason and a server-confirmed outcome. Similarity alone does not make a discrepancy disappear.

- Entry condition: REVIEWER/OWNER and current result version.
- Successful action: accepted eligible candidate or recorded rejection.
- Invalid state: stale result, conflicting assignment or failed hard gates.
- User recovery: inspect fresh evidence or correct imports.
- Acceptance: the audit timeline identifies actor, prior/new status and reason.

### P06 — supplier follow-up

Produce a clear draft containing invoice reference, requested correction and an appropriate next step. Do not disclose unrelated records or automatically spam every contact found in a spreadsheet.

- Entry condition: selected result and supplier contact deliberately provided.
- Successful action: draft prepared; live send only if enabled and permitted.
- Invalid state: unknown recipient consent, unavailable messaging route or exhausted budget.
- User recovery: copy draft or complete setup; do not imply delivered.
- Acceptance: status separates queued, accepted, delivered, failed and unknown.

### P07 — review cases

Cases organize evidence and next actions without confusing workflow progress with statutory filing. The demo can teach the lifecycle through clearly labeled fixture events.

- Entry condition: selected document and case kind.
- Successful action: facts/evidence recorded and case advanced with reason.
- Invalid state: required observation missing or incompatible evidence context.
- User recovery: attach permitted evidence or keep EVIDENCE_REQUIRED.
- Acceptance: a sample observation never becomes a factual current supplier status.

### P08 — evidence output

Reports must be useful enough to inspect, not decorative dashboard screenshots. Include source references, unresolved issues and what the application actually observed.

- Entry condition: completed run or valid case.
- Successful action: private downloadable PDF/manifest.
- Invalid state: source stale, incomplete generation or denied access.
- User recovery: regenerate from the selected run or sign in.
- Acceptance: PDF monetary values equal persisted results and private access is enforced.

## Product copy and visual semantics

| Use this wording | Meaning |
|---|---|
| Exact match | Fields match the selected source under stated tolerances |
| Suggested match | Similarity candidate awaiting review |
| Missing in snapshot | No acceptable candidate in the selected uploaded data |
| Tax awaiting review | Recorded magnitude associated with specified unresolved categories |
| Evidence incomplete | Required facts are absent/unsupported |
| Proposal exported | A draft instruction artifact was produced |
| Provider accepted | API accepted a send request; delivery remains separate |
| Sample case | Synthetic observations demonstrate the workflow |

Green is reserved for a defined result state, not universal compliance. Yellow represents review; red represents discrepancy or failed validation; grey represents unknown/unsupported evidence. Never make unknown facts green through defaults.

## Hackathon differentiation we can demonstrate

1. One uploaded dataset feeds a usable website and a physical WhatsApp companion.
2. Reconciliation explains unique matches and ambiguity instead of silently trusting fuzzy scores.
3. A later snapshot creates a visible versioned change, preserving earlier evidence.
4. Cases join discrepancy detection to documented follow-up rather than ending at a spreadsheet.
5. Evidence outputs are generated from actual persisted facts with source hashes and sample labels.

These strengths are demonstrable capabilities, not claims that every competitor lacks them. A judge can inspect one difficult record rather than accept a percentage assertion.

## Scope changes and implementation choices

When time is tight, preserve the six-problem Phase 6 tracking/reminder workflow and working upload/reconcile/phone/report loop. Defer only optional integrations such as trusted IRN authentication, direct ERP sync and AI/OCR; do not drop core action tracking under the label optional automation. If the supplied website lacks a needed screen, add the smallest compatible flow rather than a wholesale redesign. If official samples are unavailable, demonstrate the canonical adapter honestly and retain the official adapter as a pending integration.

If the hackathon requires an AI component, add explanation of already computed results with a deterministic fallback. The model receives minimal structured facts and cannot calculate authoritative amounts, select a tenant, authenticate an IRN or authorize a payment. Paid models or OCR must not become mandatory for the core demo.

## Final product acceptance questions

- Can a new demonstration user complete the main flow without terminal intervention?
- Does every button lead to a real backend operation or an explicitly unavailable feature?
- Can a reviewer understand why one invoice is suggested, missing or ambiguous?
- Does the phone interaction use the same persisted run shown on the website?
- Does a repeated upload/action avoid duplicate effects?
- Do missing facts remain visible rather than becoming invented values?
- Can the report be opened and checked against source files?
- Can the presenters state exactly which integrations are live?
- Can the application recover from a restart without losing the demonstration?
- Is every claimed achievement backed by observable behavior?

## Phase 4 demo capability

The backend can now compare two explicitly confirmed imports, save a run, paginate classifications and show candidate explanations. A human can accept an eligible suggestion or reject a match with a recorded reason. Totals update with the committed decision. Demonstrate exact, suggested, amount mismatch, missing, ambiguous and incomplete-evidence rows; do not hide uncertainty or represent suggestions as accepted matches. Historical runs remain readable after reruns; a failed replacement does not wipe earlier findings.

This is a backend capability. The Phase 3 milestone predates the website; Phases 8–9 now supply the connected internal interface. Use documented local API examples or developer docs for backend testing; the current delivered website/PDF scope is recorded in Phases 8–9/05; physical WhatsApp remains pending. No GST filing, bank action, official 2B verification or legal eligibility decision was added.

## Implemented Phase 5 demo path

The backend now supports a real persisted case, evidence timeline, approved allocation draft, reconciliation/evidence PDF, proposal CSV and rejected-row CSV. Use an accepted invoice from a completed current run; record a payment observation in a Rule 37 or MSME case; advance it through evidence review; create and approve a draft; request its report job and download the READY artifact. Export never changes the recorded amount paid. A changed source or case marks the draft STALE and blocks its CSV.

Reports label source provenance and uncertainty. A reconciliation report includes at most 200 chosen/default result rows and says how many of the full run it shows; full run summary totals are preserved. Evidence packs show missing facts instead of inventing compliance. The website UI and physical WhatsApp demonstration remain Phases 8–13, not delivered by this backend phase.


## Six-problem completion ownership (roadmap correction)

The original six problems remain the product target: missing/wrong supplier invoices, MSME/payment risk, forgotten reversal/reclaim review, e-invoice evidence, notice readiness and manual reconciliation/follow-up. Phases 1–5 deliver the local import, matching, review, case and report foundation. Manual case capture alone does not complete these operational workflows.

Phase 6 implements persisted business actions, supplier follow-up drafts/history, cross-snapshot changes, reversal/reclaim review triggers, recorded-date reminders and notice/e-invoice evidence tasks. The detailed six-scenario acceptance matrix is in [05](05_BUILD_AND_VERIFICATION_PLAN.md#phase-6--business-workflow-completion-for-the-six-original-problems-complete). Phases 8–9 now expose and connect them through the internal website; Phase 13 connects real WhatsApp, and Phase 14 demonstrates all six scenarios together. The local backend code is implemented; final verification is recorded in 05. The website has passed real browser journeys; phone delivery and whole-product rehearsal retain their later gates. Evidence-backed review outcomes are distinct from actual legal eligibility, filed returns, executed payments and successful tax recovery.


## Why use this application rather than a one-off AI analysis?

A general chatbot can compare provided data, explain discrepancies and draft a PDF or reminder. An AI system with storage, tools and integrations can also automate workflows; the product must not claim those operations are impossible for AI. GSTShield's intended value is providing a running, repeatable accounting workflow: retained source versions and exact amounts, role-scoped review, remembered unresolved actions, evidence-change tracking, due reminders, follow-up history and connected website/WhatsApp operations. The user need not repaste earlier invoices and reconstruct what was reviewed or chased.

Today the backend retains imports, results, cases, business actions and reports, performs bounded reconciliation on request and runs local evidence/due-review checks while active. It does not send WhatsApp messages. Phase 6 supplies automatic local tasks and reminders; Phases 8–9 make them usable through the website; Phase 13 enables actual channel alerts/follow-up only after integration prerequisites pass. New uploaded evidence or recorded observations are required: the local application cannot know that a supplier filed by itself. The PC/backend must be running to process automatic checks.

Useful automation is: a confirmed run or new evidence changes a tracked issue, the system persists a deduplicated review action, reminds the reviewer when due, and retains what happens next. The reviewer controls consequential decisions. Proposed recovery is separate from recorded actual reclaim. Automatic government filing and guaranteed recovery were excluded by the corrected plan; review worksheets and actual filing-outcome tracking belong to Phase 6. See the canonical [capability status ledger](05_BUILD_AND_VERIFICATION_PLAN.md#capability-status-and-remaining-work-ledger) for every implemented, partial, pending, conditional and excluded capability.
