# GST-Shield / VoucherLock — deep report review

Reviewed 2026-10-02. Input: `C:\Users\yashk\Downloads\GST_ITC_SHIELD_REPORT.md`, 545 lines, 43,831 bytes. This is an independent project. The original report and Jainune source were not edited for this task.

## Assessment

The report proposes a useful operational workflow: connect purchase-register reconciliation, supplier remediation, payment-risk review, reversal/reclaim tracking and supporting evidence. That workflow is a plausible product hypothesis. The document is a pitch and demo blueprint, not yet a validated legal specification or production architecture. Its strongest claims depend on assumptions that the included code neither models nor verifies.

The most consequential unproven assumption is that paying the invoice base and moving GST into a buyer-controlled account satisfies all supplier-payment obligations. Separately, matching an invoice in GSTR-2B is not equivalent to proving every ITC eligibility condition, and a valid-looking IRN is not proof of government registration. These distinctions affect the central payment automation design.

## Legal and data claims checked against primary sources

### 1. Payment splitting is not an established compliance safe harbour

The MSMED Act distinguishes the agreed payment deadline and the day of acceptance/deemed acceptance. Section 15 caps an agreed period at 45 days from that acceptance; section 16 addresses delayed-payment interest. The report simplifies this to invoice date and treats 45 days as a universal default. It also conflates expense-deduction timing with a fixed 30% penalty. Historical section 43B(h) concerns deduction on actual payment for sums payable to micro/small enterprises beyond the relevant time limit; that is not a universal fixed penalty.

The cited materials do not establish the report's base-only settlement guarantee. A transfer to another buyer-controlled account does not itself demonstrate payment to the supplier or constitute a legally established third-party escrow. The report needs a specific, reviewed analysis of contractual amounts due, GST accounting treatment, supplier classification, applicable period and disputed/accepted supplies before it labels a split compliant. The absence of a deduction for a GST component in one accounting treatment does not by itself prove that commercial/MSMED payment obligations are extinguished.

Sources: [MSMED Act, sections 15–17](https://upload.indiacode.nic.in/showfile?actid=AC_CEN_46_77_00002_200627_1517807324919&filename=msmed_act%2C_2006_scan.pdf&type=notification), [Income Tax Department historical section 43B including clause (h)](https://wmstatic-prd.incometaxindia.gov.in/hi/web/guest/w/section-43b-41).

An omitted GST issue is the buyer's own non-payment reversal exposure under Rule 37. The notification amends that rule to address whole/partial non-payment and proportionate reversal. A design that withholds part of the invoice must evaluate that lifecycle independently from supplier non-filing under Rule 37A. [Notification 26/2022, clauses 5–6](https://gstcouncil.gov.in/sites/default/files/2024-05/ct26-2022.pdf).

### 2. Rule 37A needs a separate, evidenced lifecycle

The notification ties the rule to the corresponding supplier GSTR-3B, September/November cutoffs following the financial year in which the recipient availed the credit, and subsequent supplier filing for re-availment. A newly visible invoice, a generic eligibility flag, or a registration-status lookup does not by itself prove all those facts. Missing first-time ITC and re-availment of previously reversed ITC are different states.

The report describes reclaim solely as a Table 4D(1) entry. GSTN guidance describes reclaim in Table 4A(5) with separate disclosure in 4D(1). The implementation must track the original claim, reversal reason/amount/period, supplier return period, observed evidence, proposed reclaim and actual filed reclaim, so a recommendation cannot silently become a completed claim.

Sources: [Notification 26/2022](https://gstcouncil.gov.in/sites/default/files/2024-05/ct26-2022.pdf), [GSTN reversal/reclaim statement guidance](https://tutorial.gst.gov.in/downloads/news/new_functionalities_compilation_april_2023_march_2024.pdf).

The public endpoint/API access contract asserted in the report remains unverified. Do not design production polling around an undocumented portal route or infer filing/payment evidence from a taxpayer-details response. Verify authorization, documented fields, availability, rate limits and permitted use; represent missing information as unknown rather than compliant.

### 3. Regex validates format, not authenticity

The included validator accepts any 64 hex characters, including `a` repeated 64 times. GSTN-authorized IRP material describes verification using signed JSON or signed QR data, matching buyer/supplier/invoice fields and considering cancellation status. The report also reduces applicability to a boolean turnover flag, omitting effective dates, relevant turnover history and exemptions. [IRP guidance for recipients and verification](https://einvoice6.gst.gov.in/content/how-will-recipients-receive-e-invoices-from-their-suppliers/), [IRP mandate and exemptions](https://einvoice6.gst.gov.in/content/e-invoice-mandate-e-invoicing-changes-exemptions-documents-covered-transactions-and-more/).

### 4. DRC-01C does not mean automatic invoice-issuance shutdown

GSTN describes a mismatch intimation with a Part B response and a restriction on subsequent GSTR-1/IFF filing when the response is not furnished. That differs from the report's claim that failure to resolve the dispute automatically removes the ability to issue customer invoices. A response workflow must distinguish submission from acceptance/resolution. [GSTN DRC-01C functionality guidance](https://tutorial.gst.gov.in/downloads/news/new_functionalities_compilation_april_2023_march_2024.pdf).

A SHA-256 digest can help detect later modification relative to a trusted recorded digest. It does not prove an invoice or underlying transaction genuine, authenticate who supplied it, establish when it existed, or guarantee a legal outcome. A dossier needs evidence provenance, recorded hashes, access/audit history and reviewed legal arguments. The report's universal reliance on Suncraft was not established by a review of the full applicable judgments/orders in this task.

### 5. The rule set needs time and schema versioning

This review occurs after the Income-tax Act, 2025 took effect on 1 April 2026. The Department says earlier tax years continue under the old Act. Historical 43B(h) references can remain relevant to historical data, but must not be the only hardcoded representation for a current product. [Income Tax Department transition guidance](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/objective-and-scope-new-act).

The report's static monthly-snapshot model also omits IMS interactions. Official guidance allows actions and GSTR-2B regeneration before GSTR-3B filing and describes changes in credit-note handling from October 2025. Imported period alone is insufficient: retain snapshot creation time, source/version, filing state and supersession relationships. [GST Council newsletter reproducing GSTN portal updates](https://gstcouncil.gov.in/sites/default/files/2025-11/october_issue.pdf).

## Embedded engine: reproduced behavior

The 195-line embedded Python block parsed and ran in memory with the locally installed RapidFuzz package. These checks used synthetic inputs and did not contact GST, bank or messaging services. The input report was not changed.

| Synthetic case | Observed result | Consequence |
|---|---|---|
| Two purchase records, one matching portal record | Both classified clean; two full payout rows | A portal record can authorize multiple settlements |
| Same supplier/number/value but invoice dates one year apart | Clean match | Cross-year invoice identity is not enforced |
| Empty invoice numbers on both records | Clean match | Missing identities become trusted exact matches |
| Base ₹1,000, GST ₹180, imported gross ₹99,000 | Clean match; CSV pays ₹99,000 | Payout gross is not reconciled to underlying totals |
| Non-MSME purchase absent from portal | Base settlement still labeled MSME; included in MSME released total | `is_msme` does not control the policy |
| Mandatory e-invoice with fabricated `a` × 64 IRN | Passes gate and releases full amount | Format is being treated as verification |
| Negative base/tax on missing invoice | Negative payout rows and negative protected-tax total | Document type and monetary domains are unvalidated |
| Advertised `INV/24-25/0942` versus `INV-942` | Score 70.588%, below 88%; classified missing | The demo's claimed fuzzy resolution does not work with its engine |

Other observations from source:

- `float` represents money; use exact decimal/integer-minor-unit arithmetic with explicit rounding policy.
- GSTIN, invoice date, bank details and configuration ranges have no input validation in these dataclasses.
- Normalization is lossy; delimiter removal can merge distinct document identities. Token sorting after removing all delimiters provides little meaningful token structure.
- No uniqueness assignment consumes portal candidates. No ambiguity class or second-best confidence margin exists. Choosing the first exact match can make results input-order dependent.
- Matching ignores recipient GSTIN, document type, component taxes, gross value, fiscal identity and ITC metadata. Supplier/GSTIN equality itself is unnormalized.
- Duplicate voucher imports, repeated exports and already-paid invoices are not guarded by persistent state or idempotency.
- Exact/fuzzy result arrays are counted but omitted from the returned output, so the proposed drill-down matrix lacks those details.
- The generic eight-column CSV is not verified against a particular bank's current import contract. No amount/account approval snapshot binds the export to approved data.
- A generated CSV is a payment instruction proposal, not evidence that money moved, ITC was secured, or MSME obligations were satisfied. The summary overstates these effects.
- The code contains no FastAPI endpoints, ingestion parsers, database persistence, sentinel, signed-QR verification, WhatsApp integration, evidence vault or legal-dossier generator. Those remain proposed features.

## Architecture required to make the workflow concrete

Keep facts, decisions and money movement separate. Suggested boundaries:

1. **Import/evidence layer:** immutable source files and checksums, tenant/GSTIN/period ownership, schema-version adapters, mapping preview, rejected-row reporting and import idempotency.
2. **Canonical invoice model:** buyer/supplier identity, invoice/document type, date/fiscal period, component taxes, exact amounts, related amendments/credit notes and source provenance.
3. **Reconciliation service:** deterministic unique matches, scored candidate suggestions, ambiguous/unmatched states, explicit human resolution, reproducible rule versions and explanations.
4. **Policy service:** date-effective legal rules, unknown applicability/evidence states, due-date facts, first-time credit eligibility and reversal/reclaim cases. No unconditional legal guarantee from a match.
5. **AP decision service:** payable balance, prior/partial payments, deductions and disputes, approved beneficiary version, maker/checker review and immutable approved instruction snapshots.
6. **Payment adapter:** bank-specific export validation or provider integration, durable idempotency, status reconciliation, authenticated webhooks, cancellation/retry recovery and execution audit.
7. **Durable case/task layer:** supplier follow-up, filing observations, deadline reminders, reversal/reclaim evidence and notice response tracking. Restart must not lose deadlines or repeat payouts.
8. **Evidence vault:** access-controlled documents, provenance and versioned manifests, trustworthy hash records, retention policy and reviewed export/dossier templates.

A reconciliation state machine and a payment state machine should remain distinct. For example, a match can transition to disputed or superseded while payment is already submitted; a new upload must not silently undo or repeat settlement. A third lifecycle handles ITC first claimed, reversed, reclaim proposed and reclaim actually filed. Tenant identity and versioned evidence bind all transitions.

## Security and regression requirements missing from the report

The report specifies almost no production trust model. Before handling business documents or approved payments, define tenant isolation and object ownership, CA-firm delegated access, role/approval separation, secure sessions, encrypted provider credentials, upload and archive expansion limits, parser sandboxing, formula-safe exports, PDF renderer restrictions, secure evidence links and redacted logs. Authenticated callbacks need replay protection and idempotency. A supplier message/button click is untrusted input and cannot substitute for verified filing evidence.

Bank-detail changes are especially consequential: bind each payment approval to a beneficiary version; require reapproval after changes; track execution status separately from generation. Monetary totals and balances need durable constraints and concurrency tests. Batch generation must not select arbitrary client-submitted accounts as trusted beneficiaries.

Initial regressions should cover every reproduced case above, ambiguous equal-score candidates, shuffled import order, repeated imports/exports, partial payments, amendments and credit notes, component-tax mismatch, stale/superseded 2B, unknown provider state, revoked tenant membership, cross-tenant file access, hostile CSV/XLSX/JSON/PDF input and crashes between approval/submission/confirmation. Verify bank integration with documented test environments before calling a file bank-ready.

## Commercial and demo corrections

The stated SAM arithmetic is wrong by approximately 10×: 75 lakh businesses × ₹999 × 12 equals ₹8,991 crore annual revenue; at ₹4,999 it equals ₹44,991 crore, rather than the report's ₹900–₹4,500 crore. Those figures still assume every claimed seat buys; arithmetic does not validate the market size. The 12-lakh CA-firm count, leakage estimate, retention, CAC and conversion assumptions need identified sources. Revenue LTV is not contribution-profit LTV, particularly with commission, included messages, support and provider costs.

Competitor claims are insufficiently evidenced. Tally's current first-party material describes connected reconciliation/IMS capabilities, so the categorical manual-only framing should not be used as established fact. [Tally current banking/accounting feature material](https://tallysolutions.com/tally-prime-banking-accounting/?ad=&strCampaignID=21292).

Zoho integration should distinguish bills from purchase orders; its API explicitly models conversion of purchase orders to bills. Purchase-order retrieval alone does not supply the billed AP ledger. [Zoho Books bills API](https://www.zoho.com/books/api/v3/bills/).

The five-column import template cannot supply all facts required by the demo's payout/IRN/MSME workflow. The missing facts include beneficiary accounts, vendor contacts, acceptance dates, agreement terms, applicability evidence and existing payments. Explicitly collect or integrate them rather than presume they exist in every purchase export.

For an initial demo, show actual reconciliation, ambiguous-match review, evidence-backed risk explanations, a reviewed draft payout proposal and a simulated reversal/reclaim case. Label fixtures and mocks. Remove claims of guaranteed loss prevention, guaranteed legal compliance, autonomous government filing or guaranteed notice dismissal until their prerequisites are substantiated.

## Decisions carried forward

- Treat this as an independent new project; no code is being added to Jainune.
- Retain the core operational product hypothesis, but rework legal/data foundations before automating consequential actions.
- Preserve the original report; this review is a separate artifact.
- No GST portal login, taxpayer data access, messaging, bank instruction submission, deployment or production code changes were performed.
- Unverified: actual public API contract, complete GSTR-2B schema/payload examples for the claimed signals, bank template compatibility, competitor feature/pricing coverage, legal outcome guarantees and the full Suncraft applicability argument.
