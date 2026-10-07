# GSTShield: first manual test, in plain English

This is a controlled software test with fictional records. It teaches the flow without requiring accounting knowledge. It does not determine tax eligibility or make an actual bank payment.

## Start here

- Website: http://localhost:3000/
- Username: `demo`
- Password: `gstshield-demo-only`
- Workspace: **Hackathon demo**
- Registration: **Demo company**, `27ABCDE1234F1Z5`
- Accounting month: **2026-10**
- Invoice PDF: `output/pdf/GSTShield_SAMPLE_Invoice_MANUAL-DEMO-18000.pdf`
- Extra GST CSVs: `demo/manual-test/`

Both the website and backend must remain running on this PC. A laptop shutdown or sleep stops the local experience. No real customer data is needed.

## What the numbers mean

You are pretending to buy 10 pumps. Their price before tax is ₹1,00,000. The sample tax is ₹18,000. The invoice total is ₹1,18,000.

An order records what you intended to buy. A delivery receipt records what arrived. The invoice records what the supplier charged. A GST statement supplies the tax-side comparison record. The application checks these saved sources and recommends a payment decision.

In this test, the tax-side invoice starts missing. That means the application should ask for correction and protect the tax portion in its demo payment gate. It does not establish that a supplier committed fraud or that tax credit is legally lost.

## Before you click

Use this sample once for the clean journey. If this invoice already exists, select it rather than confirming another identical copy. Deliberately creating a duplicate triggers a different protection and changes the expected result.

Wait for each operation to finish and for the screen to refresh before taking the next step. Do not repeatedly click a button while it is saving.

### 1. Sign in and choose your test company

Open the website, sign in with the demo account and select the workspace, registration and accounting month listed above.

**Why:** invoices, sources and approvals belong to a particular company and month. You must compare records in the same context.

**Look for:** the selected Demo company and October 2026. Go to **Invoice desk**, then **Invoices**.

### 2. Let AI read the sample invoice

Open **Add an invoice**. Choose the sample PDF under **Invoice PDF or photo**. Tick **Allow Google AI to read this invoice.** Click **Read invoice**.

**Why:** this checks the actual extraction connection, not just manual entry.

**Look for:** proposed supplier, invoice, amounts and item fields. Review them against this exact checklist:

| Field | Expected value |
|---|---|
| Supplier GST number | 27PQRSX5678L1Z2 |
| Supplier name | Sample Pump Supplier |
| Invoice number | MANUAL-DEMO-18000 |
| Invoice date | 2026-10-07 |
| Goods value | 100000.00 |
| CGST | 9000.00 |
| SGST | 9000.00 |
| IGST / Cess | 0.00 / 0.00 |
| Other charges / Rounding | 0.00 / 0.00 |
| Invoice total | 118000.00 |
| Total quantity | 10 |
| Item name | Industrial pumps |
| Item code | PUMP-01 |
| Unit | pieces |
| Item quantity / Goods value | 10 / 100000.00 |

Correct any extraction mistake before **Confirm details**. If no item appears, use **Add item** and enter it. Leave the e-invoice reference and bank account empty: this sample supplies neither.

**Pass:** the saved invoice shows the correct fields and one item. OCR proposals remain subject to your confirmation.

**Fail:** an unreadable document is silently accepted, wrong figures cannot be corrected, or confirmation saves different figures. If the provider returns an error, report the exact error; do not call that a passed AI test. Manual entry can test the remaining workflow separately.

### 3. Record the matching order

Select the invoice. Under **1. Check the four records**, choose **Add purchase order details**.

Enter reference `PO-MANUAL-01`, goods value `100000.00`, total quantity `10`, date `2026-10-07`. Under **Individual items**, add Industrial pumps / PUMP-01 / pieces / quantity 10 / goods value 100000.00. Save the order.

**Why:** the application must compare what was ordered with what was invoiced, including the individual item.

**Pass:** the order matches. Entering only a total is insufficient for this item-level test.

### 4. Record the matching delivery

Choose **Add delivery receipt details**. Enter reference `GRN-MANUAL-01`, goods value `100000.00`, total quantity `10`, date `2026-10-07`. Add the same individual item and save the receipt.

**Why:** a bill and an order agreeing does not show that goods arrived. This tests the separate delivery comparison.

**Pass:** order and delivery both match the invoice, with matching item comparisons.

### 5. Record the baseline payment facts

Open **2. Review payment dates** and **Record payment and timing facts**. Leave MSME timing at **Not confirmed**, enter **Already paid = 0**, and leave unrelated timing dates blank. Save dates.

**Why:** the gate needs recorded payment facts. We keep deadline-specific conditions out of this first test so they do not mask the missing-GST scenario.

**Pass:** the unpaid invoice amount is ₹1,18,000. The application does not invent a legal deadline from missing facts.

### 6. Simulate missing GST evidence

Go to **Watch & outcomes**, choose this invoice, open **Demo GST fetching** and click **Fetch sample: invoice missing**. Return to **Invoices** and select the same saved invoice if needed.

**Why:** this demonstrates a received tax-side snapshot that does not contain the target invoice. It is not a government portal request.

**Pass:** invoice, order and delivery agree; the GST record is missing. The screen shows ₹18,000 recorded tax needing attention and a part-payment recommendation when no other blocking condition exists.

**Fail:** the application treats missing evidence as a confirmed match, hides that the source is simulated, or permits an unapproved release.

### 7. Try to pay the full balance before approval

Expand **Demo bank - test the payment protection** and click **Try paying the balance**.

**Why:** recommendations alone do not demonstrate enforcement. This button attempts a simulated transfer through the gate.

**Pass:** **Payment blocked**. Demo money released remains ₹0. No real transfer occurs.

### 8. Approve and release only the base amount

Under **3. Decide payment**, choose **Part payment**. Enter approved amount `100000.00`. Enter a reason, for example: `Order and delivery match; hold the tax until the supplier record is corrected.` Save decision.

In the demo bank, click **Release permitted demo amount**.

**Pass:** demo money released becomes ₹1,00,000; demo balance held is ₹18,000. **Try paying the balance** should still block the remaining tax while evidence is missing.

**Why:** an approver explicitly controls the exception; the system does not silently decide to pay a supplier.

The demo ledger is separate from actual payment facts. **Already paid** remains 0 and the actual invoice balance can still display ₹1,18,000. The demo bank alone displays the simulated ₹1,00,000 release. That separation prevents fake demo transfers from altering real accounting facts.

### 9. Prepare and track the supplier correction

Open **4. Request correction**. Click **Prepare supplier request** and inspect the message.

**Pass:** it identifies this supplier/invoice and explains the missing GST evidence. Copy the message if desired. Under **Record supplier response**, record **Correction promised**, a future promised date, and a short note; save it.

**Why:** the case should retain follow-up history so users do not have to remember everything themselves.

Real WhatsApp delivery and replies require the Meta account, callback and consent setup. They are not configured for this local test. A prepared message or manual response is not proof that an external message was sent. Do not send fictional requests to a real supplier.

### 10. Bring in the corrected tax record

Go to **Watch & outcomes**, choose the invoice and click **Fetch sample: invoice corrected**. Return to the invoice.

**Pass:** the GST record now matches, and the old payment approval becomes stale or requires a fresh decision. The original invoice, order, receipt and earlier history remain saved.

**Why:** new evidence changes the basis of a decision. An old approval must not automatically authorize a new payment amount.

Before approving again, try the demo payment button. It should block release under the stale approval.

### 11. Approve again and release the remainder

Choose **Full payment**, approved amount `118000.00`, and a reason such as `The corrected GST statement now agrees with the invoice, order and delivery.` Save decision, then click **Release permitted demo amount**.

**Pass:** only the remaining ₹18,000 is released in the demo ledger. Total demo money released reaches ₹1,18,000 and demo balance held reaches ₹0. Repeating release must not pay the invoice twice.

You approve the full invoice amount because the real payment facts still say zero paid. The demo bank subtracts its earlier ₹1,00,000 release and transfers only its remaining ₹18,000. Do not change actual payment facts merely to simulate this test.

### 12. Inspect the history and the broader tools

Open **Invoice details and history** and **Download history PDF**. Check that it records saved sources, changes, decisions and demo gateway events. Review supplier follow-up separately where available.

Go to **Suppliers**: look at reliability signals and explanations. There is no required score of 42; scores depend on the saved history. A low score or unusual pattern is a review signal, not proof of fraud.

Go to **Finance**, then **Ask about today's priorities**. Click **Show priorities**. Check that money, reasons and actions agree with the invoices in this month. Test the optional AI explanation separately; it must not invent a payment or tax submission.

Under **Explore a payment**, enter available cash `200000.00` and proposed payment `118000.00`. Compare the scenario. It should describe the resulting cash position without making a transfer.

Under **Prepare an evidence note**, describe the fictional concern in at least 20 characters. The output is a draft grounded in supplied records, with missing evidence identified. It is not a filed response or a guaranteed outcome.

In **GST action guidance**, review the proposal. For a clean matching record, test saving **Accept** with a reason. The result remains a recorded review, not a GST portal submission.

In **Watch & outcomes**, **Monitor on this PC** can recheck records available to this backend while it is running. It does not fetch the government portal or continue when the PC is off. Turn monitoring off after testing if you no longer want it.

## Expected money progression

| Stage | Demo released | Demo held | Expected protection |
|---|---:|---:|---|
| Missing GST, no approval | ₹0 | ₹1,18,000 | Full payment blocked |
| Part-payment approved and released | ₹1,00,000 | ₹18,000 | Tax remainder blocked |
| Corrected GST, old approval | ₹1,00,000 | ₹18,000 | Fresh approval required |
| New full-payment approval released | ₹1,18,000 | ₹0 | Repeat transfer cannot overpay |

## Optional: test actual CSV upload instead of sample fetching

These CSVs are fictional test inputs, not government exports. The application can compare uploaded records; it cannot authenticate their government origin.

1. Go to **Sources** in the same company and October 2026.
2. Set **Source kind = Supplier / 2B snapshot**, **File format = CSV**.
3. Upload `01_SAMPLE_gst_missing_invoice.csv`, inspect the accepted row, then click **Confirm source**.
4. In the invoice's **Choose GST statement**, explicitly select this uploaded statement and click **Compare statement**. It should show the target invoice missing; the file intentionally contains another invoice.
5. Upload and confirm `02_SAMPLE_gst_corrected_invoice.csv`. You may replace the earlier uploaded snapshot by selecting it and acknowledging the replacement, or keep separate sources and select explicitly.
6. Select the corrected statement in the invoice and compare. It should match and invalidate any earlier payment approval.
7. Finally, upload `03_SAMPLE_gst_changed_tax.csv`. Select it explicitly and compare. Its total tax is ₹16,000 versus the invoice's ₹18,000; the mismatch must be visible and the old approval unusable.

If several GST snapshots are available, never assume the latest file was selected automatically. Select the intended statement. Keep the source ID shown after upload to identify it in the comparison dropdown.

Do not run this optional mismatch step before the clean payment journey; it intentionally changes the outcome. Do not approve/release any more money after the demo ledger has fully paid this sample.

## Useful failure tests, after the main journey

- Change delivery quantity to 9: delivery must stop matching and an existing approval must become stale. Restore the exact item only when testing recovery.
- Change the item code while retaining the same totals: equal money alone must not disguise an item mismatch.
- Try release without a saved approval on a fresh invoice: it must block.
- Repeat the payment button: it must not overpay or create duplicate successful transfers for the same release.
- Switch company/month and return: records must stay scoped correctly; reselect the invoice instead of trusting an old screen.
- Refresh the browser: saved invoices and decisions should remain; unsaved form inputs may be lost.
- Use a duplicate invoice only as a separate final test: duplicate detection changes the clean journey. Do not create a duplicate just to restart.
- Record **Resolved** while GST is still missing: the software must not accept it as a verified resolution of the mismatch.

## What this manual test proves, and what it does not

A passed journey demonstrates extraction with confirmation, matching saved evidence, item checks, approval invalidation, a simulated payment gate, tracked correction and saved history.

It does not demonstrate live government fetching, official GST filing, a real bank block/transfer, live WhatsApp delivery without setup, guaranteed tax recovery, or legal approval. The sample and simulations should remain visibly labelled during the hackathon.

The expanded supplier, fraud, finance, monitoring and review tools depend on the records you provide. A single clean invoice cannot demonstrate shared-bank patterns, repeat disputes or long-term supplier history. Use separate controlled data for those later.

## If a step differs from the expected result

Record the screen name, invoice number, button, displayed error and expected result. Avoid changing unrelated fields while investigating. If the application says the record changed, reload it, read the latest evidence and save a deliberate fresh decision. Never bypass the gate to make the demo appear successful.

This kit adds test documents only; it does not reset your saved data, run regression, commit or push changes.


## New: continue from the selected invoice into cases and payment drafts

Invoice desk is now the starting screen. After confirming an invoice, use **Cases for this invoice** or **Payment drafts for this invoice**. A banner keeps the invoice identity visible and shows the next prerequisite. Once the invoice and its selected GST statement are confirmed, the comparison starts automatically. **View comparison** shows its progress and results. Wait for completion, then open the invoice cases. Confirming a replacement GST statement reruns the affected comparisons; explicitly selecting another statement also updates the comparison. Missing order, delivery or payment facts still need to be supplied before their checks can be completed.

The case creation form preselects the exact comparison result. Existing related cases appear automatically. Record the relevant facts and supporting observations and review the case explicitly; opening the page does not manufacture evidence. In the payment-draft screen, the current comparison and eligible invoice/payment evidence are preselected. You still enter allocations, save a draft and approve it deliberately. **Back to this invoice** returns to the original saved invoice. **Show all records** restores the broader screen. Changing company or month clears this handoff.

This connection uses existing records, requires no second invoice upload, and does not convert a payment-gate decision into a bank transfer or automatically approve a case or draft. The related screens remain separate views of the invoice workflow.
