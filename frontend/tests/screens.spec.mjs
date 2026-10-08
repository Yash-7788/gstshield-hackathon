import { openSection } from "./navigation.mjs";
import { test, expect } from "@playwright/test";
const session = {
  user_id: "11111111-1111-4111-8111-111111111111",
  username: "alice",
  csrf_token: "synthetic-memory-token",
  expires_at: new Date(Date.now() + 600000).toISOString(),
};
const ws = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Synthetic screen fixture",
  role: "OWNER",
};
const registration = {
  id: "33333333-3333-4333-8333-333333333333",
  workspace_id: ws.id,
  gstin: "27ABCDE1234F1Z5",
  display_name: "Synthetic fixture",
};
async function mockScreens(page, role = "OWNER") {
  await page.route("http://127.0.0.1:8027/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data;
    if (path.endsWith("auth/session")) data = session;
    else if (path.endsWith("workspaces")) data = [{ ...ws, role }];
    else if (path.endsWith("registrations")) data = [registration];
    else if (path.endsWith("imports"))
      data = { imports: [], next_cursor: null };
    else if (path.endsWith("runs")) data = { runs: [], next_cursor: null };
    else if (path.endsWith("cases")) data = { cases: [], next_cursor: null };
    else if (path.endsWith("proposals"))
      data = { proposals: [], next_cursor: null };
    else if (path.endsWith("artifacts"))
      data = { artifacts: [], next_cursor: null };
    else if (path.endsWith("actions"))
      data = {
        actions: [],
        next_cursor: null,
        automation: {
          pending_sources: false,
          pending_due: false,
          last_error_code: null,
        },
      };
    else
      return route.fulfill({
        status: 404,
        json: { error: { message: "Synthetic missing screen resource" } },
      });
    await route.fulfill({ json: { data } });
  });
}
test("all six internal sections render empty states, navigation and mobile without overflow", async ({
  page,
}) => {
  await mockScreens(page);
  await page.goto("/#%malformed");
  await expect(
    page.getByRole("heading", { name: "Invoice desk", exact: true }),
  ).toBeVisible();
  for (const section of [
    "Reconciliation",
    "Cases & evidence",
    "Work queue",
    "Payment drafts",
    "Reports",
    "Sources",
  ]) {
    await openSection(page, section);
    await expect(
      page.getByRole("heading", { name: section, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("No saved records in this selection yet.").first(),
    ).toBeVisible();
  }
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Reports", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/internal-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "test-results/internal-desktop.png",
    fullPage: true,
  });
  await page.keyboard.press("Tab");
  expect(
    await page.evaluate(() => document.activeElement?.tagName !== "BODY"),
  ).toBe(true);
});
test("viewer has explicit read-only screens; unavailable data never shows success", async ({
  page,
}) => {
  await mockScreens(page, "VIEWER");
  await page.goto("/#Sources");
  await expect(
    page.getByText(
      "Financial records are read-only. Your approved shared-work actions remain available.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Upload source", exact: true }),
  ).toHaveCount(0);
  await openSection(page, "Payment drafts");
  await expect(
    page.getByText("Create a payment draft", { exact: true }),
  ).toHaveCount(0);
  await page.route("**/proposals?**", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { message: "Synthetic unavailable backend" } },
    }),
  );
  await page.getByRole("button", { name: "Refresh drafts" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Synthetic unavailable backend",
  );
  await expect(
    page.getByText("Saved. The backend record has been updated."),
  ).toHaveCount(0);
});
