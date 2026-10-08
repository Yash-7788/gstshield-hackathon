import { openSection } from "./navigation.mjs";
import { test, expect } from "@playwright/test";
async function navigate(page, name) {
  await openSection(page, name);
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
async function login(page, username, password) {
  await page.goto("/?portal=team");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Team desk", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Accounting month", { exact: true }).fill("2025-03");
}
test("landing entry, business privacy, repeated CA accounts and shared work use real APIs", async ({
  page,
  browser,
}) => {
  test.setTimeout(180000);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/landing.html");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const choices = page.getByRole("dialog");
  await expect(choices).toBeVisible();
  await choices.getByRole("link", { name: /Business owner/ }).click();
  await page.getByLabel("Username", { exact: true }).fill("alice");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-passphrase-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Owner desk", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption({ label: "Synthetic demonstration · owner" });
  await page
    .getByRole("combobox", { name: "Registration", exact: true })
    .selectOption({ label: "Synthetic company · 27ABCDE1234F1Z5" });
  await page.getByLabel("Accounting month", { exact: true }).fill("2025-03");
  await page
    .getByText("Enter or update business details", { exact: true })
    .click();
  await page
    .getByLabel("Business name", { exact: true })
    .fill("Browser Demo Pumps");
  await page
    .getByLabel("Revenue this month (₹)", { exact: true })
    .fill("1000000");
  await page.getByLabel("Number of people", { exact: true }).fill("2");
  await page.getByRole("button", { name: "Add a person", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("PRIVATE SALARY PERSON");
  await page.getByLabel("Role", { exact: true }).fill("Warehouse");
  await page.getByLabel("Monthly salary (₹)", { exact: true }).fill("25000");
  const saved = page.waitForResponse(
    (r) =>
      r.url().endsWith("/product/business") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Save business details", exact: true })
    .click();
  expect((await saved).ok()).toBe(true);
  await navigate(page, "Team desk");
  await page.getByText("Add a team account", { exact: true }).click();
  const usernames = [];
  const prefix = "browserca" + Date.now().toString().slice(-7);
  const memberForm = page.locator("form").filter({
    has: page.getByRole("button", {
      name: "Create team account",
      exact: true,
    }),
  });
  for (const n of [1, 2]) {
    const username = prefix + n;
    usernames.push(username);
    await memberForm
      .getByLabel("Person's name", { exact: true })
      .fill("Browser CA " + n);
    await memberForm.getByLabel("Username", { exact: true }).fill(username);
    await memberForm
      .getByLabel("Initial password (12 characters or more)", { exact: true })
      .fill("synthetic-team-password");
    const created = page.waitForResponse(
      (r) =>
        r.url().endsWith("/product/team/members") &&
        r.request().method() === "POST",
    );
    await memberForm
      .getByRole("button", { name: "Create team account", exact: true })
      .click();
    expect((await created).ok()).toBe(true);
    await expect(
      page.getByRole("row").filter({ hasText: username }),
    ).toBeVisible();
  }
  await navigate(page, "Assistants");
  await page
    .getByRole("combobox", { name: "Your assistant", exact: true })
    .selectOption("CMO");
  await page
    .getByRole("button", { name: "Ask about saved records", exact: true })
    .click();
  await expect(
    page.getByText("reported marketing spend is unknown.", { exact: true }),
  ).toBeVisible();
  const ca1 = await browser.newContext();
  const ca2 = await browser.newContext();
  try {
    const first = await ca1.newPage();
    const second = await ca2.newPage();
    await login(first, usernames[0], "synthetic-team-password");
    await first
      .getByLabel("What changed, and what does the next person need?", {
        exact: true,
      })
      .fill("Shared browser CA review: request delivery evidence.");
    await first
      .getByRole("button", { name: "Share update", exact: true })
      .click();
    await expect(
      first.getByText("Shared browser CA review: request delivery evidence.", {
        exact: true,
      }),
    ).toBeVisible();
    await login(second, usernames[1], "synthetic-team-password");
    await expect(
      second.getByText("Shared browser CA review: request delivery evidence.", {
        exact: true,
      }),
    ).toBeVisible();
    await navigate(second, "Owner desk");
    await expect(
      second.getByText(
        "Employee names and individual salaries are visible only to the owner.",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      second.getByText("PRIVATE SALARY PERSON", { exact: true }),
    ).toHaveCount(0);
    await navigate(second, "Assistants");
    const approved = await second
      .getByRole("combobox", { name: "Your assistant", exact: true })
      .locator("option")
      .allTextContents();
    expect(approved).toHaveLength(1);
    expect(approved[0]).toContain("CA");
    for (const screen of [
      "Team desk",
      "Owner desk",
      "Shared process",
      "Assistants",
      "Today",
    ]) {
      await navigate(second, screen);
      await second.setViewportSize({ width: 390, height: 844 });
      expect(
        await second.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
  } finally {
    await ca1.close();
    await ca2.close();
  }
  expect(errors).toEqual([]);
});

test("approved roles show focused desks and closed supporting panels make no requests", async ({
  page,
}) => {
  await page.goto("/?portal=team");
  await page.getByLabel("Username", { exact: true }).fill("alice");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-passphrase-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("heading", { name: "Team desk", exact: true }).waitFor();
  await page
    .getByRole("combobox", { name: "Workspace", exact: true })
    .selectOption({ label: "Synthetic demonstration · owner" });
  await page
    .getByRole("combobox", { name: "Registration", exact: true })
    .selectOption({ label: "Synthetic company · 27ABCDE1234F1Z5" });
  await page.getByLabel("Accounting month", { exact: true }).fill("2025-03");
  await openSection(page, "Owner desk");
  await page
    .getByText("Enter or update business details", { exact: true })
    .click();
  await page
    .getByLabel("Marketing spend this month (₹)", { exact: true })
    .fill("10000");
  await page
    .getByLabel("Sales attributed to marketing (₹)", { exact: true })
    .fill("40000");
  const saved = page.waitForResponse(
    (r) =>
      r.url().endsWith("/product/business") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Save business details", exact: true })
    .click();
  expect((await saved).ok()).toBe(true);

  const role = page.getByRole("combobox", { name: "Working as", exact: true });
  await role.selectOption("CMO");
  await expect(
    page.getByRole("heading", {
      name: "See what comes back.",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("₹10,000.00", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({
    path: "../output/verification/corrected-cmo-desktop.png",
    fullPage: true,
  });
  const marketingCanvas = await page
    .locator(".app")
    .evaluate((e) => getComputedStyle(e).backgroundColor);

  const nav = page.getByRole("navigation", {
    name: "Workspace sections",
    exact: true,
  });
  await expect(
    nav.getByRole("link", { name: "Payment drafts", exact: true }),
  ).toBeHidden();
  await openSection(page, "Assistants");
  await expect(
    page.getByRole("combobox", { name: "Your assistant", exact: true }),
  ).toHaveValue("CMO");
  await role.selectOption("CA");
  await expect(
    page.getByRole("heading", {
      name: "The review desk.",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    nav.getByRole("link", { name: "Invoice desk", exact: true }),
  ).toBeVisible();
  const reviewCanvas = await page
    .locator(".app")
    .evaluate((e) => getComputedStyle(e).backgroundColor);
  expect(reviewCanvas).not.toBe(marketingCanvas);
  expect(
    await page
      .locator(".layout > main")
      .evaluate((e) => getComputedStyle(e).backgroundColor),
  ).toBe("rgba(0, 0, 0, 0)");
  await expect(
    nav.getByRole("link", { name: "Payment drafts", exact: true }),
  ).toBeHidden();
  for (const width of [1440, 1280, 390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const position = await page.locator(".workspace-nav").evaluate((e) => ({
      bottom: e.getBoundingClientRect().bottom,
      width: e.getBoundingClientRect().width,
    }));
    const mainTop = await page
      .locator(".layout > main")
      .evaluate((e) => e.getBoundingClientRect().top);
    expect(position.bottom).toBeLessThanOrEqual(mainTop + 1);
    await page.screenshot({
      path: `../output/verification/corrected-ca-${width}.png`,
      fullPage: true,
    });
  }
  const directoryReads = [];
  page.on("request", (r) => {
    if (/product\/(schemes|competitors)|passports\?/.test(r.url()))
      directoryReads.push(r.url());
  });
  await role.selectOption("OWNER");
  await page
    .getByRole("heading", { name: "Owner desk", exact: true })
    .waitFor();
  await page.waitForTimeout(300);
  expect(directoryReads).toEqual([]);
  await page
    .getByText("Government finance schemes to discuss with your lender", {
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("columnheader", { name: "Scheme", exact: true }),
  ).toBeVisible();
  expect(directoryReads.some((u) => u.includes("product/schemes"))).toBe(true);
});
