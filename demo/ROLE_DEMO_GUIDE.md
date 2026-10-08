# Test GSTShield locally

The application is already running on this laptop at http://localhost:3000/landing.html. These accounts and figures are fictional local demonstration data, not business records or provider credentials. They were added to this laptop through authenticated routes; another cloned laptop must provision its own local accounts using the backend setup, because private SQLite storage is not part of the repository.

## Demo accounts

| View | Username | Password |
| --- | --- | --- |
| Owner | demo | gstshield-demo-only |
| First CA | demo-ca1 | gstshield-team-demo |
| Second CA | demo-ca2 | gstshield-team-demo |
| CFO | demo-cfo | gstshield-team-demo |
| CMA | demo-cma | gstshield-team-demo |
| CMO | demo-cmo | gstshield-team-demo |
| CEO | demo-ceo | gstshield-team-demo |
| COO | demo-coo | gstshield-team-demo |
| CTO | demo-cto | gstshield-team-demo |

## Start with the owner

1. Open the landing, choose Sign in and Business owner. Use the owner credentials.
2. Select Hackathon demo, Demo company and October 2026. Owner desk shows fictional reported revenue, profit and payroll. Those figures were entered, not fetched from a bank.
3. Open business details to see the fields for company, costs, people and salaries. Blank tax figures remain unknown. Only the owner may change the profile or see private employee/salary rows.
4. Team desk contains account formation and shared work updates. More than one CA or CFO is allowed. Only an authorized owner creates and changes team accounts.
5. Open the schemes or legal tax drawer when needed. A scheme is an official-link directory to discuss with a lender. A tax suggestion is a cited review opportunity, not an automatic claim or guaranteed saving.

## Test the team's shared work

1. Sign out and use Team sign in with demo-ca1. Select the same company and month. The first links prioritize Invoice desk and Reconciliation.
2. Share a short work update in Team desk. Sign in as demo-ca2 in a separate browser session or after signing out. The second CA sees the shared update.
3. Each account can only choose its approved role. A role selection is not a promotion. A CA cannot create accounts or read private employee salary rows. Aggregated business figures permitted to that role are separate from private rows.
4. Open Shared process. The same invoice/process is visible to both CAs. An assigned step can be updated by its authorized assignee; another CA may read its progress. A later step cannot complete before its prerequisite checks pass.
5. CFO emphasizes payment drafts, CMA costs, CMO reported spend/sales, COO handoffs, CEO the business memo and CTO application/integration facts. These assistants use saved facts and list missing data. They do not invent connected ads, bank balances or firm infrastructure.

## Test an invoice from start to finish

1. Invoice desk is the starting point. Open Start with an invoice. The sample PDF is output/pdf/GSTShield_SAMPLE_Invoice_MANUAL-DEMO-18000.pdf. PDF, PNG and JPEG OCR require configured Gemini, upload consent and human confirmation. Do not expect a sample PDF to prove delivery or government reporting.
2. The existing MANUAL-DEMO-18000 invoice contains 100000 goods and 18000 tax. Select it to open its story. Supply actual order and delivery facts where requested. Missing facts remain visibly missing.
3. Confirmed extraction creates a purchase-side source. A GST comparison needs a separate uploaded statement. Sources accepts the supported five-column CSV and supported B2B GSTR-2B JSON examples described in demo/README.md. Their invoice ID differs from the PDF example; use corresponding sources rather than pretending unrelated rows match.
4. Four-way review compares bill, order, receipt and GST evidence, including items. A fuzzy suggestion stays a suggestion until reviewed. Unknown tax components do not automatically become an exact match.
5. Review the amount and reasons, then explicitly choose the payment recommendation. A controlled part payment is a reviewed demonstration decision, not a live bank transfer or legal escrow. The bank simulator demonstrates permitted or blocked releases inside its own gateway only.
6. A supplier request records the missing details and follow-up state. External delivery needs provider setup. A promise or reply does not prove correction; upload the corrected evidence and recheck.
7. Shared process moves through intake, confirmation, order/delivery, GST comparison, risks, payment decision, supplier follow-up, recheck, CA tax review and final completion. Expand a node to see its owner, requirements and recorded actions. A blocked node explains what is missing.
8. Change a relevant source after review. Old decisions and downstream work should become stale and require review. The history retains who did what and which evidence was used.
9. Final completion means the team's internal review is complete. It does not mean tax was filed, a payment happened, credit is legally eligible or money was recovered.

## Keep the screen simple

Primary links reflect the selected role. More tools exposes supporting pages without removing them. Drawers open only when needed. Changing company, month or approved role clears the old invoice selection. If you see Unknown, add the missing fact; it is not a zero or a proven loss. AI explanation is optional and explicitly sends selected facts to Google when enabled.

## Verification and limits

Read md/12_ROLE_WORKSPACE_UI_PLAN.md for the exact results. All 31 browser cases have passing full-run/retry evidence; the actual 30-size/role sweep had no page errors or horizontal overflow. No new live bank, GST fetching or WhatsApp delivery was tested or claimed. Competitor claims without verified owner content remain placeholders. Every legal suggestion needs CA review. Nothing was pushed after this work.
