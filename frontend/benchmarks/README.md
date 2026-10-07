# Connected website performance measurement

This opt-in Playwright workload uses the actual built website, an isolated local FastAPI process, temporary SQLite and synthetic CSV sources. It never reads the presenter's backend .env or private database. Run from frontend/ with the locked dependencies and ports 3000/8027 free.

```powershell
$env:GSTSHIELD_TEST_PREVIEW='1'
$env:GSTSHIELD_TEST_PERFORMANCE='1'
$env:GSTSHIELD_MEASUREMENT_LABEL='after'
node node_modules/@playwright/test/cli.js test
```

For the baseline, set GSTSHIELD_MEASUREMENT_LABEL=before and GSTSHIELD_MEASUREMENT_COMMIT=4ff43fe. The test server reads that committed frontend/src tree and index.html into an ignored test-results directory, then builds it with the same installed runtime, toolchain, configuration and synthetic API origin. It does not revert current files, change dependencies, access GitHub or modify business data.

The profile visits the 100-row demonstration and maximum supported 2,000-row workloads. Invoice strings use SHA-256-derived numbers; 95% are exact and 5% are suggestions. Both source types are uploaded through the real website, parsed, previewed and explicitly confirmed. The website creates the comparison, filters results, accepts one eligible suggestion with a reason, pages and scrolls results, opens a tracked action/history, generates/downloads a private PDF, navigates every section three times, checks a 390px viewport and opens a second authenticated tab. It checks initial summary counts and bounded 20-row rendering. Business journeys separately cover case/payment evidence, submission observations, proposal CSVs, restart and stale conflicts.

Measurements include click-to-next-paint and awaited-UI timings (these include Playwright automation overhead), compiled JS/CSS resource bytes, actual API requests, Chrome long tasks/layout shifts and garbage-collected JS heap before/after repeated navigation. Heap is not total Chrome-process RSS. The two workloads are one observation each, rather than a statistical speed claim. Navigation has 18 observations per workload. API request counts cover the main measured page; the auxiliary tab is checked for real operation but excluded from that page's request counter. Budget limits are local demo margins, not guarantees on arbitrary hardware.

Local budgets: initial login UI <=2 seconds, navigation <=1 second, ordinary measured interaction <=1 second, parsed preview <=6 seconds, matching results <=10 seconds, report readiness <=15 seconds, private download <=3 seconds, and retained JS heap growth <=2 MiB after navigation. Before.json predates automatic budget/hash fields; it is the successful saved baseline, including the observed lost result filter. After.json includes the final source SHA-256, budgets, failures and measurement_passed. Filters must survive review in the optimized build.

The source hash concatenates each sorted src/*.ts, *.tsx and *.css filename, a newline and UTF-8 content normalized to LF. It identifies the application measured, independently of the documentation/benchmark commit. JSON measurements contain only synthetic IDs and evidence. Mobile screenshots remain ignored in benchmarks/screenshots/; baseline build files, browser traces and test-server scratch remain ignored in test-results/. Vite development serving denies benchmarks/** to avoid publishing measurement artifacts.

Usability tests explicitly simulate 100-event histories, 60 candidates, stalled/denied refreshes, active jobs, hidden-tab visibility, Retry-After, filter-response races and mobile keyboard scrolling. Simulated visibility/clock faults are not presented as physical-device or real-provider evidence. Real security/browser journeys and the built-preview content-policy tests remain separate gates.

No new production dependency, backend route, legal calculation, schema, external storage or hosting service is introduced.
