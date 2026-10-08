import { test, expect, request } from "@playwright/test";
import { randomUUID } from "node:crypto";
const api = "http://127.0.0.1:8027/api/v1";
const origin = "http://127.0.0.1:3127";
const password = "synthetic-role-password";
const roles = {
  CA: "Tax and accounting reviewer",
  CFO: "Finance lead",
  CMA: "Cost and margin reviewer",
  CMO: "Marketing lead",
  CEO: "Business lead",
  COO: "Operations lead",
  CTO: "Technology lead",
};
let workspace, registration;
test.beforeAll(async () => {
  const owner = await request.newContext({
    extraHTTPHeaders: { Origin: origin },
  });
  const login = await owner.post(api + "/auth/login", {
    data: { username: "alice", password: "synthetic-passphrase-only" },
  });
  expect(login.status()).toBe(200);
  const csrf = (await login.json()).data.csrf_token;
  workspace = (await (await owner.get(api + "/workspaces")).json()).data.find(
    (w) => w.role === "OWNER",
  ).id;
  const base = api + "/workspaces/" + workspace;
  registration = (await (await owner.get(base + "/registrations")).json())
    .data[0].id;
  const existing = (await (await owner.get(base + "/product/team")).json()).data
    .members;
  for (const role of Object.keys(roles)) {
    if (existing.some((m) => m.username === "acceptance-" + role.toLowerCase()))
      continue;
    const member = await owner.post(base + "/product/team/members", {
      headers: { "X-CSRF-Token": csrf, "Idempotency-Key": randomUUID() },
      data: {
        username: "acceptance-" + role.toLowerCase(),
        password,
        display_name: role,
        roles: [role],
      },
    });
    expect(member.status(), await member.text()).toBe(200);
  }
  const currentBusiness = (
    await (
      await owner.get(
        base +
          "/product/business?registration_id=" +
          registration +
          "&period=2026-10",
      )
    ).json()
  ).data;
  const profile = await owner.post(base + "/product/business", {
    headers: { "X-CSRF-Token": csrf, "Idempotency-Key": randomUUID() },
    data: {
      registration_id: registration,
      period: "2026-10",
      expected_version: currentBusiness.version,
      profile: {
        business_name: "Synthetic role company",
        monthly_revenue: "1000000",
        monthly_profit: "180000",
        monthly_operating_cost: "820000",
        marketing_spend: "20000",
        attributed_sales: "100000",
      },
    },
  });
  expect(profile.status(), await profile.text()).toBe(200);
  await owner.dispose();
});
async function login(page, role) {
  await page.goto("/?portal=team#Shared%20process");
  await page
    .getByLabel("Username", { exact: true })
    .fill("acceptance-" + role.toLowerCase());
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Team desk", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".context")).toContainText(roles[role]);
  await page.getByLabel("Accounting month", { exact: true }).fill("2026-10");
}
for (const [role, name] of Object.entries(roles))
  test(
    role + " has one role, its own briefing and safe refresh",
    async ({ page }) => {
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await login(page, role);
      await expect(
        page.getByRole("combobox", { name: "Working as", exact: true }),
      ).toHaveCount(0);
      await expect(
        page.getByRole("link", { name: "Invoice desk", exact: true }),
      ).toHaveCount(["CA", "CFO"].includes(role) ? 1 : 0);
      await expect(
        page.getByRole("button", { name: "More tools", exact: true }),
      ).toHaveCount(["CA", "CFO"].includes(role) ? 1 : 0);
      await page.getByRole("link", { name: "Assistants", exact: true }).click();
      await expect(
        page.getByRole("heading", { name: name + " briefing", exact: true }),
      ).toBeVisible();
      const answer = page.waitForResponse(
        (r) =>
          r.url().includes("/product/assistants/") &&
          r.request().method() === "POST",
      );
      await page
        .getByRole("button", { name: "Ask about saved records", exact: true })
        .click();
      const response = await answer;
      expect(response.status()).toBe(200);
      await expect(
        page.getByText(
          "Briefing ready. Based on saved facts; no decision was changed.",
          { exact: true },
        ),
      ).toBeVisible();
      const data = (await response.json()).data;
      expect(data.role).toBe(role);
      await page.reload();
      await expect(
        page.getByRole("heading", { name: name + " briefing", exact: true }),
      ).toBeVisible();
      if (!["CA", "CFO"].includes(role)) {
        await page.goto("/#Shared%20process");
        await expect(
          page.getByRole("heading", { name: "Team desk", exact: true }),
        ).toBeVisible();
        await expect(
          page.getByRole("button", { name: /Start.*process/ }),
        ).toHaveCount(0);
      }
      await page.getByRole("button", { name: "Sign out", exact: true }).click();
      await expect(
        page.getByRole("button", { name: "Sign in", exact: true }),
      ).toBeVisible();
      await expect(page).not.toHaveURL(/#.+/);
      expect(errors).toEqual([]);
    },
  );

test("owner sees oversight, one-role setup and no accounting forms", async ({
  page,
}) => {
  await page.goto("/?portal=owner#Invoice%20desk");
  await page.getByLabel("Username", { exact: true }).fill("alice");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-passphrase-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Owner desk", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Invoice desk", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.locator("main input,main select,main textarea"),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "Team desk", exact: true }).click();
  await page.getByText("People and access", { exact: true }).click();
  await page.getByText("Create your team", { exact: true }).click();
  const form = page.locator(".team-formation form");
  await expect(form.getByLabel("Assigned role", { exact: true })).toHaveCount(
    1,
  );
  await form.getByLabel("Assigned role", { exact: true }).selectOption("CA");
  await form.getByLabel("Assigned role", { exact: true }).selectOption("CMA");
  await expect(form.getByLabel("Assigned role", { exact: true })).toHaveValue(
    "CMA",
  );
  await expect(form.getByRole("radio")).toHaveCount(0);
  await page.goto("/#Shared%20process");
  await expect(
    page.getByRole("heading", { name: "Owner desk", exact: true }),
  ).toBeVisible();
});

for (const width of [1280, 390])
  test(
    "guided invoice OCR and document proofs at " + width + "px",
    async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await login(page, "CA");
      await page
        .getByLabel("Accounting month", { exact: true })
        .fill("2024-05");
      await page
        .getByRole("link", { name: "Invoice desk", exact: true })
        .click();
      if (
        !(await page
          .getByLabel("Invoice PDF or photo", { exact: true })
          .isVisible())
      )
        await page
          .getByRole("button", { name: "Upload an invoice", exact: true })
          .click();
      await page
        .getByLabel("Invoice PDF or photo", { exact: true })
        .setInputFiles({
          name: "synthetic-" + width + ".pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from("%PDF-controlled-OCR-fixture-" + width),
        });
      await page
        .getByLabel("Allow Google AI to read this invoice.", { exact: true })
        .check();
      await page
        .getByRole("button", { name: "Read invoice", exact: true })
        .click();
      await expect(
        page.getByRole("heading", {
          name: "Confirm what was read",
          exact: true,
        }),
      ).toBeVisible();
      const confirmation = page.locator("section.panel").filter({
        has: page.getByRole("heading", {
          name: "Confirm what was read",
          exact: true,
        }),
      });
      await expect(confirmation.locator("input,select,textarea")).toHaveCount(
        0,
      );
      await page
        .getByRole("button", { name: "Confirm details", exact: true })
        .click();
      for (const kind of ["order", "delivery"]) {
        const label =
          kind === "order" ? "Order PDF or photo" : "Delivery PDF or photo";
        await page.getByLabel(label, { exact: true }).setInputFiles({
          name: kind + ".pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from("%PDF-controlled-" + kind),
        });
        await page
          .getByLabel("Allow Google AI to read this supporting document.", {
            exact: true,
          })
          .check();
        await page
          .getByRole("button", {
            name: "Read supporting document",
            exact: true,
          })
          .click();
        const confirm = page.getByRole("button", {
          name: "Confirm " + kind,
          exact: true,
        });
        await expect(confirm).toBeVisible();
        const proof = page.locator("form").filter({ has: confirm });
        await expect(proof.locator("input,select,textarea")).toHaveCount(0);
        await confirm.click();
      }
      await expect(
        page.getByRole("heading", {
          name: "Order and delivery checks complete",
          exact: true,
        }),
      ).toBeVisible();
      await expect(
        page.getByRole("heading", {
          name: "Add the month's GST statement",
          exact: true,
        }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
      ).toBe(true);
      await page.screenshot({
        path: "test-results/guided-invoice-" + width + ".png",
        fullPage: true,
      });
    },
  );

test("CFO cannot correct or confirm an unreviewed invoice", async ({
  page,
}) => {
  await login(page, "CA");
  await page.getByLabel("Accounting month", { exact: true }).fill("2024-05");
  await page.getByRole("link", { name: "Invoice desk", exact: true }).click();
  if (
    !(await page
      .getByLabel("Invoice PDF or photo", { exact: true })
      .isVisible())
  )
    await page
      .getByRole("button", { name: "Upload an invoice", exact: true })
      .click();
  await page
    .getByLabel("Invoice PDF or photo", { exact: true })
    .setInputFiles({
      name: "pending-finance.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-controlled-pending-finance"),
    });
  await page
    .getByLabel("Allow Google AI to read this invoice.", { exact: true })
    .check();
  await page.getByRole("button", { name: "Read invoice", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Confirm what was read", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await login(page, "CFO");
  await page.getByLabel("Accounting month", { exact: true }).fill("2024-05");
  await page.getByRole("link", { name: "Invoice desk", exact: true }).click();
  await page
    .getByRole("button", { name: /Confirm extracted details/ })
    .first()
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Accounting confirmation pending",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Confirm details", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Correct a detail", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.locator("main input,main select,main textarea"),
  ).toHaveCount(0);
});
