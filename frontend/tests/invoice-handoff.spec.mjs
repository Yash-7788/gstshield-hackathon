import { test, expect } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`invoice-specific cases and drafts remain connected at ${width}px`, async ({
    page,
  }) => {
    const ws = "11111111-1111-4111-8111-111111111111";
    const rid = "22222222-2222-4222-8222-222222222222";
    const pid = "33333333-3333-4333-8333-333333333333";
    const runId = "44444444-4444-4444-8444-444444444444";
    const resultId = "55555555-5555-4555-8555-555555555555";
    const doc = "66666666-6666-4666-8666-666666666666";
    const caseId = "77777777-7777-4777-8777-777777777777";
    const draftId = "88888888-8888-4888-8888-888888888888";
    const period = new Date().toISOString().slice(0, 7);
    const fields = {
      document_type: "INVOICE",
      invoice_number: "HANDOFF-001",
      supplier_name: "Sample supplier",
      supplier_gstin: "27PQRSX5678L1Z2",
      invoice_date: period + "-01",
      taxable_value: "100000.00",
      gross_total: "118000.00",
      total_tax: "18000.00",
      items: [],
    };
    const invoice = {
      id: pid,
      workspace_id: ws,
      registration_id: rid,
      period,
      confirmed: true,
      version: 1,
      filename: "sample.pdf",
      fields,
      findings: {
        summary: "MATCHED",
        invoice: "CONFIRMED",
        po: "MATCHED",
        receipt: "MATCHED",
        gst: "MATCHED",
      },
      gate: {
        remaining_amount: "118000.00",
        recorded_tax_under_review: "0.00",
        recommendation: "PAY",
        payment_facts_confirmed: true,
      },
      clocks: { facts: {} },
      approval: null,
      resolution: { state: "NOT_STARTED" },
      demo_bank: { attempts: [] },
      supplier_channel: {},
      history: [],
      extraction: {},
      purchase_import_id: doc,
      source_signature: "a".repeat(64),
    };
    const run = {
      id: runId,
      run_id: runId,
      state: "COMPLETED",
      version: 1,
      sources_current: true,
      registration_id: rid,
      period,
      revision: 1,
      job_id: runId,
      summary: null,
    };
    const result = {
      provenance: "SYNTHETIC_DEMO",
      id: resultId,
      run_id: runId,
      workspace_id: ws,
      purchase_document_id: doc,
      source_row_number: 1,
      status: "EXACT_MATCH",
      version: 1,
      canonical: fields,
      reason_codes: [],
    };
    const evidence = {
      provenance: "SYNTHETIC_DEMO",
      id: caseId,
      workspace_id: ws,
      registration_id: rid,
      result_id: resultId,
      purchase_document_id: doc,
      kind: "RULE37_REVIEW",
      amount: "18000.00",
      state: "REVIEW_READY",
      version: 1,
      facts: { amount_paid: "0.00", payment_observed_on: period + "-01" },
      missing_facts: [],
      timeline: [],
      irn_observation: "NOT_PROVIDED",
    };
    const draft = {
      id: draftId,
      workspace_id: ws,
      run_id: runId,
      state: "DRAFT",
      version: 1,
      sources_current: true,
      snapshot: { total_allocated: "100000.00" },
      timeline: [],
    };
    const workflow = {
      passport_id: pid,
      registration_id: rid,
      period,
      invoice_number: "HANDOFF-001",
      confirmed: true,
      purchase_import_id: doc,
      portal_import_id: resultId,
      purchase_document_id: doc,
      run,
      result,
      cases: [evidence],
      proposals: [draft],
    };
    page.on("pageerror", (error) =>
      console.error("Browser page error:", error.message),
    );
    let workflowReads = 0;
    let mutations = 0;
    await page.route("**/api/v1/**", async (route) => {
      if (route.request().method() !== "GET") mutations++;
      const path = new URL(route.request().url()).pathname;
      let data;
      if (path.endsWith("auth/session"))
        data = {
          user_id: ws,
          username: "demo",
          csrf_token: "synthetic",
          expires_at: new Date(Date.now() + 600000).toISOString(),
        };
      else if (path.endsWith("workspaces"))
        data = [{ id: ws, name: "Sample company", role: "OWNER" }];
      else if (path.endsWith("registrations"))
        data = [
          {
            id: rid,
            workspace_id: ws,
            gstin: "27ABCDE1234F1Z5",
            display_name: "Sample registration",
          },
        ];
      else if (path.endsWith("/workflow")) {
        workflowReads++;
        data =
          workflowReads === 1
            ? {
                ...workflow,
                automation: { state: "QUEUED" },
                run: { ...run, state: "QUEUED" },
                result: null,
              }
            : workflow;
      } else if (path.endsWith("/passports"))
        data = {
          passports: [invoice],
          metrics: {},
          vendors: [],
          anomalies: [],
          provider: {},
        };
      else if (path.endsWith("/imports"))
        data = { imports: [], next_cursor: null };
      else if (path.endsWith("/cases"))
        data = { cases: [evidence], next_cursor: null };
      else if (path.endsWith("/cases/" + caseId)) data = evidence;
      else if (path.endsWith("/proposals"))
        data = { proposals: [draft], next_cursor: null };
      else if (path.endsWith("/proposals/" + draftId)) data = draft;
      else if (path.endsWith("/runs"))
        data = { runs: [run], next_cursor: null };
      else if (path.endsWith("/results"))
        data = { results: [result], next_cursor: null };
      else
        return route.fulfill({
          status: 404,
          json: { error: { message: "Unexpected fixture request" } },
        });
      await route.fulfill({ json: { data } });
    });
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(
      page.getByRole("heading", {
        name: "Invoice desk",
        exact: true,
        level: 1,
      }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: /HANDOFF-001 Sample supplier/ })
      .click();
    await page
      .getByRole("button", { name: "Cases for this invoice", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Evidence case", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("article", { name: "Selected invoice workflow" }),
    ).toContainText("Comparing your confirmed records automatically.");
    await expect(
      page.getByRole("article", { name: "Selected invoice workflow" }),
    ).toContainText("HANDOFF-001");

    await page.getByText("Create an evidence case", { exact: true }).click();
    await expect(
      page.getByRole("combobox", { name: "Current comparison", exact: true }),
    ).toHaveValue(runId);
    await expect(
      page.getByRole("combobox", { name: "Invoice result", exact: true }),
    ).toHaveValue(resultId);
    await page
      .getByRole("button", { name: "Open invoice payment drafts", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Payment proposal", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Approve recorded draft", exact: true }),
    ).toBeVisible();
    await page.getByText("Create a payment draft", { exact: true }).click();
    await expect(
      page.getByRole("combobox", { name: "Accepted invoice", exact: true }),
    ).toHaveValue(resultId);
    await expect(
      page.getByRole("combobox", {
        name: "Reviewed payment evidence",
        exact: true,
      }),
    ).toHaveValue(caseId);
    expect(mutations).toBe(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await page
      .getByRole("button", { name: "Back to this invoice", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "HANDOFF-001", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Cases for this invoice", exact: true })
      .click();
    await page.getByLabel("Accounting month", { exact: true }).fill("2024-01");
    await expect(
      page.getByRole("article", { name: "Selected invoice workflow" }),
    ).toHaveCount(0);
    expect(mutations).toBe(0);
  });
}
