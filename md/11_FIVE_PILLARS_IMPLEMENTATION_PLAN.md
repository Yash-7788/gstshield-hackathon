# GSTShield: Design 2 and five-pillar implementation plan

Current request: 7 October 2026. CMA was clarified by the owner to mean CMO (marketing).

## First deliverable: the final frontend file

Use `GST-Shield (Design 2).html`, not the old v4 reference. Preserve the colours, book, rangoli, sticky sections and interaction style. Save an updated standalone `GST-Shield (Final Frontend).html` in Downloads and a reviewed landing entry in frontend. Keep the existing React workspace and its current privacy controls. Correct wording to the actual feature boundaries: simulated bank, recorded tax under review, explicit review, no live fetching/filing, and reference-format checks. Keep three onboarding steps and the pricing visual; planned paid tiers are clearly labelled rather than implying active billing.

## Pillar 1: guided financial help

Files: `backend/app/domain/knowledge.py`, `backend/app/api/command_center.py`, `frontend/src/GuidedHelp.tsx`, App/CommandCenter styles and integration. Routes: authenticated glossary, role-based saved-fact staff and owner priorities. No new AI authority. Read-only guided checklists use the existing Passport findings, approvals, source signatures and resolution. All private reads retain membership checks. No invented 8-second guarantee or automatic acceptance of ambiguous five-column tax inputs.

## Pillar 2: risk review and truthful comparisons

Files: knowledge rule catalogue, `backend/app/domain/trap_checks.py`, matching/import integration where a supported input adapter is needed, competitor data and table, focused tests. Six review detectors consume saved findings and typed case observations. Legal references link official sources and always say verify with CA. Unknown applicability/timing remains NEEDS_CA_REVIEW. No hard-coded 30% loss, universal invalid-PDF claim or fictional bank escrow. Preserve invoice-number digits/leading zeroes; fuzzy suggestions never become exact. Competitor claims need sources or OWNER_TO_FILL. Existing engines own money and matching.

## Pillar 3: scoped assistants

Files: command-center service/contracts/API and assistant UI. CFO reuses recorded metrics; CEO/COO use only supported invoice/receipt/concentration evidence; CTO reports bounded application facts without exposing secrets; CMO shows missing campaign/sales data rather than fabricated marketing results. Saved facts are returned first. Optional AI explanation requires an explicit request and configuration. Each answer includes facts, amounts, actions, missing data and scope. No independent cost/margin CMA assistant after the owner's clarification.

## Pillar 4: invoice/batch team workflow

Files: `backend/app/storage/process_schema.py`, contracts/services/API for process workflows, `frontend/src/ProcessWorkspace.tsx`. Add an explicit additive schema upgrade after validating/backing up current storage. Tables: workflow_template, workflow_run, node, edge, node_event, assignment. Reuse current invoice/batch identities and source signatures. Sequential exit checks; typed transitions; assignments only to permitted active workspace members; bounded retained nodes/events; scoped reads, versions and idempotency. Downstream work becomes stale/reopens after relevant evidence changes. PROCESS_COMPLETED is an internal reviewed process outcome, not a bank/tax/recovery claim. Notifications are retained local handoff/completion records, not an unconfigured outbound channel.

## Pillar 5: tax-review suggestions

Files: cited deterministic catalogue and suggestion service/UI. Inputs are current invoice/case facts plus explicitly supplied business facts if needed. Return triggered facts, cited rule, missing data, amount range or UNKNOWN, next steps and NEEDS_CA_REVIEW. Unverified law stays disabled/review-only. Split-payment suggestions refer to an internal controlled-payment scenario, not a legal safe harbour or actual escrow. Suggestions never file, approve or invent eligibility. Connect the review to its process node.

## Verification order

Finish and inspect the final frontend first. Then implement one pillar at a time, show focused passing checks and record limits. Reuse existing focused security/version/evidence boundaries. No full regression is implied by a focused pass. Stop/restart only the identified local service when needed; preserve the populated database, use the explicit backed-up schema upgrade, and keep private keys and test artifacts outside Git. Do not push unfinished changes.

## Existing explanation guide

The current explanation file was being expanded when this new frontend/product request arrived. Its completed workflow sections describe the pre-pillar baseline; the missing architecture/reference appendices and the new feature ledger must be finished before describing it as exhaustive. This plan and current source are the implementation authority for the new work.

## Design correction: 7 October 2026

Restore the supplied Design 2 layout, original typography, palette, hero background, cursor rangoli and CTA shapes. Remove the added hero invoice card and global workspace restyling. Update content only to current feature boundaries and affordable proposed pricing. The grey-to-white/yellow/red comparison animation belongs only to the existing Try to fool it demo section, triggered by comparing entered sample records; it is separate from the hero cursor rangoli. No additional landing sections are authorised by this correction.

## Latest design steering: flowing timeline

Use the scroll effects from `GST-Shield · बही-खाता (Design 2).html`: normal scrolling for the demo, pricing and closing section; alternating step cards with intersection reveals; a curved path drawn by scroll position; the ledger pages follow book progress. Keep the existing hero cursor rangoli and grey-to-colour demo in their separate places. Use English current-codebase copy, original CTA shapes with invitation-style wording, Fraunces/DM Sans typography and a restrained cream/teal palette in the existing workspace. No hero invoice card, invented legal certainty, live sync or new product section.


## Latest correction: restore viewport stages, 7 October 2026

The owner superseded the flowing-page change: restore Design 2 pinned full-screen sections, section links that land inside their revealed panels, and Lenis smooth scrolling. Lenis 1.3.26 is pinned locally and embedded in the standalone export; no CDN runtime dependency was added. Shorten the edited headlines. Keep the original homepage cursor rangoli in its own region, right of the copy on desktop and below it on mobile. Remove the blended flower overlay. Preserve the separate grey-to-white/yellow/red comparison animation. Mobile panels retain internal scrolling when their content cannot fit the screen. Desktop/mobile focused navigation, no-overlap, comparison animation, syntax and build checks passed. Pillar implementation and the pitch-deck redesign remain pending; this correction does not mark them complete.


## Screenshot fixes: viewport fit and supplier shuffle

Fixed the reported clipped payment/pricing content and overflowing ledger cover. Keep full-screen stages and local Lenis; long content scrolls inside its panel with a scroll cue, while its illustrated background stays fixed. Compact the laptop payment form, show full goods/tax amounts below the proportional bar, and wrap narrow layouts. Book cover uses two bounded lines; shorter page copy and a normal-flow review stamp fit every face. Restore supplier shuffle alongside a separate comparison button: shuffle changes fictional inputs and restarts the cancellable grey-to-colour animation. Clarify hero and closing copy with the actual invoice/evidence/payment-review/correction workflow; no added live integration claims. Checked desktop, laptop and two phone heights, all book faces, end-of-panel access, actual shuffle/animation and standalone Lenis. Syntax and production build pass; no backend regression run or push performed.


# Active execution plan: five pillars, owner and team portals

7 October 2026. Preserve final Design 2 visuals and the existing React workspace; do not rewrite working services. The latest request lists both CMA and CMO: provide cost/accounting and marketing scopes separately. Login choices and role selections never grant permissions. No fixed four-person or one-person-per-role restriction; configured local account limits still apply.

1. Pillar 1: finish guided help; add owner business form, monthly supplied revenue/profit/cost/tax figures, workforce roles/salaries, owner priorities, secure team creation and repeated roles, shared contributions, and owner/team entry. Employee-level salaries remain owner-only. Existing CFO/CA members receive finance-edit membership; other roles receive shared read-only finance context. Team activity is shared within the same workspace.
2. Pillar 2: reuse existing OCR, item-level matching, Passport, gateway, scoring, anomalies, IMS, reports and channels. Add six trap detectors and typed invoice review facts. Test missing GST, supplier payment timing, reversal/reclaim, required IRN format, actual notice deadline and credit review deadline. Keep unknown explicit. Fuzzy never becomes exact. Competitor cells without verified supporting facts remain OWNER_TO_FILL. No universal 30% penalty, forced 45-day rule, automatic IRN authenticity, tax loss, seven-day blackout or legal escrow claim.
3. Pillar 3: saved-facts CFO, CMA, CMO, CA, CEO, COO and CTO assistants. Include facts used, amounts, actions, missing data and evidence fingerprint. CMO uses supplied marketing facts; CTO reports bounded application/provider facts only. Optional Gemini explanation is explicit and cannot change deterministic results.
4. Pillar 4: invoice/batch process runs with ten sequential nodes, assignments, workload, due dates, handoff notes and cross-role context. A current predecessor and real exit checks are required for completion. Evidence changes reopen affected downstream work. Shared graph in Owner and Team; multiple CAs work on the same records. Every transition is versioned, idempotent and audited. Handoff/completion notifications are local. PROCESS_COMPLETED means reviewed internal work, not a transfer or filing.
5. Pillar 5: deterministic cited tax-review suggestions, ranges or UNKNOWN, recorded deadlines, CA confirmation and stale-review rejection. Owner/team also get an officially sourced government-schemes directory, eligibility facts still needed, dated sources and lender-dependent interest. No guaranteed loan or savings. Review the Income-tax Act 2025 transition before applying legacy 43B(h) references.

## Files, tables and routes

Add storage/product_schema.py, contracts/product.py, services/business.py, services/processes.py, domain/trap_checks.py, domain/tax_guidance.py, domain/assistants.py, API product.py and curated scheme/competitor JSON. Extend main.py, existing Passport audit hook, local.py schema validation/upgrade and guidance integration. One explicit v7-to-v8 additive upgrade validates and backs up existing SQLite first. Tables: business_profile, team_profile, product_events, team_contribution, workflow_template, workflow_run, node, edge, node_event, assignment, process_notification, invoice_review_facts, tax_suggestion_review. Reuse workflow_operations for receipts and existing memberships for authority.

JSON routes under /workspaces/{workspace_id}/product: portal; business; team; team/members; contributions; owner-summary; schemes; competitors; assistants/{role}; invoices/{id}/review-facts and /traps; tax-suggestions and /review; workflows; workflows/{id}/refresh; nodes/{id}/assign and /transition; notifications and /read. All private reads check current membership first; all writes require session/origin/CSRF/idempotency, scope and versions.

Frontend: add product types, OwnerWorkspace, TeamWorkspace, Assistants, ProcessWorkspace and TaxSuggestions; extend App login/navigation using existing ApiClient/Context cancellation. Keep CA invoice/import/reconciliation/case/payment/report screens. Add landing sign-in choice and separate pillars.html explanation entry without changing the design. Rebuild the standalone final HTML after landing changes.

## Verification and completion

Finish one pillar at a time, run focused meaningful checks and record limits. Verify duplicate-role people, no self-promotion, cross-workspace rejection, salary redaction, unknown money, all six traps, two CAs sharing progress, out-of-order rejection, source-change reopening and idempotent completion. At the end run cross-pillar demo, generate API contracts, build website, update README/explanation and seed clearly fictional demo data. Keep original populated storage and private keys. No live external messages and no push unless requested. Pillars 2-5 remain unfinished until their implementation and checks pass.


## Owner correction: six pillars

The owner explicitly separates the additional portal requirements into Pillar 6. Pillar 1 stays financial explanations, digital staff, daily priorities, guided invoices and three-step onboarding. Pillar 6 contains owner/team login choices, approved role selection, business/workforce input, secure repeated-role account formation, shared contributions, consolidated owner/team dashboards and scheme-directory presentation. Pillars 2-5 retain their original scope. The business/team backend foundation and two focused tests already exist; moving its label does not rewrite the implementation. Portal work supports the views of Pillars 1, 3, 4 and 5.

Execution: finish and verify Pillar 1 help screens first, then the Pillar 6 entry/foundation already in progress, followed by the remaining engines and full cross-pillar integration. No pillar is complete merely because its tables or routes exist.


## Acceptance ledger in progress: 7 October 2026

All six pillar engines/screens are written and connected. The original no-redesign landing visuals now include owner/team sign-in choices. The next UI task is explicitly queued until acceptance completes: role-specific workspace design using the final landing DNA, with no duplicate workflows, unclipped layouts or unnecessary elements.

Focused checks passed: owner/team privacy and duplicate-role accounts; all six trap states; schema 7-to-8 data preservation; new five-column/GST JSON parsing and real endpoint/worker confirmation. The cross-pillar correction/completion test passed before the final added batch/two-CA assertions; the complete suite is checking those assertions now. TypeScript, generated API contracts and the production website build passed before final verification-only changes.

The real presenter's database was upgraded offline with backup `cf5552ab-7616-4f34-9363-dc03aac15452`. All 46 legacy business tables and 24 rows match their backup; only schema metadata changed. SQLite integrity and foreign-key checks pass. Details are in output/verification/schema8-upgrade.json.

The first complete browser run exposed hidden empty-help placeholders and tests assuming they owned every purchase in a shared fixture. Help content now mounts only on request; tests identify their own retained file and independent concurrent-review example. The second run passed 29 checks including real owner entry, two CA accounts, shared updates, salary privacy and scoped assistants; one concurrent-review assertion needed its correct canonical field and is being rerun. Do not call that suite entirely green until the retry passes.

Audit changes: new import adapters wired through extension validation; fixed-format remapping rejected; JSON money parsed exactly; role rechecked after optional AI; deadline-based signal changes included in review fingerprints; future recorded events rejected; unknown component tax retained without exact-match promotion; future assignments permitted without activating later steps. Existing provider limits and permissions remain.

Full backend regression and final browser/manual acceptance are pending. No push was performed. Infigraph tools are unavailable in this session; direct search/read fallback was used and this ledger preserves decisions.


### Acceptance update
The full backend run completed with 399 passing, one Windows privilege skip and two failing legacy expectations. Both failures were fixed and verified in an eight-test security/action recheck. The second browser run passed 29 cases and its remaining self-contained concurrent-review case passed separately. Both built-preview/CSP tests now pass. Final affected-flow regressions cover provider permission ordering, post-AI authority and evidence rechecks, and rotating monitor pages so workflows beyond the first 50 do not starve. The Rule 37A review deadline uses the actual recorded claim financial year and September observation, with a CA flag. No UI task2 implementation has started yet.


### Task1 acceptance completed; task2 starts
Final affected regressions: 28 passed. New monitor/date/AI-revocation checks: seven passed. Actual local Chrome inspected 26 desktop/phone sections with no page errors or horizontal overflow; a rapid sweep intentionally hit the 60/minute budget and the subsequent ordinary Today load recovered without alerts. Every previous backend failure has a passing focused recheck; a second entire 16-minute backend run was not repeated. Built preview/CSP passed twice. The standalone final landing now carries the owner/team entry. Role-workspace UI implementation starts only now, under md/12_ROLE_WORKSPACE_UI_PLAN.md. Limits remain simulated bank/GST retrieval, draft-only portal actions, optional configured external channels, and CA verification for legal review.


## Final local acceptance and role UI, 7 October 2026

The six pillars and subsequent role-workspace UI are complete for the local hackathon scope. This dated entry supersedes earlier in-progress notes. The integrated landing is /landing.html; the workspace is /. No commit or push was performed.

The owner sees business figures, private workforce input and short invoice priorities. CA sees invoice/evidence and reconciliation first. CFO sees payment priorities and a financial brief. CMA has a ruled cost sheet; CMO has reported marketing spend and attributed sales; CEO has a business memo; COO has evidence handoffs; CTO has an honest application/integration register. Accounts, warehouse and follow-up have dedicated entry actions. Palettes vary by role while sharing serif titles, readable controls and ledger lines. The role picker only exposes approved roles; it does not grant authority. Owners previewing a role retain their owner permissions, whereas actual team accounts use their own server-enforced permissions.

Closed tax and scheme drawers do not fetch their data. Secondary tools sit under More tools. Account/company/month/role changes reset invoice focus and invalidate previous context. Node update and assignment controls follow permissions returned by the server, which rechecks every write. Relevant changed evidence reopens downstream work and invalidates old decisions.

### Exact verification record

- Complete backend run: 399 passed, one Windows privilege skip, two legacy expectations failed. Both were corrected and passed an eight-test security/action recheck. A second entire backend run was not repeated.
- Final affected backend regression: 28 passed. Additional monitor fairness, deadline and post-AI authority checks: seven passed. Final process/access recheck after UI permission projection: eight passed. These are separate suites, not additive unique-test counts.
- UI browser run: 26 of 31 passed initially. Corrected targeted retries passed all five remaining cases. All 31 cases therefore have passing evidence across the full run and retries, rather than one fresh full green run.
- Client tests: 11 passed. API contract alignment: 132 checked. TypeScript, production build and Ruff passed.
- Final built-preview and browser content-security tests: two passed.
- Actual local Chrome sweep: 30 role/viewport combinations at 1440, 390 and 320 pixels, zero page errors, zero horizontal overflow and zero alerts. See output/verification/final-role-visual.json. Owner and Invoice desk were also captured. Representative owner, CA, CFO, CMA, CMO, CEO, COO and CTO screenshots were visually inspected, including phone CFO/CMO; no clipping or overlapping controls was found in those inspected captures.
- Schema 8 upgrade preserved all 46 original business tables and 24 original rows against the backup. Integrity and foreign keys passed. Afterwards explicitly fictional demo profiles, accounts and a process were added through authenticated routes.

### Limits retained

Local PC storage; simulated bank and GST fetching; no GST portal submission, real escrow or actual bank hold. IMS actions remain NOT_SUBMITTED and notices remain DRAFT_FOR_REVIEW. WhatsApp/email need configured authorized providers; local tests do not prove live delivery. AI integration is configured separately; no fresh live-provider test was made during this final UI run. AI extracts/explains/drafts, and deterministic rules decide matches and payment recommendations. Legal suggestions require CA confirmation. Completion is internal review, not filing, paid money or recovered credit. Unsupported competitor assertions remain OWNER_TO_FILL. Unknown evidence and amounts stay unknown.

### Session narrative

The work first completed the six pillar engines and entry integration, then verified owner privacy, duplicate-role collaboration, reconciliation, evidence-driven payment and ten-node completion/staleness. Full regression found outdated source-replacement and route-inventory expectations, which were corrected with focused security checks. Cross-system review also fixed provider permission ordering, authorization after optional AI, changing deadline fingerprints and monitor fairness beyond 50 records. Original SQLite business rows were compared with the offline backup before the local demo was populated. Only after that acceptance gate did workspace design begin. Role navigation was reduced to primary tasks with supporting tools disclosed separately; closed drawers and duplicate portal requests were removed. Distinct role layouts and palettes were then verified through browser regression, isolated fixture corrections, built CSP preview and actual local Chrome screenshots. The final screenshots show readable mobile/desktop layouts and no measured overflow; the final guide provides fictional demo logins and honest workflow boundaries. No push occurred and no live bank, government or channel approval was fabricated. Infigraph session tools are unavailable, so this dated narrative is the continuity record.
