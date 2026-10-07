# GST-Shield — rules, evidence and integration truth

> **Active local implementation (2026-10-04):** This is a website with a Python backend running on the PC. Authoritative storage is a private SQLite file under `backend/data/`; accounts are provisioned locally and browser access uses revocable sessions. No external database, hosted identity, cloud storage or application hosting is selected. Phases 1–12 are complete and locally verified. Phase 11 passed the full backend regression (343 passed, 1 Windows privilege-related skip). Phase 12 passed 22 browser checks, built-preview checks and real 100/2,000-row website measurements. See 05 for dated evidence. Phase 13 local WhatsApp integration is implemented with focused checks; Meta setup and physical-phone acceptance remain pending. Phase 14 is not started. Full Phase 13 regression was stopped at the user’s request. The landing page/design is pending. The user authorized a new internal website in Phases 8–9; real WhatsApp remains Phase 13.

Baseline 2026-10-03. This document owns factual assumptions and capability labels. It does not provide individualized tax/legal advice. The application presents review findings; professional validation is needed before consequential filing/payment automation.

## Source hierarchy

Original report: product hypothesis and demo ambition. GST review: reproduced engine defects and source-based corrections. ENGINEERING_HEADSTART.md: source-sampled engineering lessons, with explicit limitations. Current official documentation and actual authorized samples: integration truth. Implementation tests: evidence that our code meets a supported contract, not that a legal outcome is guaranteed.

A claim is `VERIFIED_SOURCE`, `PRIOR_REVIEW_SOURCE`, `PROJECT_DECISION`, `SYNTHETIC_DEMO` or `UNVERIFIED`. Record source URL, checked date, applicability period, expected fields and limitations. A inaccessible source is not silently marked freshly verified. Some legal/IRP pages linked in the earlier review could not be fetched again during this planning pass; their observations retain prior-review status.

## Product statements and legal boundaries

| Report claim | Planning rule / resulting implementation |
|---|---|
| Match means ITC secured | Match establishes comparison against one uploaded source; evidence/eligibility are separate |
| Base paid, tax held universally satisfies MSME obligations | Not established. Show optional reviewed allocation proposal without compliance guarantee |
| Missing 2B means permanent loss | Record “missing in selected snapshot”; future amendments, timing and other facts remain relevant |
| 45 days always counted from invoice | Require acceptance/deemed-acceptance facts and agreement evidence; unknown when absent |
| Fixed 30% penalty | Do not calculate/claim a universal penalty from invoice value |
| Any 64-hex IRN is verified | Format only; authenticity requires additional trusted verification |
| New 2B record proves supplier tax paid/reclaim allowed | Cannot infer that from appearance alone; model claim/reversal/filing evidence separately |
| CSV means payment completed | Proposal export only; no money movement occurs |
| SHA-256 dossier guarantees notice dismissal | Hash/provenance supports traceability, not authenticity or legal success |
| Undocumented public endpoint provides authorized filing history | Unsupported until documented access/fields/terms and real payload are verified |

## Date-effective rule facts

The original monthly/section labels cannot be hardcoded as eternal truth. Income Tax Department guidance distinguishes years beginning before 1 April 2026 from the new Act's tax years. Historical fixtures may use historical references; current-year rules require their own verified mapping. [Official transition FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/objective-and-scope-new-act-faq)

For each policy fact store `rule_id`, `rule_version`, `effective_from`, `effective_to`, `source_url`, `checked_at`, `evidence_required`, `applicability` and `provenance`. The current engine persists match-v1 reconciliation settings and evidence facts. No date-effective statutory calculation engine or legal-rule configuration file is implemented; statutory calculations require separate current verification before future implementation.

Rule 37 and Rule 37A represent different exposures. The reviewed notification addresses proportionate non-payment reversal and supplier non-filing, including relevant financial-year cutoffs and later re-availment. A case needs original claim period, reversal amount/period, reason, supplier return period and observation evidence. Do not merge these into one `eligible=true` flag. [Notification 26/2022](https://gstcouncil.gov.in/sites/default/files/2024-05/ct26-2022.pdf)

Earlier GST review links describe reclaim disclosure involving 4A(5) and 4D(1), and DRC-01C response/restriction behavior. Preserve these as reviewed guidance requiring current form/version confirmation before filed-return generation. The hackathon generates a review worksheet, not a ready-filed return. [Prior-review GSTN guidance](https://tutorial.gst.gov.in/downloads/news/new_functionalities_compilation_april_2023_march_2024.pdf)

MSME workflow requires classification evidence, acceptance basis, agreed period, payment observations and dispute facts. Incomplete inputs produce EVIDENCE_REQUIRED. No current tax-year automatic disallowance formula is in scope. [MSMED Act source used in prior review](https://upload.indiacode.nic.in/showfile?actid=AC_CEN_46_77_00002_200627_1517807324919&filename=msmed_act%2C_2006_scan.pdf&type=notification)

IRN has separate states: NOT_PROVIDED, FORMAT_INVALID, FORMAT_ONLY, VERIFIED, VERIFICATION_FAILED, UNKNOWN. VERIFIED remains disabled until a real signed JSON/QR verification adapter, trusted keys and field/cancellation checks are proved. Turnover/applicability is not inferred merely from supplier size or a boolean. [IRP source used in prior review](https://einvoice6.gst.gov.in/content/how-will-recipients-receive-e-invoices-from-their-suppliers/)

## GSTR-2B and IMS evidence

Official GST guidance supports taxpayer post-login JSON/Excel downloads and recommends reconciliation with books, including avoiding duplicate credit. We require user-supplied files, never portal passwords. [GSTN FAQ](https://tutorial.gst.gov.in/userguide/returns/FAQ_gstr2b.htm)

IMS guidance allows recomputation after recipient actions. Thus a reporting period alone cannot identify an immutable final snapshot. Store generation time, import time, source hash, filing-state observation and explicit supersession. [GSTN draft IMS manual](https://tutorial.gst.gov.in/downloads/news/draft_manual_ims.pdf)

The original `schema v1.4` and `itcAvl/itcElg` claims have not been proved with an actual authorized file. Do not create fictitious keys and name them official. Initial `canonical-demo-v1` has our own documented shape. Real adapter activation requires a redacted original with preserved layout and expected row/count/tax totals.

Adapter support is table-specific: B2B invoice first, then amendments/credit/debit notes only after sample validation. ISD/import/RCM and other unsupported sections trigger explicit UNSUPPORTED_SECTION reporting. An unsupported section's tax must not vanish into a clean total. A fixture name `official.json` is not proof of official provenance.

## Integration matrix

| Integration | Initial mode | Prerequisites / unknowns |
|---|---|---|
| Purchase-register upload | Real CSV/XLSX | Actual headers/sheet selection mapped; no universal Tally layout promised |
| GSTR-2B upload | Real parser for supported samples; synthetic canonical fixture immediately | Authorized actual file needed for official adapter claims |
| GST taxpayer/filing lookup | Disabled or fixture observation | Documented permitted API and evidence semantics not verified |
| IMS actions/government filing | Simulated/read-only case state | No login automation or write access |
| Meta WhatsApp | Real test/account integration | App/WABA/phone, recipient permissions, token, callback and billing proof |
| Supplier reminder | Draft first; send conditional | Consent, approved messaging route/window/template and account entitlement |
| Bank export | Generic proposal CSV | Bank-specific verified template absent; no bank-ready claim |
| Bank execution/escrow | Disabled | No provider contract or legally reviewed settlement model |
| Tally/Zoho direct sync | Deferred | Export files suffice; purchase orders are not booked bills |
| IRN verification | Format/evidence review | Signed source and current verification contract required |
| PDF/manifest | Real generation | Facts/provenance only; no automated legal judgment |
| AI/OCR | Optional, disabled by default | Core works without paid services or hallucinated facts |

Meta's official API collection establishes asset/token/request setup, but does not settle all current no-cost account entitlements. Its public pricing page and inaccessible detailed developer pricing prevent a blanket free-messaging promise. Check actual account status/rates at setup and enforce a hard demo budget. [Official API collection](https://www.postman.com/meta/whatsapp-business-platform/collection/wlk6lh4/whatsapp-cloud-api), [Public pricing](https://whatsappbusiness.com/products/platform-pricing/)

## Fixture and evidence design

Use fixed synthetic registration/supplier identifiers labeled non-authoritative. Validate GSTIN format separately from existence. Fix demo clock and reporting period rather than compare historical sample deadlines to the presentation date. Fixture files include `provenance=SYNTHETIC_DEMO`, independently prepared expected totals and deliberate error cases.

Suggested fixtures: 100-row purchase register; matching canonical portal snapshot; later superseding snapshot; case evidence for original claim/reversal/supplier filing observation; malformed import; duplicate portal row; cross-year invoice number; missing components; forged IRN-shaped string. Add a fixture where a legitimate fuzzy suggestion is rejected to show human review and preserved audit history.

Trusted sources are not created by a client-provided `verified=true`. Users may submit observations, but server/source metadata identifies them as USER_PROVIDED or SYNTHETIC_DEMO. A provider adapter can attach VERIFIED_SOURCE only after validation. Supplier chat messages remain unverified observations.

## Claims permitted at judging

Say: “The application parsed these files, detected these discrepancies, persisted review actions, and delivered this summary on WhatsApp.” Say: “This sample case demonstrates how reversal/reclaim review can be tracked.” Say: “The report includes source hashes and an evidence timeline.”

Do not say: “We guarantee no ITC loss,” “this account is legal escrow,” “the supplier definitely paid tax,” “the bank paid this CSV,” “this PDF will dismiss the notice,” or “all competitors lack this capability.” Market/pricing/comparison claims from the report remain separate research, not technical acceptance criteria.

## Unresolved evidence register

Before implementation expands claims: inspect the later supplied landing page/design; obtain a permitted portal file; maintain the tested locked backend combination; verify PC disk/availability budgets; provision and test Meta assets; reconcile detailed messaging pricing; validate any bank format; obtain professional review for current-year statutory calculations. The build can proceed with clearly bounded synthetic adapters while these are resolved.

## Evidence ledger for this planning pass

| Subject | Evidence status | Consequence |
|---|---|---|
| Original GST report | READ | Product ambition retained; claims not automatically adopted |
| GST report review | READ | Reproduced engine defects become targeted regressions |
| ENGINEERING_HEADSTART.md | READ | Server authority, contract and failure-boundary lessons carried forward |
| Local runtime/storage | IMPLEMENTED_AND_TESTED, Phase 2 | PC availability and private SQLite storage replace cloud deployment |
| Local account access | IMPLEMENTED_AND_TESTED, Phase 2 | Operator-created accounts and opaque sessions replace hosted identity |
| Locked backend dependencies | INSTALLED_AND_TESTED, Phase 1 | Actual versions in 02; future parser/report dependencies remain pending |
| GSTN post-login 2B downloads | VERIFIED_SOURCE, FAQ | Parser must prove actual layout support |
| IMS recomputation | VERIFIED_SOURCE, draft guidance | Store immutable snapshots and supersession |
| Rule 37/37A notification | VERIFIED_SOURCE, published notification | Current applicability/form details require reviewed implementation |
| Current-year income-tax transition | VERIFIED_SOURCE, official FAQ | Historical section label not universal current policy |
| MSMED/IRP/form detail sources | PRIOR_REVIEW_SOURCE | Linked pages could not all be freshly retrieved |
| Meta Cloud API collection | VERIFIED_SOURCE, official collection | Real account provisioning not yet proved |
| Detailed current WhatsApp price entitlement | UNVERIFIED | No guaranteed free-messaging assertion |
| Claimed public GST filing API | UNVERIFIED | Do not call it as a required live integration |
| Particular bank upload contract | UNVERIFIED | Generic proposal export only |
| Supplied website implementation | WAITING_INPUT | Framework and deployment decision provisional |

Each later implementation observation records its date/environment. Do not replace UNVERIFIED with VERIFIED_SOURCE merely because a demo fixture has the expected field.

## Policy evidence schema

Use a small schema such as the following for a case observation:

```json
{
  "fact_type": "SUPPLIER_RETURN_OBSERVATION",
  "supplier_gstin": "illustrative-supplier",
  "return_period": "2024-05",
  "observed_state": "UNKNOWN",
  "observed_at": "2026-10-03T00:00:00Z",
  "provenance": "USER_PROVIDED",
  "source_file_id": null,
  "source_url": null,
  "adapter_version": null,
  "reviewed_by": null,
  "note": "No authorized filing evidence has been supplied."
}
```

The server assigns observation provenance based on source path. `observed_state` refers to the documented fact, not a broad compliance conclusion. A source can establish a filing occurrence without proving all financial/tax obligations; record the actual semantics.

## Unknown-state examples

| Missing fact | Correct output | Incorrect shortcut |
|---|---|---|
| MSME classification evidence | Classification unknown; review required | Treat every small supplier as eligible |
| Acceptance date | Deadline evidence incomplete | Use invoice date without explanation |
| Written terms | Agreement facts absent | Assume 45 days universally |
| Original ITC claim | Cannot classify as re-availment case | Call newly visible credit a reclaim |
| Supplier return filing observation | Unknown | Infer paid from registration active |
| IRN authenticity evidence | FORMAT_ONLY or UNKNOWN | Regex success becomes verified |
| Tax component values | COMPONENTS_UNKNOWN | Fill zeroes and call exact match |
| Snapshot generation time | Timestamp unknown; user warning | Use upload time as generation time |
| Bank payment observation | Payment status unobserved | CSV generated means paid |
| Provider delivery receipt | ACCEPTED or UNKNOWN | Successful API request means delivered |

Unknown is a first-class useful outcome. It tells the reviewer what to collect next and prevents the application from promising more than its data supports.

## Official adapter activation protocol

1. Obtain a permitted redacted actual export.
2. Preserve structural keys, source section identifiers and representative value types.
3. Record export origin, format/version if available and anonymization method.
4. Independently count rows and component-tax totals per supported section.
5. Map each official field to the canonical schema explicitly.
6. Identify optional/absent/unsupported sections and amendment relationships.
7. Validate registration, period, date/money types and source generation metadata.
8. Run parser tests with unknown fields and missing mandatory fields.
9. Compare parser output to independent expected totals.
10. Enable that exact adapter version and document its coverage.

An additive unknown metadata field may be preserved/ignored safely; an unknown document table must be reported. Do not reject all future files because of harmless metadata, but do not silently skip financial sections. Adapter versions allow controlled evolution.

## Reversal/reclaim sample design

Create a sample case with explicit original claim, reversal reason/amount/period and a later sample supplier-return observation. Show the progression from EVIDENCE_REQUIRED to REVIEW_READY after sufficient fixture evidence. Explain that the app proposes a review action and has not filed a government return.

The sample cannot model every legal exception. Keep the fixture's applicable historical policy version visible. If the presenter uses a current-year example, first validate the relevant provisions/forms instead of merely changing the year in old text.

## Notice/evidence sample design

Use a synthetic notice reference, a source invoice, purchase evidence observation, payment observation if supplied, and a chronology. The PDF lists included/missing evidence and reviewed factual statements.

Do not automatically attach a legal precedent as a universal dismissal argument. Legal text beyond factual organization is a professional-reviewed template, not generated certainty. A timestamp recorded by our server indicates when it observed bytes, not when the underlying transaction occurred.

## Payment-proposal interpretation

Proposals can demonstrate alternative allocations and document review intent. A buyer-controlled reserve is labeled illustrative; it is not represented as third-party escrow. Known payments reduce the evidenced payable balance, but their source/verification status remains visible.

If no bank-specific template is validated, export our generic columns and label them clearly. A claimed beneficiary account from a supplier message is unverified input; initial public demo should use synthetic beneficiaries or omit bank coordinates.

## Messaging cost validation protocol

- Inspect actual test/registered-number mode.
- Confirm allowed recipients and account eligibility.
- Confirm permitted message type/window for the intended command reply.
- Check detailed current rates/allowances in the account or accessible official documentation.
- Send one controlled message and confirm physical delivery.
- Inspect provider acceptance/delivery status and available billing evidence.
- Record limits/date without secrets.
- Enforce a conservative project budget and disable paid proactive messages by default.

Until these steps succeed, describe ₹0 WhatsApp as a goal/conditional setup, not a completed fact. Website/core functionality can be planned independently from billing uncertainty.

## Document update rules

When source evidence changes, update this document first, then the affected contracts/algorithm/copy/tests. A source correction must propagate to the website, phone response and PDF; changing only pitch text leaves misleading outputs in the product.

When a provider cannot support the chosen free path, record the exact blocker and smallest compatible alternative. Do not silently introduce a paid prerequisite into a zero-cost core. If only a simulation is feasible, retain the feature boundary and label it clearly.

## Future implementation questions to close

- Which actual website framework/build needs to be preserved?
- Which real portal export sections are available for validation?
- Which Meta account assets can the team provision before the deadline?
- Which message types remain within the actual no-cost entitlement?
- Which exact dependency combination installs and runs locally successfully?
- Which evidence facts can the user provide without government API access?
- Is an actual bank-specific artifact required by the hackathon, or is a proposal sufficient?
- Does the hackathon require a separate AI component, and can it remain optional?

These questions are implementation inputs, not an instruction to stop all work. Proceed with the bounded deterministic core while collecting the facts needed for larger claims.

## Phase 4 capability truth

Implemented comparisons use only the selected confirmed source imports and saved server policy. EXACT_MATCH means identity and each supported amount agree within tolerance against that snapshot. FUZZY_SUGGESTION still requires a human decision; REVIEW_ACCEPTED preserves that human distinction. Neither classification proves an invoice is genuine, a supplier filed/paid tax or ITC is legally available. There is no official GST/IRP lookup or filing integration in this phase.

MISSING_IN_SNAPSHOT is limited to the chosen supplied snapshot, not permanent ITC loss. Rejected related snapshot evidence, unknown components, duplicate identities and contested candidates are retained as uncertainty. Known tax exposure is an exact recorded review subtotal, with explicit unknown-row counts. Credit-note magnitudes remain separate. No comparison total is a recoverable/denied ITC determination, payment instruction or debt calculation.

USER_PROVIDED stays user-provided; canonical-demo-v1 stays SYNTHETIC_DEMO through the run and review. Accepting a candidate never promotes provenance to VERIFIED_SOURCE. Source hashes, adapters, context revisions and policy snapshots preserve reproducibility; they are not third-party certification.

## Phase 5 evidence semantics

REVIEW_READY means the selected facts and referenced observations are sufficient for a human workflow review; CLOSED records a human closure. Neither certifies a supplier classification, filing, payment or ITC claim. User-supplied filing observations remain USER_PROVIDED. Synthetic source provenance conservatively propagates into cases/proposals/artifacts and cannot be promoted by request fields.

Rule 37 facts track original claim plus payment observations; Rule 37A facts separately track claim, reversal and supplier return observations. Dates/periods/amounts are validated but no statutory cutoff, interest, tax-year disallowance or return-filing calculation runs automatically. IRN observation is only NOT_PROVIDED, FORMAT_INVALID or FORMAT_ONLY; VERIFIED remains unavailable.

A proposal records invoice gross, observed amount paid, remaining balance and proposed allocations at frozen versions. It may reserve an illustrative amount for internal review, but establishes no escrow, lawful withholding or bank-ready instruction. An exported CSV does not change payment facts. Source hash and report hash establish traceability relative to stored bytes, never government authenticity or legal success.


## Business workflow completion does not imply legal automation

Phase 6 implements tracked actions for the original six problems under these evidence boundaries. It proposes review from recorded claim/reversal/payment facts and uploaded or explicitly recorded observations. An invoice newly present in 2B does not alone establish all credit conditions or a Rule 37A reclaim. Buyer non-payment and supplier non-filing remain separate evidence lifecycles. An IRN format check remains unverified; a notice PDF is a preparation artifact.

Due-review reminders use explicitly recorded, reviewed dates until a verified dated statutory policy with adequate facts is implemented. Do not invent a universal 45-day rule, fixed tax penalty, mandatory seven-day notice response, legally safe split-payment escrow or guaranteed recovery. Keep a suggested action, reviewer decision, recorded submission and observed resolution distinct. Live government access/authenticity verification remains unavailable unless separately validated. The six-scenario gate in 05 tests useful local tracking, not legal certification.


Current scope/status is reconciled in the [capability ledger in 05](05_BUILD_AND_VERIFICATION_PLAN.md#capability-status-and-remaining-work-ledger). Phase 6 now has local business-action APIs, automatic deduplicated evidence-change and due-review tracking, private follow-up drafts/history, a review worksheet and separately evidenced user-recorded filing/submission observations. Browser presentation/connection remains 8–9 and conditional WhatsApp delivery remains 13. Automatic fetching, government filing and legal decision integrations are deferred; guaranteed recovery is not a software promise.


## Phase 13 integration truth — 2026-10-04

Signed callbacks, local phone commands, draft-specific supplier consent/outbox and website controls are implemented locally. The user has no Meta setup yet. No physical message, approved callback, supported account Graph version, token entitlement or billing outcome is verified. Never use earlier example demo wording that says “delivered on WhatsApp” until an actual delivery callback/physical test proves it. Fake transport tests and real local PDFs/imports are distinct evidence.

Recorded reminders do not determine statutory due dates. A supplier message does not establish invoice correction, filing or ITC entitlement. Government fetching/filing, trusted IRN verification, bank execution and guaranteed recovery remain excluded/deferred as already planned. Current local verification gaps and provider gates are recorded in 05.
