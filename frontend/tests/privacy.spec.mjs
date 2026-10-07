// Synthetic fault replies deliberately isolate browser privacy behavior.
// The separate journeys and preview suite exercise the real backend.
import { test, expect } from "@playwright/test";
const api = "http://127.0.0.1:8027/api/v1";
const ws = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Privacy fixture",
  role: "OWNER",
};
const reg = {
  id: "33333333-3333-4333-8333-333333333333",
  workspace_id: ws.id,
  gstin: "27ABCDE1234F1Z5",
  display_name: "Private registration",
};
const action = {
  id: "44444444-4444-4444-8444-444444444444",
  registration_id: reg.id,
  period: "2024-05",
  kind: "MISSING_SUPPLIER_INVOICE",
  state: "OPEN",
  source: {
    recorded_tax: "180.00",
    invoice: { invoice_number: "PRIVATE-REVOCATION-ROW" },
  },
  timeline: [],
  sources_current: true,
};
async function fixture(page, state) {
  await page.clock.install();
  await page.route(api + "/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data;
    if (path.endsWith("auth/session"))
      data = {
        user_id: "11111111-1111-4111-8111-111111111111",
        username: "alice",
        csrf_token: "synthetic-memory-token",
        expires_at: new Date(Date.now() + 600000).toISOString(),
      };
    else if (path.endsWith("workspaces"))
      data = [{ ...ws, role: state.role || "OWNER" }];
    else if (path.endsWith("registrations")) data = [reg];
    else if (path.endsWith("actions")) {
      if (state.denied)
        return route.fulfill({
          status: 404,
          json: { error: { message: "Access no longer available" } },
        });
      data = {
        actions: [action],
        next_cursor: null,
        automation: { pending_sources: 0, error_code: null },
      };
    } else if (path.endsWith(action.id)) data = action;
    else if (path.endsWith("55555555-5555-4555-8555-555555555555"))
      data = {
        id: "55555555-5555-4555-8555-555555555555",
        kind: "EVIDENCE_PDF",
        state: "READY",
        provenance: "USER_UPLOADED",
        sources_current: true,
        filename:
          "gstshield-evidence_pdf-55555555-5555-4555-8555-555555555555.pdf",
      };
    else if (path.endsWith("artifacts"))
      data = { artifacts: [], next_cursor: null };
    else if (path.endsWith("imports"))
      data = { imports: [], next_cursor: null };
    else if (path.endsWith("runs")) data = { runs: [], next_cursor: null };
    else
      return route.fulfill({
        status: 404,
        json: { error: { message: "Synthetic missing resource" } },
      });
    return route.fulfill({ json: { data } });
  });
  await page.goto("/#Sources");
  await page.getByLabel("Accounting month", { exact: true }).fill("2024-05");
}
test("denied queue polling clears private rows and the open detail", async ({
  page,
}) => {
  const state = {};
  await fixture(page, state);
  await page.getByRole("link", { name: "Work queue", exact: true }).click();
  await expect(
    page.getByText("PRIVATE-REVOCATION-ROW", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open action", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Tracked business action" }),
  ).toBeVisible();
  state.denied = true;
  await page.clock.runFor(10100);
  await expect(page.getByRole("alert")).toContainText(
    "Access no longer available",
  );
  await expect(
    page.getByText("PRIVATE-REVOCATION-ROW", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Tracked business action" }),
  ).toHaveCount(0);
});
test("membership refresh removes privileged controls after role changes", async ({
  page,
}) => {
  const state = {};
  await fixture(page, state);
  await expect(
    page.getByRole("button", { name: "Upload source", exact: true }),
  ).toHaveCount(1);
  state.role = "VIEWER";
  await page.clock.runFor(15100);
  await expect(page.getByText("You have read-only access.")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Upload source", exact: true }),
  ).toHaveCount(0);
});
test("report lookup rejects URL-shaped IDs without making a request", async ({
  page,
}) => {
  await fixture(page, {});
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await page
    .getByText("Find a report by its saved ID", { exact: true })
    .click();
  const calls = [];
  page.on("request", (r) => {
    if (r.url().includes("/artifacts/")) calls.push(r.url());
  });
  await page
    .getByLabel("Report ID", { exact: true })
    .fill("%2e%2e/auth/session");
  await page.getByRole("button", { name: "Find report", exact: true }).click();
  expect(
    await page
      .getByLabel("Report ID", { exact: true })
      .evaluate((e) => e.validity.patternMismatch),
  ).toBe(true);
  expect(calls).toEqual([]);
});

test("leaving report context aborts the pending download before file exposure", async ({
  page,
}) => {
  await fixture(page, {});
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await page
    .getByText("Find a report by its saved ID", { exact: true })
    .click();
  await page
    .getByLabel("Report ID", { exact: true })
    .fill("55555555-5555-4555-8555-555555555555");
  await page.getByRole("button", { name: "Find report", exact: true }).click();
  const downloads = [];
  page.on("download", (d) => downloads.push(d));
  let release;
  let entered;
  const waiting = new Promise((r) => (entered = r));
  const gate = new Promise((r) => (release = r));
  await page.route("**/artifacts/*/download", async (route) => {
    entered();
    await gate;
    await route
      .fulfill({ body: "%PDF-synthetic", contentType: "application/pdf" })
      .catch(() => {});
  });
  await page
    .getByRole("button", { name: "Download private report", exact: true })
    .click();
  await waiting;
  const cancelled = page.waitForEvent("requestfailed", {
    predicate: (r) => r.url().endsWith("/download"),
  });
  await page.getByLabel("Accounting month", { exact: true }).fill("2024-06");
  await cancelled;
  release();
  await expect(
    page.getByRole("button", { name: "Download private report", exact: true }),
  ).toHaveCount(0);
  expect(downloads).toEqual([]);
});
