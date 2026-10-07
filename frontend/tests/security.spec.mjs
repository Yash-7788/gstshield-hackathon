import { test, expect } from "@playwright/test";
const api = "http://127.0.0.1:8027/api/v1";
async function signIn(page, username = "alice") {
  await page.goto("/#Sources");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-passphrase-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Sources", exact: true }),
  ).toBeVisible();
}
test("real imported HTML-shaped text stays inert and logout isolates the next user", async ({
  page,
  context,
}) => {
  await signIn(page);
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption({ label: "Synthetic demonstration · owner" });
  await page.getByLabel("Accounting month", { exact: true }).fill("2024-08");
  const workspace = await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .inputValue();
  const hostile = "<img src=/phase10-xss onerror=alert(1)>";
  const dialogs = [];
  const unsafe = [];
  page.on("dialog", async (d) => {
    dialogs.push(d.message());
    await d.dismiss();
  });
  page.on("request", (r) => {
    if (r.url().includes("/phase10-xss")) unsafe.push(r.url());
  });
  const keys = [
    "voucher_id",
    "recipient_gstin",
    "supplier_gstin",
    "invoice_number",
    "invoice_date",
    "document_type",
    "taxable_value",
    "cgst",
    "sgst",
    "igst",
    "cess",
    "other_charges",
    "round_off",
    "gross_total",
  ];
  const values = [
    "PHASE10",
    "27ABCDE1234F1Z5",
    "27PQRSX5678L1Z2",
    hostile,
    "2024-07-10",
    "INVOICE",
    "1000.00",
    "90.00",
    "90.00",
    "0.00",
    "0.00",
    "0.00",
    "0.00",
    "1180.00",
  ];
  await page.getByLabel("Source file").setInputFiles({
    name: "html-shaped-text.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      keys.join(",") +
        "\n" +
        values.map((v) => '"' + v.replaceAll('"', '""') + '"').join(","),
    ),
  });
  await page
    .getByRole("button", { name: "Upload source", exact: true })
    .click();
  await expect(page.getByText("View row", { exact: true }).first()).toBeVisible(
    { timeout: 30000 },
  );
  await page.getByText("View row", { exact: true }).first().click();
  await expect(page.getByText(hostile, { exact: true }).last()).toBeVisible();
  expect(await page.locator('img[src="/phase10-xss"]').count()).toBe(0);
  expect(dialogs).toEqual([]);
  expect(unsafe).toEqual([]);
  const cookies = (await context.cookies(api)).filter(
    (c) => c.name === "gstshield_session",
  );
  expect(cookies).toHaveLength(1);
  expect(cookies[0].httpOnly).toBe(true);
  expect(cookies[0].sameSite).toBe("Strict");
  expect(cookies[0].path).toBe("/api/v1");
  const storage = await page.evaluate(() => ({
    local: { ...localStorage },
    session: { ...sessionStorage },
    cookie: document.cookie,
  }));
  expect(storage.local).toEqual({});
  expect(storage.cookie).not.toContain("gstshield_session");
  expect(JSON.stringify(storage)).not.toContain(hostile);
  expect(JSON.stringify(storage)).not.toContain(cookies[0].value);
  expect(JSON.stringify(storage)).not.toContain("csrf_token");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByText("Signed out.", { exact: true })).toBeVisible();
  expect(
    (await page.request.get(`${api}/workspaces/${workspace}/imports`)).status(),
  ).toBe(401);
  await page.getByLabel("Username", { exact: true }).fill("bob");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-passphrase-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("combobox", { name: "Workspace", exact: true }),
  ).toContainText("Other workspace");
  expect(
    (await page.request.get(`${api}/workspaces/${workspace}/imports`)).status(),
  ).toBe(404);
  await expect(page.getByText(hostile, { exact: true })).toHaveCount(0);
});
test("real backend rejects missing CSRF and cross-site logout without ending the session", async ({
  page,
}) => {
  await signIn(page);
  const denied = await page.evaluate(async (api) => {
    const response = await fetch(api + "/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    return { status: response.status, body: await response.json() };
  }, api);
  expect(denied.status).toBe(403);
  expect(denied.body.error.code).toBe("CSRF_INVALID");
  const stillActive = await page.request.get(api + "/auth/session");
  expect(stillActive.ok()).toBe(true);
  await page.goto("http://localhost:3000");
  const blocked = page.waitForResponse(
    (r) => r.url() === api + "/auth/logout" && r.request().method() === "POST",
  );
  const browserResult = page.evaluate(async (api) => {
    try {
      const response = await fetch(api + "/auth/logout", {
        method: "POST",
        credentials: "include",
      });
      return response.status;
    } catch {
      return "blocked";
    }
  }, api);
  expect((await blocked).status()).toBe(401);
  expect([401, "blocked"]).toContain(await browserResult);
  const foreign = await page.request.post(api + "/auth/logout", {
    headers: { Origin: "http://untrusted.invalid" },
  });
  expect(foreign.status()).toBe(403);
  expect((await page.request.get(api + "/auth/session")).ok()).toBe(true);
});
