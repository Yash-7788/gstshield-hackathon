import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
const api = "http://127.0.0.1:8027";
const item = {
  description: "Industrial pumps",
  sku: "PUMP-01",
  unit: "pieces",
  quantity: "10",
  taxable_value: "100000.00",
};
for (const width of [1280, 390]) {
  test(`real invoice items and GST action workflow at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/#Sources");
    await page.getByLabel("Username", { exact: true }).fill("alice");
    await page
      .getByLabel("Password", { exact: true })
      .fill("synthetic-passphrase-only");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Sources", exact: true }),
    ).toBeVisible();
    const workspace = page.getByRole("combobox", {
      name: "Workspace",
      exact: true,
    });
    await workspace.selectOption({ label: "Synthetic demonstration · owner" });
    const registration = page.getByRole("combobox", {
      name: "Registration",
      exact: true,
    });
    await registration.selectOption({
      label: "Synthetic company · 27ABCDE1234F1Z5",
    });
    await page.getByLabel("Accounting month", { exact: true }).fill("2024-05");
    const ws = await workspace.inputValue(),
      rid = await registration.inputValue();
    const auth = (
      await (await page.request.get(api + "/api/v1/auth/session")).json()
    ).data;
    const headers = {
      Origin: "http://127.0.0.1:3000",
      "X-CSRF-Token": auth.csrf_token,
    };
    const base = api + `/api/v1/workspaces/${ws}/passports`;
    const raw = await page.request.post(base + "/documents", {
      headers: { ...headers, "Idempotency-Key": randomUUID() },
      multipart: {
        registration_id: rid,
        period: "2024-05",
        consent: "true",
        file: {
          name: `fixture-${width}.pdf`,
          mimeType: "application/pdf",
          buffer: Buffer.from("%PDF-1.7 synthetic fixture"),
        },
      },
    });
    expect(raw.ok(), await raw.text()).toBe(true);
    let invoice = (await raw.json()).data;
    const pid = invoice.id;
    async function post(suffix, data) {
      const response = await page.request.post(
        base + "/" + pid + "/" + suffix,
        { headers: { ...headers, "Idempotency-Key": randomUUID() }, data },
      );
      expect(response.ok(), await response.text()).toBe(true);
      return (await response.json()).data;
    }
    invoice = await post("confirm", {
      expected_version: invoice.version,
      fields: {
        supplier_gstin: "27PQRSX5678L1Z2",
        supplier_name: "Synthetic supplier",
        invoice_number: `BROWSER-${width}`,
        invoice_date: "2024-05-10",
        taxable_value: "100000.00",
        igst: "0.00",
        cgst: "9000.00",
        sgst: "9000.00",
        cess: "0.00",
        gross_total: "118000.00",
        quantity: "10",
        items: [item],
      },
    });
    invoice = await post("evidence", {
      expected_version: invoice.version,
      kind: "PO",
      reference: "ORDER-001",
      observed_on: "2024-05-10",
      taxable_value: "100000.00",
      quantity: "10",
      items: [item],
    });
    invoice = await post("simulate-fetch", {
      expected_version: invoice.version,
      status: "MATCHED",
    });
    await page.getByRole("link", { name: "Invoice desk", exact: true }).click();
    await page
      .getByRole("button", { name: new RegExp(`BROWSER-${width}`) })
      .click();
    const receipt = page
      .locator("details")
      .filter({
        has: page.locator("summary", {
          hasText: "Add delivery receipt details",
        }),
      })
      .first();
    await receipt.locator("summary").first().click();
    const form = receipt.locator("form");
    await form
      .getByLabel("Reference number", { exact: true })
      .fill("RECEIPT-WRONG");
    await form.getByLabel("Goods value", { exact: true }).fill("100000.00");
    await form
      .getByLabel("Total quantity, if known", { exact: true })
      .fill("10");
    await form.getByRole("button", { name: "Add item", exact: true }).click();
    for (const [label, value] of [
      ["Item name", "Different goods"],
      ["Item code, if available", "OTHER-02"],
      ["Unit, such as pieces", "pieces"],
      ["Quantity", "10"],
    ])
      await form.getByLabel(label, { exact: true }).fill(value);
    await form
      .getByLabel("Goods value", { exact: true })
      .last()
      .fill("100000.00");
    let pending = page.waitForResponse(
      (r) => r.url().endsWith("/evidence") && r.request().method() === "POST",
    );
    await form
      .getByRole("button", { name: "Save receipt", exact: true })
      .click();
    let response = await pending;
    expect(response.ok(), await response.text()).toBe(true);
    invoice = (await response.json()).data;
    expect(invoice.findings.receipt).toBe("MISMATCH");
    await expect(page.locator(".match-grid").first()).toContainText(
      "Does not match",
    );
    const ims = page
      .locator("details")
      .filter({
        has: page.locator("summary", { hasText: "GST action guidance" }),
      })
      .first();
    await ims.locator("summary").first().click();
    await ims
      .getByRole("combobox", { name: "Reviewed action", exact: true })
      .selectOption("PENDING");
    await ims
      .getByLabel("Reason, at least 10 characters", { exact: true })
      .fill("Await correct delivered item evidence.");
    pending = page.waitForResponse(
      (r) => r.url().endsWith("/ims-review") && r.request().method() === "POST",
    );
    await ims
      .getByRole("button", { name: "Save GST review", exact: true })
      .click();
    response = await pending;
    expect(response.ok(), await response.text()).toBe(true);
    invoice = (await response.json()).data;
    expect(invoice.findings.ims_review.submission).toBe("NOT_SUBMITTED");
    await expect(ims.getByText(/Saved action: Keep pending/)).toBeVisible();
    const bank = page
      .locator("details")
      .filter({
        has: page.locator("summary", {
          hasText: "Demo bank — test the payment protection",
        }),
      })
      .first();
    await bank.locator("summary").first().click();
    pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/demo-bank-payment") &&
        r.request().method() === "POST",
    );
    await bank
      .getByRole("button", { name: "Try paying the balance", exact: true })
      .click();
    response = await pending;
    expect(response.ok(), await response.text()).toBe(true);
    expect((await response.json()).data.demo_bank.last_attempt.status).toBe(
      "BLOCKED",
    );
    await expect(
      bank.getByText("Payment blocked", { exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: `test-results/invoice-desk-${width}.png`,
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    for (const tab of ["Suppliers", "Finance", "Watch & outcomes"]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
  });
}
