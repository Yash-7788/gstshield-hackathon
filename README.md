# GSTShield

Latest usability/access correction (8 October 2026): one assigned role per teammate, owner oversight, progressive OCR invoice/proof review and monthly GST reuse. See [the simple role guide and input inventory](demo/ROLE_SIMPLIFIED_GUIDE.md) and [dated verification ledger](md/13_ROLE_AND_INPUT_SIMPLIFICATION.md). The older acceptance notes below describe earlier checkpoints.

> Current local acceptance: six pillars are implemented and verified for the hackathon scope. The workspace now uses saturated floral canvases, book tabs and role-specific ledgers; see the dated corrective UI acceptance below the earlier visual notes. See [final role acceptance](md/12_ROLE_WORKSPACE_UI_PLAN.md) for exact full-run/retry results and limits, and [demo logins and walkthrough](demo/ROLE_DEMO_GUIDE.md). The supplied landing design is integrated at `/landing.html`.


Hackathon website with a local FastAPI backend, private SQLite storage, React workspace and the supplied HTML landing. Owner/team entry, scoped assistants and shared invoice processes extend the existing imports, reconciliation, cases, payment drafts and reports. Local WhatsApp groundwork is implemented; external delivery requires configured providers. See [frontend setup](frontend/README.md) and [backend setup](backend/README.md).

## Start here

Read [Product and Demo](md/01_PRODUCT_AND_DEMO.md) for the scope and document map.

## Implementation planning

1. [Product and Demo](md/01_PRODUCT_AND_DEMO.md)
2. [Tech Stack and Deployment](md/02_TECH_STACK_AND_DEPLOYMENT.md)
3. [Backend and Data Specification](md/03_BACKEND_AND_DATA_SPEC.md)
4. [Website and WhatsApp Integration](md/04_WEBSITE_AND_WHATSAPP_INTEGRATION.md)
5. [Build and Verification Plan](md/05_BUILD_AND_VERIFICATION_PLAN.md)
6. [Security and Privacy](md/06_SECURITY_AND_PRIVACY.md)
7. [Rules and Integration Truth](md/07_RULES_AND_INTEGRATION_TRUTH.md)
8. [Contracts and Alignment](md/08_CONTRACTS_AND_ALIGNMENT.md)

## Foundation documents

- [Original GST report](md/GST_ITC_SHIELD_REPORT.md): original product hypothesis; read together with the review.
- [GST report review](md/GST_ITC_SHIELD_REVIEW.md): corrections, reproduced prototype defects, and evidence boundaries.
- [Engineering headstart](md/ENGINEERING_HEADSTART.md): transferable lessons from Jainune, with verification limits.

The original report is historical context, not the final implementation authority. The planning pack defines the bounded hackathon build. The local Phase 1 dependencies are resolved in backend/uv.lock. Later feature dependencies and any actual WhatsApp account setup are verified in their own phases.

## Collaboration

Use branches and pull requests for implementation changes. Update shared contracts, schema, adapters and verification together. Keep credentials, private taxpayer documents and real financial data out of commits. Collaborator invitations are managed separately through GitHub access settings.

## Full application phases

The expanded plan has **14 phases** with separate backend, frontend, security, connection and performance work. Phases 1–12 are complete and locally verified. Phase 11 passed 343 backend tests (1 Windows privilege-related skip), the full local load gate and website checks. Dated evidence is in 05. Phase 13 is a local work-in-progress checkpoint; provider/regression verification remains pending. Phase 14 has not started.

1. Local backend foundation.
2. Local storage and private access.
3. File imports, checking and confirmation.
4. Reconciliation and human review.
5. Backend reports, cases and evidence workflow.
6. Business workflows for all six original problems.
7. Backend security and failure review.
8. Internal frontend inspection, cleanup and complete screens.
9. Frontend/backend connection.
10. Frontend security and privacy review.
11. Backend performance and resource efficiency.
12. Frontend smoothness, speed and usability.
13. WhatsApp connection and channel review.
14. Whole-application regression and hackathon rehearsal.

The [build plan](md/05_BUILD_AND_VERIFICATION_PLAN.md) contains each phase's detailed tasks and review gates. The internal React website is implemented; the separately supplied landing page/design will be integrated later. Basic security and responsiveness apply during feature work; focused review phases do not defer them.

## Active first-demo scope

Run GSTShield on the local PC; no cloud server or external database. Phase 1 provides local HTTP/configuration. Phase 2 stores identities, sessions and workspace context in a local SQLite file. See [backend setup](backend/README.md) and the [phased implementation plan](md/05_BUILD_AND_VERIFICATION_PLAN.md). All eight active specifications now use the local architecture. The three original foundation documents remain historical context.

```text
gstshield/
  md/                         # eight specifications and three foundations
  backend/
    app/                      # API, contracts, domain, services, adapters,
                              # storage, jobs and security packages
    tests/                    # unit, integration and synthetic fixtures
    pyproject.toml            # runtime and development dependencies
    .env.example
  frontend/                   # connected internal React website
```

Run instructions and phase status are in [backend/README.md](backend/README.md). SQLite/private access is implemented in Phase 2. Private GST import/preview/confirmation endpoints are implemented in Phase 3. Reconciliation, saved runs/results and human review are implemented in Phase 4. Phase 5 cases, proposals and private reports are implemented. Phase 6 business automation is complete and locally verified; frontend wiring is delivered by Phases 8–9; WhatsApp remains Phase 13.


## Business workflow roadmap correction

Phase 6 implements the six local business workflows through retained actions, supplier follow-up drafts/history, snapshot-change review, reversal/reclaim tracking, recorded-date reminders and notice/IRN tasks. Its local completion gate passed; the measured full-suite and final focused verification record is in 05. The internal screens/connection are delivered by Phases 8–9. Real WhatsApp remains Phase 13, combined acceptance Phase 14, and focused security/performance Phases 10–12.

## Website connection verification

Phases 7–9 are complete: backend security checks, internal workspace screens and actual browser/API workflows. Full backend regression passed 314 tests (1 platform-privilege skip); eight browser tests, six API-client tests and the built-preview CSP upload/confirmation test passed. [Build plan](md/05_BUILD_AND_VERIFICATION_PLAN.md) records scope, evidence and remaining phases. Start the website from frontend with `pnpm dev` alongside the local backend. Landing-page design and real WhatsApp remain later work.

Phase 10 adds denied-access screen clearing, role refresh, obsolete-response/download cancellation, strict API paths/UUID lookup and explicit public configuration. Verification: 10 client/config checks, 14 browser checks, 2 built-preview checks and 25 targeted backend checks passed. [The phase plan](md/05_BUILD_AND_VERIFICATION_PLAN.md#phase-10-completion-and-verification--2026-10-04) records their scope and limits.


## Backend performance verification

Phase 11 fixes repeated invoice normalization, workspace-indexed source lookups, duplicate
catch-up work, long matching read locks and oversized duplicated PDF history. Exact matching
results are unchanged; no dependency or database migration was added. On the recorded PC,
dense domain matching changed from about 36 seconds to 4.7 seconds; normal 2,000-row HTTP runs
complete in 1.5–1.8 seconds. Repeated reports and all expected retained actions pass.

Full regression: **343 passed, 1 Windows privilege-related skip**; 14 browser, 2 built-preview
and 10 client/config checks pass. See [Phase 11 evidence](md/05_BUILD_AND_VERIFICATION_PLAN.md#phase-11-completion-and-measured-verification--2026-10-04)
and [reusable synthetic benchmark](backend/benchmarks/README.md). The default 64 MiB DB/history
caps remain: maximum/repeated stress datasets consume storage faster than the 100-row demo.
The following Phase 12 review is complete; real WhatsApp/design remain later work.


## Website smoothness verification

Phase 12 preserves forms and filters during same-context refresh, reduces redundant processing polls, pauses hidden-tab polling and renders history/candidates in batches of 20. It improves keyboard focus and small-screen table scrolling without changing backend contracts or dependencies. Verification: **22 browser checks, 11 client/config checks, two built-preview checks and six backend website-contract checks passed**. Actual 100/2,000-row workflows pass all local performance budgets; startup/navigation stay broadly similar. [Dated evidence and limits](md/05_BUILD_AND_VERIFICATION_PLAN.md#phase-12-completion-and-measured-verification---2026-10-04) and [repeatable measurements](frontend/benchmarks/README.md) are recorded. Phases 13–14 remain pending.


## Phase 13 checkpoint — 2026-10-04

Local WhatsApp commands, signed callbacks, durable inbox/outbox, supplier consent and website controls are implemented. **This is a work-in-progress checkpoint, not completed Phase 13 acceptance.** Meta setup/HTTPS callback/physical-phone proof remain pending. Default WHATSAPP_ENABLED=false and send budget zero; no real messages or tunnel were created. Existing storage now needs an explicit offline, validated/backed-up `python -m app.manage storage-upgrade` from backend/ to reach schema 6. Never delete the old database; the presenter store was not changed here.

The initial channel/provider set passed 29 tests; the final added ambiguity check passed separately. Browser run: 24 passed, one blank-page failure before login; follow-up startup also failed. Full regression was stopped at the user's request and must not be claimed as passed. See [the build plan](md/05_BUILD_AND_VERIFICATION_PLAN.md) for exact scope, remaining checks and physical acceptance (use ../md/ from component folders). Git checkpoint skips CI to respect the request not to run regression now.


## Six-pillar local product extension: 7 October 2026

This section supersedes earlier roadmap statements about the owner/team portals. The code now includes six pillars. Acceptance is tracked in `md/11_FIVE_PILLARS_IMPLEMENTATION_PLAN.md`; a passing focused check is not a full regression pass.

1. Financial guidance: plain-language glossary, five saved-fact digital staff views, daily priorities, invoice checklist and supported purchase-register / GSTR-2B-file onboarding.
2. Invoice review: existing OCR, item-level four-way checks, Passport, payment gate, supplier follow-up, reports and evidence; six cited review signals and a competitor table with unverified cells explicitly left open.
3. Scoped assistants: CFO, CMA, CMO, CA, CEO, COO and CTO use their permitted saved facts. AI explanation is optional and does not decide money or eligibility.
4. Shared process: ten sequential invoice/batch steps, assignments, due dates, handoff notes, local notifications and audited completion. Changed evidence reopens affected work and makes old approvals/reviews stale.
5. Legal tax review: deterministic cited suggestions, known amount ranges or UNKNOWN, missing facts and explicit CA review. Nothing is filed. No guaranteed savings or loan approval.
6. Owner/team portals: landing sign-in choices, approved-role selection, monthly business/workforce inputs, private individual salaries, repeated-role account creation, role changes, shared work updates and official scheme directories.

### Run and use

Stop the backend before upgrading an existing store. From `backend`, run `python -m app.manage storage-upgrade`, then the supported `python -m app` launcher. The upgrade validates old storage and preserves a backup before adding schema 8 tables. Start the frontend as documented in its README. Open `/landing.html` for the brand page and sign-in choice; `/` opens the workspace.

Owners enter known monthly business figures and create team accounts. Team members choose only roles the owner assigned. CA reviewers start with Invoice desk, confirm extraction, add order/delivery facts and a downloaded statement, then review findings and decisions. Shared process exposes the checked handoffs. Another CA in that workspace sees the same progress. A role picker does not grant access.

### Supported new source formats

The five-column purchase CSV uses GSTIN, invoice number, date, taxable value and tax. Selecting it declares invoice-only rows with no additional charges or rounding. The reported total tax is preserved; its component split stays unknown. It cannot silently become a fully verified exact match.

Downloaded GSTR-2B JSON supports the documented B2B invoice shapes under `data.docdata.b2b` or `docdata.b2b`. Its recipient GSTIN and month must match the selected context. The parser preserves decimal amounts. Non-empty unsupported categories are rejected rather than dropped. Availability restrictions are flagged for review. CSV/XLSX mapping remains available for other supported exports. This is file import, not live government fetching.

### Boundaries

Bank release and sample GST fetching remain simulations. There is no real escrow, bank transfer or GST-portal submission. IMS actions remain NOT_SUBMITTED and notice responses remain drafts for review. A format-valid IRN is not government authentication. Supplier promises do not establish a correction; the saved evidence must pass a recheck.

The scheme directory links PMMY and CGTMSE to official sources; eligibility and interest depend on verified facts and lenders. Legacy 43B(h) references are review-only pending current-period mapping. A controlled payment is not automatically a legal tax-saving strategy. Unknown figures remain unknown. Configured local account, storage and history limits still apply.
