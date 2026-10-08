# GSTShield: simple role guide and input inventory

Updated 8 October 2026. This describes the current local implementation, not a live bank or GST portal connection.

## Start with your own role

Choose Business owner or Team member on the sign-in page. Your account has one role assigned by the owner. The login buttons do not give extra permissions.

| Role | Main screens | What the person does |
| --- | --- | --- |
| Business owner | Owner desk, Team desk | Read priorities and progress; manage teammates and one-time business setup. |
| CA | Team desk, Invoice desk, Assistants | Confirm invoices, check supporting files, review GST evidence and tax actions. |
| CFO | Team desk, Invoice desk, Assistants | Review current payment decisions and report cash priorities. |
| CMA | Team desk, Assistants | Understand saved costs and reported business figures. |
| CMO | Team desk, Assistants | Review reported marketing spend and attributed sales. |
| CEO | Team desk, Assistants | Read business priorities and team handoffs. |
| COO | Team desk, Assistants | Identify missing receiving evidence and coordinate handoffs. |
| CTO | Team desk, Assistants | Read configured application connections and their limits. |

Several people can hold the same role. One person cannot be assigned several roles at once. CA and CMA are different roles. A role cannot gain another role's tools through a dropdown or a direct API request.

The detailed Shared process screen is a supporting CA/CFO tool. Other roles use team handoff notes. The owner sees a simpler read-only progress summary.

## What the owner sees

Owner desk shows reported revenue and profit, invoice tax needing review, the reason work is waiting, who is assigned and any recorded due date. Unknown amounts are labelled as unknown or awaiting review. They are not filled with fictional numbers.

Owner desk contains no accounting input forms, invoice confirmations or payment approval controls. The owner can set up the company and team separately. Related review copies appear together in progress; stored evidence is preserved.

Business setup opens with seven basics: business name, type, people count, MSME classification, monthly revenue, profit and operating cost. Only business name is required. Marketing, loan, tax already paid, private salary records and additional notes are optional expandable sections. These are monthly/company facts, not repeated invoice questions.

## The normal CA invoice path

### 1. Read the invoice

Open Invoice desk and upload the supplier's PDF, PNG or JPEG. Maximum 4 MB. Confirm consent if you want Google AI to read it.

The reader proposes printed supplier details, invoice number/date, goods value, tax, total and individual items. It also says what it could not find. Review the populated details and click Confirm details. Correct only a mistake or a missing required fact.

A complete proposal needs no manual retyping. The confirmation requires supplier GST number, invoice number, date, goods value and total. Individual items require a name, positive quantity and goods value. Missing item facts open their correction inputs automatically. Optional item code/unit can remain absent.

### 2. Add the order

The next action asks for the purchase order: what the business agreed to buy. Upload the actual order PDF/photo, allow reading, then confirm the populated facts once.

The system compares individual items and quantities automatically. An order cannot be invented from the invoice because that would make both sides of the check the same source.

### 3. Add the delivery record

The next action asks for the receipt: what actually arrived. Upload the real receiving record and confirm the proposed facts.

A receipt may contain quantities but no prices. Missing prices remain unknown; quantity checks still work. The system does not copy invoice prices into a delivery record to manufacture a match.

### 4. Add the month's GST statement

Upload your accountant's downloaded GSTR-2B JSON, or a supported CSV/XLSX export. Company, month and format are selected automatically. Review the parsed rows once and confirm.

The confirmed selection is reused by invoices in the same company and month. Choosing a new statement updates comparisons and process progress. Older approvals become stale when their evidence changes; they are not silently reapproved.

Nonstandard column names or workbook sheet choices may need a one-time import correction in Sources. Unsupported files are not treated as valid government evidence. Sample fetching is clearly marked as simulation.

### 5. Review the payment

Payment controls open after order/delivery checks and GST evidence are available. Confirm whether a payment has already been made; that fact cannot be read from an unpaid supplier invoice.

Recommended decisions and amounts use saved evidence. A reviewer explicitly chooses full payment, controlled part payment, hold or escalation. If the decision is held, zero release means a deliberate hold, not a missing invoice total.

Bank release tests use a simulated gateway. No real money moves. A stale approval must be reviewed again.

### 6. Request a supplier correction when needed

When supporting records show a problem, the app prepares a request using the saved invoice number and findings. The usual action does not require rewriting those fields.

Sending on WhatsApp requires configured credentials, verified supplier consent and the supported provider connection. Without that setup, copy the prepared message. A supplier's correction claim is not a verified resolution; upload/recheck the new evidence.

### 7. Finish the review

Evidence-only steps advance from saved facts. Risk acknowledgement, payment approval, CA tax review and final completion remain explicit. The completed state describes an internal review, not a filed return or recovered money.

Risks, deadlines and legal tax review is an optional CA section. Supply extra facts only when they apply: an original credit claim, reversal, MSME timing, filing observation or actual tax notice. Every legal suggestion needs CA review.

## Input inventory: what is asked, why and when

Counts below are visible body controls, excluding the three shared workspace/registration/month selectors. Buttons and read-only printed values are not input fields. Counts vary when missing facts or optional tools are opened.

| Screen/stage | Normal input | Why / reuse |
| --- | --- | --- |
| Owner overview | 0 | Oversight only. |
| Business setup | 7 visible basics; only name required | One-time/monthly context reused across roles. Before simplification the populated demo showed 29 visible controls. |
| Owner team creation | Username, display name, initial password, one role choice | Create an account once. Seven radio options are one choice, not seven assignments. |
| Staff team desk | One context filter and one optional handoff note | Read another role's context without editing its financial work. |
| Each assistant | One question and optional AI-explanation consent | Saved-facts answer first; no role selector. |
| Invoice upload | File and reader consent | Read the document once. |
| Complete invoice proposal | 0 manual inputs | Check displayed facts and confirm. |
| Incomplete invoice proposal | Only missing required details; correction form optional | No invented fields. |
| Complete order proposal | 0 manual inputs | Document supplies reference/date/value/items. |
| Complete receipt proposal | 0 manual inputs | Document supplies receiving facts; absent prices stay unknown. |
| Monthly GST upload | One file | Month/company/format reused automatically. |
| Import exceptions | Partial-row or replacement confirmation only when applicable | Avoid silently ignoring rejected records or superseding evidence. |
| Unsupported export | Column/sheet correction when needed | Resolve a genuinely different format once. |
| Payment | Explicit paid/unpaid fact; amount only if already paid; reviewed decision and reason | Recommendation and suggested release amount are filled from current evidence. Timing details are optional. |
| Supplier request | Generate/copy/send action | Invoice identifiers and issue are reused. |
| Offline supplier reply | Response state, supporting note, optional promised date | Records a fact the app has not received through a provider. |
| Supplier WhatsApp setup | Actual phone and verified consent | Required before transmitting a request. |
| Detailed node administration | Current step action/note; optional assignee/due date/handoff | CA/CFO supporting tool, not the normal invoice route. |
| Batch Sources | Kind and file | Older bulk path; format defaults from extension. Earlier form had five visible controls. |
| Batch Reconciliation | Two source selectors | Deliberate bulk comparison; normal invoice checks run automatically. |
| Cases / Reports / Payment drafts | 0 on their default lists | Rare create/generate forms are collapsed. These supporting tools are not required for every uploaded invoice. |
| Legal review facts | Optional claim/reversal/filing/notice facts | Facts not contained in an invoice must come from evidence or a reviewer. |
| CA suggestion review | Conclusion and supporting note | Explicit legal review, never an AI approval. |
| GST action guidance | Reviewed action/reason, rejection confirmation if relevant | Internal recommendation only; NOT_SUBMITTED. |
| Scenario / demo bank | Optional demonstration action | No live filing, bank release or guaranteed outcome. |

The five disconnected post-confirmation entry sections have been replaced by a progressive path. It asks for the next necessary document, reuses facts, then reveals the payment and correction actions when their supporting records are available.

## What cannot honestly be autofilled from one invoice

The invoice cannot prove delivery, supplier GST reporting, a bank transfer, the supplier's MSME status or an earlier ITC claim/reversal. The app reads supporting documents and reuses saved facts; it does not fabricate these records. A real zero and an unknown value remain different.

Reported company revenue, campaign attribution and salaries come from owner setup. There are no live accounting, advertising or infrastructure feeds. Assistants explain those saved facts and identify missing context.

## Navigation and safety

Signing out clears selection and the previous screen. Fresh login starts on the permitted role home. Refresh preserves the current account's allowed selection. A forbidden screen link redirects to that role's home before loading private tools. Company or month changes clear the invoice selection.

Role restrictions are checked on the server before private reads and writes. Writes use version checks, replay protection, evidence fingerprints and audit history. Reader actions recheck authority after the provider returns. Automatic progress does not approve payment or legal entitlement.

## Verification and limits

The broad backend integration run had 160 passes, four initial failures and one skip. The four failing scenarios were corrected; all ten targeted rechecks passed. A later unit/role/process selection passed 246 tests. Five invoice/process integration checks passed; the final statement/progress pair passed both checks. These overlapping runs must not be added together as a unique-test count.

All ten expanded browser acceptance checks passed, followed by three focused checks after the progressive-layout change. A separate CFO pending-invoice check also passed, confirming no accounting edit controls are shown. Eleven frontend client tests, 134-type API alignment, TypeScript and the production build passed. Desktop/mobile OCR confirmation tests use controlled reader responses against the isolated real backend; they do not contact Google.

A separate live Gemini retry of the fictional sample invoice succeeded with one item and twelve populated field groups. It correctly reported absent bank account and IRN. That verifies the sample, not every scan quality or document format. The live sample remains unconfirmed.

Manual inspection covered owner setup/oversight and the seven main staff roles. This is a local hackathon verification, not a guarantee of no bugs. Real bank transfer, live GST fetching/submission and guaranteed recovery remain unavailable. No code was pushed during this corrective task.
