import { test, expect } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
const ROW = {
  voucher_id: "V1",
  recipient_gstin: "27ABCDE1234F1Z5",
  supplier_gstin: "27PQRSX5678L1Z2",
  invoice_number: "INV-001",
  invoice_date: "2024-04-10",
  document_type: "INVOICE",
  taxable_value: "1000.00",
  igst: "0.00",
  cgst: "90.00",
  sgst: "90.00",
  cess: "0.00",
  other_charges: "0.00",
  round_off: "0.00",
  gross_total: "1180.00",
};
const api = "http://127.0.0.1:8027";
async function signIn(page, period) {
  await page.goto("/#Sources");
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Username", { exact: true }).fill("alice");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-passphrase-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Sources", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption({ label: "Synthetic demonstration · owner" });
  await page
    .getByRole("combobox", { name: "Registration", exact: true })
    .selectOption({ label: "Synthetic company · 27ABCDE1234F1Z5" });
  await page.getByLabel("Accounting month", { exact: true }).fill(period);
}
async function section(page, name) {
  await page.getByRole("link", { name, exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
async function send(page, suffix, click) {
  const pending = page.waitForResponse(
    (r) =>
      r.url().split("?")[0].endsWith(suffix) &&
      ["POST", "PATCH"].includes(r.request().method()),
  );
  await click();
  const response = await pending;
  expect(response.ok(), await response.text()).toBe(true);
  return (await response.json()).data;
}
async function get(page, ws, path) {
  const response = await page.request.get(
    `${api}/api/v1/workspaces/${ws}/${path}`,
  );
  expect(response.ok(), await response.text()).toBe(true);
  return (await response.json()).data;
}
async function upload(page, kind, row, supersedes) {
  await section(page, "Sources");
  const details = page
    .locator("details")
    .filter({ has: page.locator("summary", { hasText: "Upload a source" }) })
    .first();
  if (!(await details.evaluate((e) => e.open)))
    await details.locator("summary").first().click();
  await details
    .getByRole("combobox", { name: "Source kind", exact: true })
    .selectOption(kind);
  const keys = Object.keys(row);
  const csv = [
    keys.join(","),
    keys.map((k) => JSON.stringify(row[k])).join(","),
  ].join("\n");
  await details.getByLabel("Source file").setInputFiles({
    name: "synthetic.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  if (supersedes)
    await details
      .getByRole("combobox", {
        name: "Replace earlier snapshot (optional)",
        exact: true,
      })
      .selectOption(supersedes);
  const source = await send(page, "/imports", () =>
    details.getByRole("button", { name: "Upload source", exact: true }).click(),
  );
  await expect(
    page.getByRole("button", { name: "Confirm source", exact: true }),
  ).toBeVisible({ timeout: 30000 });
  if (supersedes)
    await page
      .getByLabel(
        "Replace the selected earlier snapshot while retaining its history",
      )
      .check();
  return send(page, `/imports/${source.id}/confirm`, () =>
    page.getByRole("button", { name: "Confirm source", exact: true }).click(),
  );
}
async function compare(page, purchase, portal) {
  await section(page, "Reconciliation");
  await page
    .getByRole("combobox", { name: "Confirmed purchases", exact: true })
    .selectOption(purchase.id);
  await page
    .getByRole("combobox", {
      name: "Confirmed supplier / 2B snapshot",
      exact: true,
    })
    .selectOption(portal.id);
  const run = await send(page, "/runs", () =>
    page.getByRole("button", { name: "Compare sources", exact: true }).click(),
  );
  await expect(
    page.getByRole("button", { name: "Open result", exact: true }).first(),
  ).toBeVisible({ timeout: 30000 });
  return get(page, run.workspace_id, `runs/${run.id}`);
}
async function createCase(page, run, kind, facts) {
  await section(page, "Cases & evidence");
  await page.getByText("Create an evidence case", { exact: true }).click();
  const form = page.locator("form").filter({
    has: page.getByRole("button", { name: "Create case", exact: true }),
  });
  await form
    .getByRole("combobox", { name: "Current comparison", exact: true })
    .selectOption(run.id);
  await expect(form.locator('[name="result"] option')).toHaveCount(2);
  await form.locator('[name="result"]').selectOption({ index: 1 });
  await form
    .getByRole("combobox", { name: "Case type", exact: true })
    .selectOption(kind);
  await form
    .getByLabel("Recorded GST amount for this case (INR)", { exact: true })
    .fill("180.00");
  for (const [name, value] of Object.entries(facts)) {
    const input = form.locator(`[name="${name}"]`);
    if (await input.evaluate((e) => e.tagName === "SELECT"))
      await input.selectOption(value);
    else await input.fill(value);
  }
  const item = await send(page, "/cases", () =>
    form.getByRole("button", { name: "Create case", exact: true }).click(),
  );
  await expect(
    page.getByRole("heading", { name: "Evidence case", exact: true }),
  ).toBeVisible();
  return item;
}
async function addEvidence(page, item, event, source) {
  await expect(
    page.getByText("Refreshing saved records", { exact: false }),
  ).toHaveCount(0);
  const box = page
    .getByRole("heading", { name: "Evidence case", exact: true })
    .locator("..");
  const summary = box.getByText("Add or update evidence and recorded facts", {
    exact: true,
  });
  if (!(await summary.locator("..").evaluate((element) => element.open)))
    await summary.click();
  const form = box.locator("form").filter({
    has: page.getByRole("button", { name: "Save evidence", exact: true }),
  });
  await form
    .getByRole("combobox", { name: "Observation kind", exact: true })
    .selectOption(event);
  if (source)
    await form
      .getByRole("combobox", {
        name: "Supporting confirmed source (for document evidence)",
        exact: true,
      })
      .selectOption(source.id);
  await form
    .getByLabel("Evidence note / reason")
    .fill("Synthetic observation for browser regression.");
  const data = await send(page, `/cases/${item.id}/evidence`, () =>
    form.getByRole("button", { name: "Save evidence", exact: true }).click(),
  );
  await expect(
    box.locator("form").filter({
      has: page.getByRole("button", { name: "Save case state", exact: true }),
    }),
  ).toBeVisible();
  return data;
}
async function caseState(page, item, state) {
  await expect(
    page.getByText("Refreshing saved records", { exact: false }),
  ).toHaveCount(0);
  const box = page
    .getByRole("heading", { name: "Evidence case", exact: true })
    .locator("..");
  const form = box.locator("form").filter({
    has: page.getByRole("button", { name: "Save case state", exact: true }),
  });
  await form
    .getByRole("combobox", { name: "Case review state", exact: true })
    .selectOption(state);
  await form
    .getByLabel("Transition reason")
    .fill("Reviewed the synthetic evidence.");
  const data = await send(page, `/cases/${item.id}/transition`, () =>
    form.getByRole("button", { name: "Save case state", exact: true }).click(),
  );
  await expect(
    box.getByText(
      state
        .replaceAll("_", " ")
        .toLowerCase()
        .replace(/^./, (c) => c.toUpperCase()),
      { exact: true },
    ),
  ).toBeVisible();
  return data;
}
async function openAction(page, kind) {
  await section(page, "Work queue");
  await page
    .getByRole("button", { name: "Check latest actions", exact: true })
    .click();
  const row = page
    .getByRole("row")
    .filter({ has: page.getByRole("cell", { name: kind, exact: false }) });
  await expect(row).toHaveCount(1);
  const response = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      /\/actions\/[0-9a-f-]{36}$/.test(new URL(r.url()).pathname),
  );
  await row.getByRole("button", { name: "Open action", exact: true }).click();
  const item = (await (await response).json()).data;
  await expect(
    page.getByRole("heading", { name: "Tracked business action", exact: true }),
  ).toBeVisible();
  return item;
}
async function outcome(page, item, decision = "REVIEW_ACCEPTED") {
  const box = page
    .getByRole("heading", { name: "Tracked business action", exact: true })
    .locator("..");
  await box.getByText("Record a review decision", { exact: true }).click();
  const form = box.locator("form").filter({
    has: page.getByRole("button", {
      name: "Save review outcome",
      exact: true,
    }),
  });
  await form
    .getByRole("combobox", { name: "Review decision", exact: true })
    .selectOption(decision);
  await form
    .getByLabel("Review reason", { exact: true })
    .fill("Human review of recorded synthetic evidence.");
  const data = await send(page, `/actions/${item.id}/outcomes`, () =>
    form
      .getByRole("button", { name: "Save review outcome", exact: true })
      .click(),
  );
  await expect(
    box.getByRole("heading", {
      name: "Recorded review / observation",
      exact: true,
    }),
  ).toBeVisible();
  return data;
}
async function report(page, kind, source) {
  await section(page, "Reports");
  await page.getByText("Generate a report", { exact: true }).click();
  const form = page.locator("form").filter({
    has: page.getByRole("button", {
      name: "Generate private report",
      exact: true,
    }),
  });
  await form
    .getByRole("combobox", { name: "Report kind", exact: true })
    .selectOption(kind);
  await form
    .getByRole("combobox", { name: "Recorded source", exact: true })
    .selectOption(source.id);
  const item = await send(page, "/artifacts", () =>
    form
      .getByRole("button", { name: "Generate private report", exact: true })
      .click(),
  );
  await expect(
    page.getByRole("button", { name: "Download private report", exact: true }),
  ).toBeEnabled({ timeout: 30000 });
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download private report", exact: true })
    .click();
  const downloaded = await download;
  const content = await readFile(await downloaded.path());
  expect(content.length).toBeGreaterThan(20);
  expect(content.length).toBeLessThanOrEqual(5242880);
  if (kind.endsWith("PDF"))
    expect(content.subarray(0, 5).toString()).toBe("%PDF-");
  else expect(content.toString()).toContain("PROPOSAL_ONLY");
  await page.reload();
  await expect(
    page.getByRole("row").filter({ hasText: item.id.slice(0, 8) }),
  ).toBeVisible();
  return item;
}

test("missing recorded GST persists across newer supplier snapshots without reuploading purchases", async ({
  page,
}) => {
  test.setTimeout(120000);
  await signIn(page, "2024-05");
  const row = {
    ...ROW,
    taxable_value: "100000.00",
    cgst: "10000.00",
    sgst: "10000.00",
    gross_total: "120000.00",
  };
  const purchase = await upload(page, "PURCHASE", row);
  const portal = await upload(page, "PORTAL_2B", {
    ...row,
    invoice_number: "OTHER-999",
  });
  const run = await compare(page, purchase, portal);
  await expect(
    page.getByText("₹20,000.00", { exact: true }).first(),
  ).toBeVisible();
  let action = await openAction(page, "INVOICE_REVIEW");
  expect(action.source.recorded_tax).toBe("20000.00");
  await page
    .getByText("Create supplier follow-up draft", { exact: true })
    .click();
  let form = page.locator("form").filter({
    has: page.getByRole("button", {
      name: "Save private draft",
      exact: true,
    }),
  });
  await form
    .getByLabel("Explicit supplier phone (+country code) or email")
    .fill("+919876543210");
  await form
    .getByLabel("Requested correction / evidence")
    .fill("Please report the retained missing invoice.");
  await form.getByLabel("Draft reason").fill("Recorded missing invoice.");
  action = await send(page, `/actions/${action.id}/followups`, () =>
    form
      .getByRole("button", { name: "Save private draft", exact: true })
      .click(),
  );
  expect(action.timeline.at(-1).snapshot.delivery).toBe("NOT_SENT");
  await expect(
    page.getByText("Record an operator contact attempt", { exact: true }),
  ).toBeVisible();
  await page
    .getByText("Record an operator contact attempt", { exact: true })
    .click();
  form = page.locator("form").filter({
    has: page.getByRole("button", {
      name: "Record unverified contact attempt",
      exact: true,
    }),
  });
  await form.locator('[name="observed"]').fill("2024-06-01");
  await form
    .locator('[name="reason"]')
    .fill("Operator reports calling supplier.");
  action = await send(page, `/actions/${action.id}/followups`, () =>
    form
      .getByRole("button", {
        name: "Record unverified contact attempt",
        exact: true,
      })
      .click(),
  );
  expect(action.timeline.at(-1).snapshot.delivery).toBe(
    "USER_REPORTED_ATTEMPT_UNVERIFIED",
  );
  const updatedPortal = await upload(page, "PORTAL_2B", row, portal.id);
  const next = await compare(page, purchase, updatedPortal);
  expect(next.purchase_import_id).toBe(purchase.id);
  const retained = await openAction(page, "INVOICE_REVIEW");
  expect(retained.id).toBe(action.id);
  expect(retained.source.status).toBe("EXACT_MATCH");
  expect(retained.timeline.some((e) => e.kind === "FOLLOWUP_DRAFT")).toBe(true);
  const imports = await get(
    page,
    run.workspace_id,
    "imports?period=2024-05&kind=PURCHASE",
  );
  expect(imports.imports).toHaveLength(1);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Work queue", exact: true }),
  ).toBeVisible();
});

test("MSME payment evidence and approved proposal export connect to retained invoices", async ({
  page,
}) => {
  test.setTimeout(120000);
  await signIn(page, "2024-06");
  const purchase = await upload(page, "PURCHASE", {
    ...ROW,
    invoice_number: "PAYMENT-001",
  });
  const portal = await upload(page, "PORTAL_2B", {
    ...ROW,
    invoice_number: "PAYMENT-001",
  });
  const run = await compare(page, purchase, portal);
  let item = await createCase(page, run, "MSME_REVIEW", {
    supplier_classification: "MICRO",
    acceptance_date: "2024-04-10",
    agreed_credit_days: "30",
    amount_paid: "180.00",
    payment_observed_on: "2024-05-01",
  });
  item = await caseState(page, item, "EVIDENCE_REQUIRED");
  item = await addEvidence(page, item, "ACCEPTANCE_OBSERVATION");
  item = await addEvidence(page, item, "PAYMENT_OBSERVATION");
  item = await caseState(page, item, "REVIEW_READY");
  const action = await openAction(page, "MSME_REVIEW");
  expect(action.source.review).toBeTruthy();
  await outcome(page, action);
  await page
    .getByRole("button", { name: "Open review worksheet", exact: true })
    .click();
  await expect(
    page.getByText(
      "Review worksheet only. No return has been filed; recovery is not guaranteed.",
      { exact: true },
    ),
  ).toBeVisible();
  await section(page, "Payment drafts");
  await page.getByText("Create a payment draft", { exact: true }).click();
  await page
    .getByRole("combobox", { name: "Current comparison", exact: true })
    .selectOption(run.id);
  await page
    .getByRole("combobox", { name: "Accepted invoice", exact: true })
    .selectOption({ index: 1 });
  await page
    .getByRole("combobox", { name: "Reviewed payment evidence", exact: true })
    .selectOption(item.id);
  await page.getByLabel("Allocation amount (INR, e.g. 100.00)").fill("1000.00");
  await page
    .getByRole("button", { name: "Add allocation", exact: true })
    .click();
  const proposal = await send(page, "/proposals", () =>
    page
      .getByRole("button", {
        name: "Save payment draft (1 allocations)",
        exact: true,
      })
      .click(),
  );
  await expect(page.getByLabel("Approval reason")).toBeVisible();
  await page
    .getByLabel("Approval reason")
    .fill("Reviewed paid amount and recorded remaining balance.");
  const approved = await send(page, `/proposals/${proposal.id}/approve`, () =>
    page
      .getByRole("button", { name: "Approve recorded draft", exact: true })
      .click(),
  );
  expect(approved.state).toBe("APPROVED");
  await report(page, "PROPOSAL_CSV", approved);
});

test("reversed credit, IRN and notice evidence retain truthful human review and private PDFs", async ({
  page,
}) => {
  test.setTimeout(180000);
  await signIn(page, "2024-07");
  const purchase = await upload(page, "PURCHASE", {
    ...ROW,
    invoice_number: "EVIDENCE-001",
  });
  const portal = await upload(page, "PORTAL_2B", {
    ...ROW,
    invoice_number: "EVIDENCE-001",
  });
  const run = await compare(page, purchase, portal);
  let reversal = await createCase(page, run, "RULE37A_REVIEW", {
    original_claim_period: "2024-04",
    original_claim_amount: "180.00",
    reversal_period: "2024-05",
    reversal_amount: "180.00",
    supplier_return_period: "2024-04",
    supplier_return_status: "FILED",
    filing_observed_on: "2024-06-01",
  });
  reversal = await caseState(page, reversal, "EVIDENCE_REQUIRED");
  reversal = await addEvidence(page, reversal, "FILING_OBSERVATION");
  reversal = await addEvidence(page, reversal, "DOCUMENT", purchase);
  reversal = await caseState(page, reversal, "REVIEW_READY");
  let action = await openAction(page, "RULE37A_REVIEW");
  expect(action.source.review.reclaim_candidate).toBe(true);
  expect(action.source.review.proposed_reclaim_amount).toBe("180.00");
  action = await outcome(page, action);
  expect(action.outcome.execution).toBe("NOT_PERFORMED");
  await page
    .getByText("Record an actual filing / notice submission observation", {
      exact: true,
    })
    .click();
  let form = page.locator("form").filter({
    has: page.getByRole("button", {
      name: "Record user-reported submission",
      exact: true,
    }),
  });
  await form.locator('[name="reference"]').fill("SYNTHETIC-RETURN-REF");
  await form.locator('[name="observed"]').fill("2024-06-02");
  await form.locator('[name="amount"]').fill("180.00");
  await form
    .locator('[name="reason"]')
    .fill("User reported external submission, not executed by GSTShield.");
  await form.getByRole("checkbox", { name: /Document/ }).check();
  action = await send(page, `/actions/${action.id}/outcomes`, () =>
    form
      .getByRole("button", {
        name: "Record user-reported submission",
        exact: true,
      })
      .click(),
  );
  expect(action.outcome.government_verified).toBe(false);
  let irn = await createCase(page, run, "IRN_REVIEW", {
    irn: "a".repeat(64),
    applicability: "APPLIES",
  });
  irn = await addEvidence(page, irn, "IRN_OBSERVATION");
  await expect(
    page.getByText("IRN: FORMAT_ONLY. Government authenticity is unverified.", {
      exact: true,
    }),
  ).toBeVisible();
  action = await openAction(page, "IRN_REVIEW");
  expect(action.source.review).toBeTruthy();
  let notice = await createCase(page, run, "NOTICE_REVIEW", {
    notice_reference: "SYNTHETIC-NOTICE",
    notice_date: "2024-06-01",
    response_due_date: "2024-06-10",
  });
  notice = await caseState(page, notice, "EVIDENCE_REQUIRED");
  notice = await addEvidence(page, notice, "DOCUMENT", purchase);
  notice = await caseState(page, notice, "REVIEW_READY");
  action = await openAction(page, "NOTICE_REVIEW");
  action = await outcome(page, action);
  await report(page, "EVIDENCE_PDF", notice);
  await report(
    page,
    "RECONCILIATION_PDF",
    await get(page, run.workspace_id, `runs/${run.id}`),
  );
});

test("real role/context switches, delayed old reply, unavailable sign-out and refresh clear private state", async ({
  page,
}) => {
  await signIn(page, "2024-05");
  await section(page, "Work queue");
  await expect(
    page.getByRole("row").filter({ hasText: "INVOICE_REVIEW" }),
  ).toHaveCount(1);
  let release;
  const intercepted = new Promise((resolve) => (release = resolve));
  await page.route("**/actions?**", async (route) => {
    const response = await route.fetch();
    await intercepted;
    await route.fulfill({ response });
  });
  await page
    .getByRole("button", { name: "Check latest actions", exact: true })
    .click();
  await page.getByLabel("Accounting month", { exact: true }).fill("2024-08");
  release();
  await expect(
    page.getByText("No saved records in this selection yet.").first(),
  ).toBeVisible();
  await expect(
    page.getByRole("row").filter({ hasText: "INVOICE_REVIEW" }),
  ).toHaveCount(0);
  await page.unroute("**/actions?**");
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption({ label: "Other workspace · viewer" });
  await expect(page.getByText("You have read-only access.")).toBeVisible();
  await section(page, "Sources");
  await expect(
    page.getByRole("button", { name: "Upload source", exact: true }),
  ).toHaveCount(0);
  await page.route("**/auth/logout", (route) => route.abort());
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Private screens are cleared.", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  expect(await page.evaluate(() => Object.keys(sessionStorage))).toEqual([
    "gstshield_signed_out",
  ]);
});

test("actual backend restart retains saved invoices and server revocation clears browser access", async ({
  page,
}) => {
  test.setTimeout(90000);
  await signIn(page, "2024-05");
  await expect(
    page.getByRole("button", { name: "Preview source", exact: true }).first(),
  ).toBeVisible();
  const before = await page
    .getByRole("button", { name: "Preview source", exact: true })
    .count();
  const fixture = JSON.parse(
    await readFile("test-results/server.json", "utf8"),
  );
  await writeFile(`${fixture.root}/restart-request`, "1");
  await expect
    .poll(
      async () => {
        try {
          await readFile(`${fixture.root}/restart-completed`);
          const response = await page.request.get(`${api}/health/ready`);
          return response.ok();
        } catch {
          return false;
        }
      },
      { timeout: 30000 },
    )
    .toBe(true);
  await page
    .getByRole("button", { name: "Refresh sources", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Preview source", exact: true }),
  ).toHaveCount(before);
  const session = await page.request.get(`${api}/api/v1/auth/session`);
  const user = (await session.json()).data;
  const loggedout = await page.request.post(`${api}/api/v1/auth/logout`, {
    headers: {
      Origin: "http://127.0.0.1:3000",
      "X-CSRF-Token": user.csrf_token,
    },
  });
  expect(loggedout.ok()).toBe(true);
  await page
    .getByRole("button", { name: "Refresh sources", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Your access has expired or been revoked. Sign in again.", {
      exact: true,
    }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => sessionStorage.getItem("gstshield_selection")),
  ).toBeNull();
});

test("stale reviewer gets conflict then reloads, summary and report show persisted exact amount", async ({
  page,
}) => {
  test.setTimeout(90000);
  await signIn(page, "2024-05");
  await section(page, "Reconciliation");
  const wsResponse = await page.request.get(`${api}/api/v1/workspaces`);
  const ws = (await wsResponse.json()).data.find((x) => x.role === "OWNER").id;
  const runs = await get(page, ws, "runs?period=2024-05");
  const run = runs.runs.find((x) => x.state === "COMPLETED");
  await page
    .getByRole("row")
    .filter({ hasText: run.id.slice(0, 8) })
    .getByRole("button", { name: "Open comparison", exact: true })
    .click();
  await page.getByRole("button", { name: "Open result", exact: true }).click();
  const result = (await get(page, ws, `runs/${run.id}/results`)).results[0];
  const session = (
    await (await page.request.get(`${api}/api/v1/auth/session`)).json()
  ).data;
  const concurrent = await page.request.post(
    `${api}/api/v1/workspaces/${ws}/results/${result.id}/review`,
    {
      headers: {
        Origin: "http://127.0.0.1:3000",
        "X-CSRF-Token": session.csrf_token,
        "Idempotency-Key": crypto.randomUUID(),
      },
      data: {
        expected_version: result.version,
        action: "REJECT_MATCH",
        reason: "Concurrent recorded review.",
        candidate_id: null,
      },
    },
  );
  expect(concurrent.ok()).toBe(true);
  const form = page.locator("form").filter({
    has: page.getByRole("button", { name: "Save review", exact: true }),
  });
  await form
    .getByLabel("Review reason", { exact: true })
    .fill("Retry after another reviewer changed the record.");
  const conflict = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/results/${result.id}/review`) &&
      r.request().method() === "POST",
  );
  await form.getByRole("button", { name: "Save review", exact: true }).click();
  expect((await conflict).status()).toBe(409);
  await expect(page.getByRole("alert")).toContainText("Refresh this result");
  await page
    .getByRole("button", { name: "Reload result before retrying", exact: true })
    .click();
  await expect(
    form.getByRole("button", { name: "Save review", exact: true }),
  ).toBeVisible();
  await form
    .getByLabel("Review reason", { exact: true })
    .fill("Reviewed current version explicitly.");
  await send(page, `/results/${result.id}/review`, () =>
    form.getByRole("button", { name: "Save review", exact: true }).click(),
  );
  await expect(
    page.getByText("₹20,000.00", { exact: true }).first(),
  ).toBeVisible();
  const current = await get(page, ws, `runs/${run.id}`);
  expect(current.summary.tax_exposure_review).toBe("20000.00");
  await report(page, "RECONCILIATION_PDF", current);
});
