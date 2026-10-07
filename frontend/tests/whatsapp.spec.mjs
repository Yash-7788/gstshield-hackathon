// Controlled channel replies test browser behavior; the first check uses the real local API.
import { test, expect } from "@playwright/test";
const exact = (name) => ({ name, exact: true });
const ws = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Channel fixture",
  role: "OWNER",
};
const reg = {
  id: "33333333-3333-4333-8333-333333333333",
  workspace_id: ws.id,
  gstin: "27ABCDE1234F1Z5",
  display_name: "Fixture",
};
const linked = {
  id: "44444444-4444-4444-8444-444444444444",
  workspace_id: ws.id,
  registration_id: reg.id,
  period: "2024-05",
  masked_phone: "******3210",
  version: 3,
  consent_alerts: false,
  active: true,
};
async function fixture(page, state) {
  await page.clock.install();
  await page.route("http://127.0.0.1:8027/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let data;
    if (path.endsWith("auth/session"))
      data = {
        user_id: "11111111-1111-4111-8111-111111111111",
        username: "alice",
        csrf_token: "synthetic-memory-only",
        expires_at: new Date(Date.now() + 600000).toISOString(),
      };
    else if (path.endsWith("workspaces")) data = [ws];
    else if (path.endsWith("registrations")) data = [reg];
    else if (path.endsWith("imports"))
      data = { imports: [], next_cursor: null };
    else if (path.endsWith("whatsapp/link-code"))
      data = {
        code: "ABCD2345EFGH",
        expires_at:
          Math.floor((await page.evaluate(() => Date.now())) / 1000) + 30,
        registration_id: reg.id,
        period: "2024-05",
      };
    else if (path.endsWith("whatsapp/context")) {
      state.context = request.postDataJSON();
      state.link = {
        ...state.link,
        ...state.context,
        version: state.link.version + 1,
      };
      data = {
        enabled: true,
        sending_enabled: false,
        link: state.link,
        deliveries: [],
        remaining_send_budget: 0,
        physical_phone_verified: false,
      };
    } else if (path.endsWith("whatsapp/unlink")) {
      state.unlink = request.postDataJSON();
      state.link = null;
      data = {
        enabled: true,
        sending_enabled: false,
        link: null,
        deliveries: [],
        remaining_send_budget: 0,
        physical_phone_verified: false,
      };
    } else if (path.endsWith("whatsapp")) {
      if (state.denied)
        return route.fulfill({
          status: 403,
          json: { error: { message: "Phone access no longer available" } },
        });
      data = {
        enabled: true,
        sending_enabled: false,
        link: state.link || null,
        deliveries: [],
        remaining_send_budget: 0,
        physical_phone_verified: false,
      };
    } else
      return route.fulfill({
        status: 404,
        json: { error: { message: "Synthetic missing route" } },
      });
    return route.fulfill({ json: { data } });
  });
  await page.goto("/#Sources");
  await page
    .getByLabel("Accounting month", exact("Accounting month"))
    .fill("2024-05");
  await page.getByRole("link", exact("WhatsApp")).click();
}
test("real default channel stays disabled while website sources remain usable", async ({
  page,
}) => {
  await page.goto("/#Sources");
  await page.getByLabel("Username", exact("Username")).fill("alice");
  await page
    .getByLabel("Password", exact("Password"))
    .fill("synthetic-passphrase-only");
  await page.getByRole("button", exact("Sign in")).click();
  await page.getByRole("combobox", exact("Workspace")).selectOption({
    label: "Synthetic demonstration · owner",
  });
  await page.getByRole("link", exact("WhatsApp")).click();
  await expect(
    page.getByText("WhatsApp is disabled.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", exact("Generate one-use link code")),
  ).toHaveCount(0);
  await expect(
    page.getByText("Physical-phone verification is still pending.", {
      exact: false,
    }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/whatsapp-mobile.png",
    fullPage: true,
  });
  await page.getByRole("link", exact("Sources")).click();
  await expect(page.getByRole("button", exact("Upload source"))).toBeVisible();
});
test("one-use code expires and permission loss clears it without browser storage", async ({
  page,
}) => {
  const state = {};
  await fixture(page, state);
  await page.getByRole("button", exact("Generate one-use link code")).click();
  await expect(
    page.getByText("LINK ABCD2345EFGH", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    ),
  ).not.toContain("ABCD2345EFGH");
  await page.clock.runFor(31000);
  await expect(
    page.getByText("LINK ABCD2345EFGH", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", exact("Generate one-use link code")).click();
  await expect(
    page.getByText("LINK ABCD2345EFGH", { exact: true }),
  ).toBeVisible();
  state.denied = true;
  await page.getByRole("button", exact("Check linked status")).click();
  await expect(page.getByRole("alert")).toContainText(
    "Phone access no longer available",
  );
  await expect(
    page.getByText("LINK ABCD2345EFGH", { exact: true }),
  ).toHaveCount(0);
});
test("context and unlink use current link versions; zero budget has clear feedback", async ({
  page,
}) => {
  const state = { link: { ...linked } };
  await fixture(page, state);
  await expect(
    page.getByRole("heading", { name: "Linked phone" }),
  ).toBeVisible();
  await expect(
    page.getByText("Outbound sending is paused", { exact: false }),
  ).toBeVisible();
  await page
    .getByLabel("Allow recorded review reminders", { exact: false })
    .check();
  await page
    .getByRole("button", exact("Use selected registration and month"))
    .click();
  await expect.poll(() => state.link.version).toBe(4);
  expect(state.context).toEqual({
    registration_id: reg.id,
    period: "2024-05",
    expected_version: 3,
    consent_alerts: true,
  });
  await expect(
    page.getByRole("button", exact("Unlink phone and revoke report links")),
  ).toBeEnabled();
  await page
    .getByRole("button", exact("Unlink phone and revoke report links"))
    .click();
  await expect(
    page.getByRole("button", exact("Generate one-use link code")),
  ).toBeVisible();
  expect(state.unlink).toEqual({ expected_version: 4 });
});
