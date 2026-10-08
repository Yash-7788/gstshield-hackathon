# GSTShield: how to use it, role by role

Updated 8 October 2026. This guide describes the current local application. Use the supplied fictional test documents in a test company, never as actual tax evidence.

## The idea in one minute

A supplier sends a bill. Before deciding what to pay, your team checks four different records: the bill, what you ordered, what arrived, and what appears in the supplied GST statement. GSTShield keeps those records, the reasons for a decision, supplier follow-up and team progress together.

For our example, ten pumps cost Rs 100,000 plus Rs 18,000 GST, total Rs 118,000. If the bill is absent from the GST statement, Rs 18,000 is tax needing review. This is not automatically a loss. A finance reviewer can consider paying the goods amount while holding the tax portion, subject to the evidence and policy. The application cannot actually block a payment made outside its simulated bank.

## Start here

1. Keep the local backend and frontend running.
2. Open http://localhost:3000/landing.html for the landing page, or http://localhost:3000/ for sign-in.
3. Choose Business owner for the owner account, Team member for a registered staff account.
4. Use the username and password assigned during team setup. The chosen portal must match the account. Another role's password does not grant owner access.
5. Select the same workspace, company and month across the team. For the supplied test files use the company GSTIN 27ABCDE1234F1Z5 and October 2026 (2026-10).
6. If the company or month changes, the selected invoice clears. Select an invoice belonging to the new context.

Current local account names in the latest setup guide are owner, ca1, ca2, cfo, cma, cmo, ceo, coo and cto. Passwords may have been individually changed; this guide does not assert an old shared password. The repository does not contain your laptop's accounts/database. Another laptop must set up its own local owner and team.

## Owner: set up once, then watch progress

1. Sign in through Business owner.
2. Open Team desk, then Create your team.
3. Add each person's name and choose one role. You can create two CAs or several CFOs, but each person has one role.
4. Choose Next: sign-in accounts. Give each person their own username and password, then Register team accounts.
5. In People and access, the owner can change an existing person's password or access. Do not share the owner account with staff.
6. In Business setup, enter the business name and known figures such as monthly revenue, profit and operating cost. Additional marketing, loan and salary sections are optional. Leave unavailable figures unknown.
7. Return to Owner desk. Read what needs attention, the amount involved, who is working on it and why work is waiting.
8. Look at the read-only process summary. The owner does not confirm invoices or approve finance decisions from this view.
9. Government scheme links are a directory for further checking; they are not an approved loan or automatic entitlement.

Owner check: after the CA saves a comparison or the CFO saves a current decision, refresh the overview if it has not yet refreshed itself. You should see saved progress in the same company/month. The owner view has no accounting edit controls.

## CA: the normal invoice journey

Use Invoice desk as your main screen. Sources, Reconciliation, Cases and Reports are supporting tools; you do not need to visit every tool for every invoice.

### Step 1: read the bill

1. Open Invoice desk, choose Add an invoice.
2. Select demo/test-pack/01_Invoice_TEST-OCT08-18000.pdf.
3. Allow Google AI reading if you want OCR, then choose Read invoice. A configured Gemini key and network are required.
4. Review the proposed supplier, bill number, date, goods amount, tax, total and items. Expected bill number is TEST-OCT08-18000; ten pumps; goods Rs 100,000; GST Rs 18,000; total Rs 118,000.
5. Choose Confirm details. Correct an actual extraction mistake or missing required fact; do not retype correct populated fields.
6. If this bill is already confirmed, select its saved entry instead of creating another copy. A deliberate second confirmation can trigger duplicate checks.

PDF, PNG and JPEG are supported for invoice/document reading, up to 4 MB. A bill alone does not prove delivery, GST reporting or a payment. Missing facts cannot honestly be filled with invented values.

### Step 2: add what you ordered

1. Follow the next order/evidence action for this invoice.
2. Upload 02_Purchase_Order_PO-TEST-OCT08.pdf.
3. Choose Read supporting document, check the populated facts and confirm once.
4. The order describes ten pumps and Rs 100,000 goods. The application compares saved item facts automatically.

### Step 3: add what arrived

1. Follow the next delivery/receipt action.
2. Upload 03_Delivery_Receipt_GRN-TEST-OCT08.pdf and confirm the populated facts.
3. It records ten pumps received. Prices are intentionally absent; they remain unknown rather than being copied from the bill.
4. The order and delivery quantity checks should agree.

### Step 4: supply GST evidence once for the month

1. Follow the GST statement action and upload 04_GST_Statement_A_Invoice_Missing.json.
2. Read the parsed rows and confirm the statement/current selection.
3. This fictional statement omits your test bill. The invoice should show missing GST evidence and Rs 18,000 tax needing review.
4. That monthly statement is reused for other invoices in the same company/month. Do not re-upload it for every bill.
5. Supported GSTR-2B JSON and CSV/XLSX exports can be imported. Nonstandard columns/sheets may require one mapping correction in Sources.

These sample JSON files are software fixtures, not live government records. Real use requires your own downloaded statement or an authorized future integration.

### Step 5: review findings and hand over to finance

1. Read the four-way check: bill, order, delivery and GST evidence.
2. Explain any mismatch or missing evidence using the saved facts.
3. Record applicable risk/tax reviews when requested. Legal suggestions require confirmation with the CA, a conclusion and supporting note.
4. Share a handoff in Team desk: identify the invoice, what was checked, what is waiting and the next person needed.

The CA can access the permitted accounting/review tools. The CMA cannot inherit CA controls through a dropdown.

## CFO: decide what may be paid

1. Sign in as Team member with the CFO account.
2. Select the same company/month and open Invoice desk.
3. Select TEST-OCT08-18000. Review the CA-confirmed facts and current findings. CFO intake is read-only; the CFO cannot edit/confirm the CA extraction proposal.
4. Confirm the fact outside the documents: whether any payment already happened. For this fictional baseline, confirm unpaid. If money was paid, enter the actual amount; never guess.
5. Review the proposed decision and amount. With aligned order/delivery, no other blocking finding and missing GST evidence, controlled part payment may propose Rs 100,000 while Rs 18,000 remains under review.
6. Choose the permitted decision and supply the requested reason. Hold/escalate may be appropriate when other evidence is missing or mismatched.
7. A simulated bank attempt before current approval, or above its permitted amount, should be blocked. A permitted simulated release writes only the local ledger; no real bank transfer happens.
8. For the simplest stale-approval test, approve but do not simulate a release yet.
9. Use Assistants for a saved-facts summary of payment priorities. Payment drafts and Reports are supporting pages when relevant.

Payment approval stays explicit. New evidence can stale the approval; the application must not silently reapprove it.

## Supplier correction and recheck

1. The authorized CA or follow-up member prepares the correction request from the invoice's findings. Check that TEST-OCT08-18000 and the missing GST record are included.
2. Copy the request for this local test. Real WhatsApp sending requires configured Meta credentials, callback and verified supplier consent.
3. A supplier promise or recorded reply is a claim, not proof of correction.
4. As CA, upload 05_GST_Statement_B_Invoice_Corrected.json as the new current October statement, review its rows and confirm replacement when asked.
5. The GST comparison should now align. An approval made against statement A must become stale.
6. The CFO reviews the revised evidence and saves a fresh decision when appropriate.
7. Complete any remaining CA tax review and final process step only when its exit checks allow it.
8. Owner sees the internal completed result and recorded team actions. This does not mean a GST return was submitted or money was recovered.

## Other role desks

| Role | Start with | What to do | How it contributes |
| --- | --- | --- | --- |
| CMA | Team desk, Assistants | Review reported operating cost, profit, payroll totals and confirmed invoice cost facts. Ask about costs and missing information. | Share cost concerns for CFO/owner context. No CA reconciliation or payment approval. |
| CMO | Team desk, Assistants | Review entered marketing spend and attributed sales. Ask what the saved figures show; note missing attribution. | Share marketing context with finance and management. No live ad-platform feed. |
| CEO | Team desk, Assistants | Read the saved business summary and priorities. | Coordinate decisions and handoffs; no automatic financial approval. |
| COO | Team desk, Assistants | Look for missing orders, receiving evidence or stalled handoffs. | Ask the right person to provide genuine supporting facts. No fabricated receipt. |
| CTO | Team desk, Assistants | Review the application's configured connection status and limits. | Explain which integrations still need setup. It does not scan the company's infrastructure. |
| Accounts, if assigned | Invoice desk, Sources | Upload and confirm allowed invoice/import facts. | Give the CA a saved intake record. |
| Warehouse, if assigned | Invoice desk | Supply/review permitted order and receipt evidence. | Give reviewers genuine commercial facts. |
| Follow-up, if assigned | Invoice desk, WhatsApp | Prepare permitted supplier requests and record replies. | Give CA new evidence to recheck; cannot declare legal eligibility. |
| Observer, if assigned | Team desk | Read shared notes. | Read-only team context. |

Assistants answer from saved facts first. Requesting an AI explanation is optional and sends allowed selected facts to Google; it does not make the assistant an approver. Missing bank, sales, salary or tax facts are not invented.

## Two CAs working together

1. Owner registers ca1 and ca2 as separate CA accounts with separate credentials.
2. CA1 selects the invoice and records a Team desk handoff.
3. CA2 signs in with their own account, selects the same company/month and reads the handoff and permitted invoice progress.
4. Shared process is a supporting CA/CFO view. If used, assignments, due dates and handoff notes belong to specific nodes; later nodes need prior exit checks.
5. An unassigned colleague can read permitted progress but cannot take over a restricted assigned action just by opening its page.
6. Do not use the same account simultaneously as two people; use separate accounts and browser sessions. Signing out clears the prior private screen.

## How the screens connect

Owner setup -> registered team and shared company/month -> CA confirms documents -> automatic comparison from saved sources -> CFO reviews current payment -> supplier correction -> CA rechecks -> explicit tax/final review -> owner reads result.

All roles share permitted records from the same local SQLite database. Their screens and authority differ. The landing page links to sign-in; it is not a separate finance database. Same company/month matters. A handoff note provides context, not permission to edit another role's work.

Only required supporting facts are entered. Fields read correctly from OCR are reused. The monthly GST statement is reused. Missing PO, delivery, payment or legal-history facts still require genuine documents or a responsible human.

## Quick checks you can perform

- CA: four records connect to one bill; the original missing statement leaves tax under review.
- CFO: cannot confirm CA intake; cannot simulate an unapproved/oversized release.
- CMA/CMO: get their saved-facts assistants, not invoice-edit controls.
- Owner: sees progress without performing accounting steps.
- Updated statement: old approval becomes stale; matching does not equal automatic legal claimability.
- Switch company/month: old invoice selection clears.
- Remove a file/invoice: use its removal action and confirmation. Used source uploads cannot be deleted as unused. Financial history remains; backups/downloads are separate copies.

## Limits to remember

Bank is simulated. Real GST fetching and filing are unavailable. Actual WhatsApp delivery needs external setup. Internal IMS guidance is not submitted. Notice documents are drafts for review. IRN format checks are not government authenticity checks. No guaranteed tax saving, recovery or loan approval is promised.
