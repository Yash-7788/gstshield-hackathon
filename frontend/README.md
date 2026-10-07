# GSTShield internal website

Phase 8 supplies the six core workspace sections. The separately supplied landing page and final design remain later work. This is a website in your browser; the API and private SQLite data run on your PC.

## Local setup

Use Node 24.19.0 (tested; Vite requires Node >=22.12 on the supported major) and pnpm 11.19.0. From this folder:

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

Open http://localhost:3000 with the backend at http://localhost:8000. Provision accounts/registrations through backend's offline administration instructions first. Browser and API must use the same hostname; localhost and 127.0.0.1 cannot be mixed. `.env.example` contains the sole public frontend configuration. Omit it to derive the same loopback hostname on port 8000. No backend keys or tax records belong in frontend environment variables.

## Checks

```powershell
pnpm check:contracts
pnpm test
pnpm build
pnpm check:format
pnpm test:browser
pnpm test:preview
```

`generate:api` derives DTOs from actual backend OpenAPI, without starting the backend or reading private data/configuration. Run it after intentional contract changes and commit the generated file. The backend virtual environment must exist. `contracts.ts` is generated and excluded from manual formatting.

Browser tests start an isolated temporary backend on 127.0.0.1:8027 and website on 127.0.0.1:3000. Do not run your real website on that port during these tests. Synthetic alice/bob passwords are test fixtures only; they do not create application defaults or bypass authentication. On Windows installed Chrome is used when available, or set GSTSHIELD_BROWSER_CHANNEL=msedge. Else install Chromium via `pnpm exec playwright install chromium`. Test traces/screenshots are ignored; they may include synthetic business evidence.

## Connected workflow boundary

All six internal sections use the real local API. Saved reports remain discoverable, and registration/month filters execute in SQL before pagination. `journeys.spec.mjs` contains six real journey tests covering the original business workflows, reports, role/context changes, delayed actual replies, server restart, revocation and stale-write recovery. `screens.spec.mjs` separately mocks empty replies to inspect layout/navigation/errors; these fixture tests do not count as connected business operations. The product has no sample-response fallback.

Authentication uses HttpOnly backend cookies, credentials-included requests and in-memory CSRF. Session data is never saved to localStorage. A user-scoped sessionStorage selection stores only workspace/registration IDs and month for refresh; it is cleared on sign-out/expiry and is never access authority. A separate sessionStorage boolean remembers an explicit sign-out even if server sign-out is unavailable; it contains no token or tax data. Lists use bounded pagination, active jobs poll while visible, money remains exact decimal strings, stale sources are labelled, and consequential writes send expected versions plus idempotency keys. An interrupted reply reuses its receipt for an unchanged explicit retry. Downloads validate MIME, enforce the 5 MiB limit and remain within the request deadline/session cancellation boundary.

Payment drafts are not bank transfers, supplier drafts are NOT_SENT, worksheets/reports are not filed returns, and IRN format is not government verification. WhatsApp belongs to Phase 13. Phase 10 completed the frontend security/privacy review for this local scope; Phase 12 completed the connected performance/usability review.

`test:preview` builds the real site against the isolated API and verifies login, upload, parsing, confirmation and sign-out under the preview CSP. Dev and preview remain loopback-only. Core browser tests are a sequential shared-fixture rehearsal; run the whole journey file when exercising persistence and later review gates.


## Frontend privacy review

Phase 10 clears cached data on access denial, removes denied action details and refreshes workspace roles every 15 seconds while visible. Role changes reset private forms. Report downloads are cancelled when leaving their context; late error bodies cannot expire replacement sessions. API pathnames and report ID lookup are restricted, with backend authorization still controlling all operations.

Only VITE_API_BASE_URL is exposed. Automatic public-directory copying is disabled; import reviewed assets from source when integrating the later design. Vite dev serving blocks backend paths, tests, helper scripts, benchmarks and test traces/screenshots. Strict CSP is exercised on the built preview; development retains functional hot reload and the framing denial header. This remains local PC software.

`pnpm test` now includes 11 client/configuration checks. The browser suite has 22 passing tests: six original real journeys, two real security journeys, four explicitly simulated privacy faults, two original screen fixtures and eight usability checks. `test:preview` has two passing checks for the working built flow, content policies and synthetic secret-canary absence. The real and mocked checks are labelled separately. Fixed browser-test ports 3000 and 8027 must be free; test output is ignored and must not be published. Full records and accepted limits are in md/05 and md/06.


## Website performance and usability

Phase 12 keeps same-context/same-version drafts and filters during refresh while disabling affected saves until refreshed versions arrive. Changed context or denied access still clears private data. Long processing polls back off from two to five seconds; hidden tabs pause timers and read errors honor bounded server retry hints. Job detail reads follow parent transitions. History and candidates render 20 at a time with all retained entries accessible; exact negative sub-rupee display is preserved. Tables expose named keyboard-scroll regions and page navigation focuses the main heading.

[Measurement instructions and before/after JSON](benchmarks/README.md) cover actual built-site workflows with 100 and 2,000 invoices against an isolated real backend. All chosen local budgets pass. This is one observation per workload, including automation overhead, rather than a broad speed guarantee. Physical-phone/Safari and WhatsApp provider checks remain later work. Six backend website-contract checks also passed; the 343-test full backend run remains the separate Phase 11 evidence, with combined rehearsal due in Phase 14.


## Phase 13 checkpoint — 2026-10-04

Local WhatsApp commands, signed callbacks, durable inbox/outbox, supplier consent and website controls are implemented. **This is a work-in-progress checkpoint, not completed Phase 13 acceptance.** Meta setup/HTTPS callback/physical-phone proof remain pending. Default WHATSAPP_ENABLED=false and send budget zero; no real messages or tunnel were created. Existing storage now needs an explicit offline, validated/backed-up `python -m app.manage storage-upgrade` from backend/ to reach schema 6. Never delete the old database; the presenter store was not changed here.

The initial channel/provider set passed 29 tests; the final added ambiguity check passed separately. Browser run: 24 passed, one blank-page failure before login; follow-up startup also failed. Full regression was stopped at the user's request and must not be claimed as passed. See [the build plan](../md/05_BUILD_AND_VERIFICATION_PLAN.md) for exact scope, remaining checks and physical acceptance (use ../md/ from component folders). Git checkpoint skips CI to respect the request not to run regression now.
