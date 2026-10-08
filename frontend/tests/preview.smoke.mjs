import { test, expect } from "@playwright/test";
test("built website signs in, uploads and confirms through configured local API under CSP", async ({
  page,
}) => {
  test.setTimeout(60000);
  const cspErrors = [];
  page.on("console", (m) => {
    if (/Content Security Policy|violates.*directive/i.test(m.text()))
      cspErrors.push(m.text());
  });
  const response = await page.goto("/#Sources");
  expect(response.headers()["content-security-policy"]).toContain(
    "http://127.0.0.1:8027",
  );
  await page.getByLabel("Username", { exact: true }).fill("alice");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-passphrase-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption({ label: "Synthetic demonstration · owner" });
  await page
    .getByRole("combobox", { name: "Registration", exact: true })
    .selectOption({ label: "Synthetic company · 27ABCDE1234F1Z5" });
  await page.getByLabel("Accounting month", { exact: true }).fill("2024-05");
  await page.getByLabel("Source file").setInputFiles({
    name: "preview.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "voucher_id,recipient_gstin,supplier_gstin,invoice_number,invoice_date,document_type,taxable_value,cgst,sgst,igst,cess,other_charges,round_off,gross_total\nV1,27ABCDE1234F1Z5,27PQRSX5678L1Z2,BUILT-001,2024-04-10,INVOICE,1000.00,90.00,90.00,0.00,0.00,0.00,0.00,1180.00",
    ),
  });
  await page
    .getByRole("button", { name: "Upload source", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Confirm source", exact: true }),
  ).toBeVisible({ timeout: 30000 });
  await page
    .getByRole("button", { name: "Confirm source", exact: true })
    .click();
  await expect(page.getByText("Ready", { exact: true }).first()).toBeVisible();
  expect(cspErrors).toEqual([]);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
});

test("built CSP blocks framing and unconfigured connections; shipped assets contain no canaries", async ({
  page,
}) => {
  const response = await page.goto("/");
  const headers = response.headers();
  expect(headers["cache-control"]).toBe("no-store");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["content-security-policy"]).toContain("object-src 'none'");
  const violations = [];
  page.on("console", (m) => {
    if (/violates|refused|blocked/i.test(m.text())) violations.push(m.text());
  });
  const blocked = await page.evaluate(async () => {
    try {
      await fetch("http://127.0.0.1:9/phase10-blocked");
      return false;
    } catch {
      return true;
    }
  });
  expect(blocked).toBe(true);
  expect(violations.some((v) => v.includes("connect-src"))).toBe(true);
  const framed = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname === "/" &&
      r.request().resourceType() === "document",
  );
  await page.evaluate(() => {
    const iframe = document.createElement("iframe");
    iframe.id = "security-frame";
    iframe.src = "/";
    document.body.append(iframe);
  });
  await framed;
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          document.querySelector("#security-frame").contentDocument === null,
      ),
    )
    .toBe(true);
  const { readdir, readFile } = await import("node:fs/promises");
  const paths = [
    "dist/index.html",
    ...(await readdir("dist/assets")).map((name) => "dist/assets/" + name),
  ];
  for (const path of paths) {
    expect(path).not.toMatch(/\.map$/);
    const content = await readFile(path, "utf8");
    expect(content).not.toContain("synthetic-secret-must-not-be-public");
    expect(content).not.toContain("synthetic-provider-secret-not-public");
    expect(content).not.toContain("synthetic-passphrase-only");
  }
});
