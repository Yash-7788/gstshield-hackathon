import { openSection } from "./navigation.mjs";
// Controlled faults/bounds complement journeys.spec.mjs and the real performance workload.
import { test, expect } from "@playwright/test";
const api = "http://127.0.0.1:8027/api/v1";
const ws = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Usability fixture",
  role: "OWNER",
};
const reg = {
  id: "33333333-3333-4333-8333-333333333333",
  workspace_id: ws.id,
  gstin: "27ABCDE1234F1Z5",
  display_name: "Fixture company",
};
const id = "44444444-4444-4444-8444-444444444444";
const runId = "55555555-5555-4555-8555-555555555555";
const jobId = "66666666-6666-4666-8666-666666666666";
const row = {
  id,
  workspace_id: ws.id,
  registration_id: reg.id,
  period: "2024-05",
  kind: "INVOICE_REVIEW",
  state: "OPEN",
  version: 1,
  source: {
    recorded_tax: "180.00",
    invoice: { invoice_number: "PRIVATE-REFRESH-ROW" },
  },
  timeline: [],
  sources_current: true,
  assigned_to: null,
  due_at: null,
  reminded_at: null,
  case_id: null,
};
const run = {
  id: runId,
  registration_id: reg.id,
  period: "2024-05",
  state: "RUNNING",
  version: 1,
  revision: 1,
  job_id: jobId,
  sources_current: true,
  summary: null,
  provenance: "SYNTHETIC_DEMO",
};
const exact = (name) => ({ name, exact: true });
async function fixture(page, state = {}) {
  await page.clock.install();
  state.calls = [];
  await page.route(api + "/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    state.calls.push(path + url.search);
    if (state.handler && (await state.handler(route, url))) return;
    let data;
    if (path.endsWith("auth/session"))
      data = {
        user_id: "11111111-1111-4111-8111-111111111111",
        username: "alice",
        csrf_token: "fixture-memory-only",
        expires_at: new Date(Date.now() + 600000).toISOString(),
      };
    else if (path.endsWith("workspaces")) data = [ws];
    else if (path.endsWith("registrations")) data = [reg];
    else if (path.endsWith("actions")) {
      if (state.error)
        return route.fulfill({
          status: state.error,
          headers: {
            "Retry-After": "60",
            "Access-Control-Expose-Headers": "Retry-After",
          },
          json: {
            error: { message: "Synthetic rate limit", code: "RATE_LIMITED" },
          },
        });
      data = {
        actions: state.rows || [row],
        next_cursor: null,
        automation: { pending_sources: 0, error_code: null },
      };
    } else if (path.endsWith(id))
      data = { ...row, timeline: state.history || [] };
    else if (path.endsWith("imports"))
      data = { imports: [], next_cursor: null };
    else if (path.endsWith("runs"))
      data = { runs: [state.run || run], next_cursor: null };
    else if (path.endsWith(runId)) data = state.run || run;
    else if (path.endsWith(jobId))
      data = {
        id: jobId,
        state: state.run?.state === "FAILED" ? "FAILED" : "RUNNING",
        error_code:
          state.run?.state === "FAILED" ? "SYNTHETIC_JOB_FAILURE" : null,
      };
    else if (path.endsWith("results"))
      data = { results: [], next_cursor: null };
    else if (path.endsWith("artifacts"))
      data = { artifacts: [], next_cursor: null };
    else
      return route.fulfill({
        status: 404,
        json: { error: { message: "Synthetic unavailable record" } },
      });
    await route.fulfill({ json: { data } });
  });
  await page.goto("/#Sources");
  await page.getByLabel("Accounting month", { exact: true }).fill("2024-05");
}
async function queue(page) {
  await openSection(page, "Work queue");
  await expect(
    page.getByRole("button", exact("Open action")).first(),
  ).toBeVisible();
}
const calls = (state, suffix) =>
  state.calls.filter((path) => path.split("?")[0].endsWith(suffix)).length;

test("same-selection refresh retains an unsaved form; denial clears private data", async ({
  page,
}) => {
  const state = {};
  await fixture(page, state);
  await queue(page);
  await page.getByRole("button", exact("Open action")).click();
  await page
    .getByText("State, assignment and next review", { exact: true })
    .click();
  await page
    .getByLabel("Change reason", { exact: true })
    .fill("Unsaved human explanation");
  let entered, release;
  const waiting = new Promise((resolve) => (entered = resolve));
  const gate = new Promise((resolve) => (release = resolve));
  state.handler = async (route, url) => {
    if (!url.pathname.endsWith(id)) return false;
    entered();
    await gate;
    await route.fulfill({ json: { data: row } });
    return true;
  };
  await page.getByRole("button", exact("Refresh action")).click();
  await waiting;
  await expect(
    page.getByText("Refreshing saved records", { exact: false }),
  ).toBeVisible();
  await expect(page.getByLabel("Change reason", { exact: true })).toHaveValue(
    "Unsaved human explanation",
  );
  await expect(
    page.getByRole("button", exact("Save action state")),
  ).toBeDisabled();
  release();
  await expect(
    page.getByText("Refreshing saved records", { exact: false }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Change reason", { exact: true })).toHaveValue(
    "Unsaved human explanation",
  );
  state.handler = async (route, url) => {
    if (!url.pathname.endsWith(id)) return false;
    await route.fulfill({
      status: 403,
      json: { error: { message: "Access revoked" } },
    });
    return true;
  };
  await page.getByRole("button", exact("Refresh action")).click();
  await expect(page.getByRole("alert")).toContainText("Access revoked");
  await expect(page.getByLabel("Change reason", { exact: true })).toHaveCount(
    0,
  );
});

test("100-event history renders only on demand and every retained event remains reachable", async ({
  page,
}) => {
  const history = Array.from({ length: 100 }, (_, i) => ({
    id: String(i),
    kind: "NOTE",
    reason: `History event ${i}`,
    created_at: 1714500000 + i,
    snapshot: { reason: "x".repeat(1000), source: { ...ROW_PLACEHOLDER } },
  }));
  await fixture(page, { history });
  await queue(page);
  await page.getByRole("button", exact("Open action")).click();
  const box = page.locator("details").filter({
    has: page.locator("summary", { hasText: "Evidence and action history" }),
  });
  await expect(box.locator("article")).toHaveCount(0);
  await box.locator("summary").click();
  await expect(box.locator("article")).toHaveCount(20);
  for (const count of [40, 60, 80, 100]) {
    await box.getByRole("button", exact("Show more history")).click();
    await expect(box.locator("article")).toHaveCount(count);
  }
  await expect(
    box.getByText("History event 99", { exact: true }),
  ).toBeVisible();
  await expect(box.getByRole("button", exact("Show more history"))).toHaveCount(
    0,
  );
  await box.locator("summary").click();
  await expect(box.locator("article")).toHaveCount(0);
});
const ROW_PLACEHOLDER = {
  invoice_number: "SYNTHETIC",
  recorded_tax: "180.00",
  legal_eligibility: "NOT_DETERMINED",
};

test("processing stays below the default read budget and terminal job errors refresh once", async ({
  page,
}) => {
  const state = {};
  await fixture(page, state);
  await openSection(page, "Reconciliation");
  await page.getByRole("button", exact("Open comparison")).click();
  await expect(
    page.getByText("Processing job: Running", { exact: false }),
  ).toBeVisible();
  const initial = calls(state, runId);
  for (let i = 0; i < 12; i++) {
    const previous = calls(state, runId);
    await page.clock.runFor(5100);
    await expect.poll(() => calls(state, runId)).toBeGreaterThan(previous);
  }
  expect(calls(state, runId)).toBeGreaterThan(initial + 10);
  expect(calls(state, jobId)).toBe(1);
  expect(state.calls.length).toBeLessThan(60);
  state.run = { ...run, state: "FAILED", version: 2 };
  await page.clock.runFor(5100);
  await expect(
    page.getByText("SYNTHETIC_JOB_FAILURE", { exact: false }),
  ).toBeVisible();
  expect(calls(state, jobId)).toBe(2);
  const terminal = calls(state, runId);
  await page.clock.runFor(31000);
  expect(calls(state, runId)).toBe(terminal);
});

test("hidden-tab polling sleeps and resumes once without a catch-up burst", async ({
  page,
}) => {
  const state = {};
  await fixture(page, state);
  await queue(page);
  await page.evaluate(() => {
    window.testVisibility = "visible";
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => window.testVisibility,
    });
    window.testVisibility = "hidden";
    document.dispatchEvent(new Event("visibilitychange"));
  });
  const count = state.calls.length;
  await page.clock.runFor(61000);
  expect(state.calls.length).toBe(count);
  await page.evaluate(() => {
    window.testVisibility = "visible";
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.clock.runFor(100);
  await expect.poll(() => calls(state, "actions")).toBe(2);
  await expect.poll(() => calls(state, "workspaces")).toBe(2);
  await page.clock.runFor(100);
  expect(calls(state, "actions")).toBe(2);
});

test("rate-limited polling respects Retry-After instead of repeatedly retrying", async ({
  page,
}) => {
  const state = {};
  await fixture(page, state);
  await queue(page);
  state.error = 429;
  await page.clock.runFor(10100);
  await expect(page.getByRole("alert")).toContainText("Synthetic rate limit");
  expect(calls(state, "actions")).toBe(2);
  state.error = 0;
  await page.clock.runFor(58000);
  expect(calls(state, "actions")).toBe(2);
  await page.clock.runFor(2500);
  await expect.poll(() => calls(state, "actions")).toBe(3);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a late filter reply cannot replace the newest selection", async ({
  page,
}) => {
  const state = {};
  await fixture(page, state);
  await queue(page);
  let entered, release;
  const waiting = new Promise((resolve) => (entered = resolve));
  const gate = new Promise((resolve) => (release = resolve));
  state.handler = async (route, url) => {
    if (!url.pathname.endsWith("actions")) return false;
    if (url.searchParams.get("state") === "OPEN") {
      entered();
      await gate;
      await route
        .fulfill({
          json: {
            data: {
              actions: [
                {
                  ...row,
                  source: {
                    ...row.source,
                    invoice: { invoice_number: "OBSOLETE-FILTER-ROW" },
                  },
                },
              ],
              next_cursor: null,
              automation: { pending_sources: 0, error_code: null },
            },
          },
        })
        .catch(() => {});
      return true;
    }
    await route.fulfill({
      json: {
        data: {
          actions: [],
          next_cursor: null,
          automation: { pending_sources: 0, error_code: null },
        },
      },
    });
    return true;
  };
  await page.getByRole("combobox", exact("Action state")).selectOption("OPEN");
  await waiting;
  await page
    .getByRole("combobox", exact("Action state"))
    .selectOption("CLOSED");
  await expect(
    page.getByText("No saved records in this selection yet.", { exact: true }),
  ).toBeVisible();
  release();
  await page.clock.runFor(100);
  await expect(
    page.getByText("OBSOLETE-FILTER-ROW", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("PRIVATE-REFRESH-ROW", { exact: true }),
  ).toHaveCount(0);
});

test("mobile tables scroll within the page and keyboard navigation reaches main content", async ({
  page,
}) => {
  const state = {
    rows: Array.from({ length: 20 }, (_, i) => ({
      ...row,
      id: crypto.randomUUID(),
      source: {
        ...row.source,
        invoice: { invoice_number: "Invoice " + i + "-" + "x".repeat(200) },
      },
    })),
  };
  await fixture(page, state);
  await queue(page);
  await expect(page.getByRole("heading", exact("Work queue"))).toBeFocused();
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const table = page.getByRole("region", exact("Business actions table"));
    expect(await table.evaluate((e) => e.scrollWidth > e.clientWidth)).toBe(
      true,
    );
    await table.focus();
    await page.keyboard.press("ArrowRight");
    await expect
      .poll(() => table.evaluate((e) => e.scrollLeft))
      .toBeGreaterThan(0);
  }
  const hash = await page.evaluate(() => location.hash);
  await page.getByRole("link", exact("Skip to workspace content")).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", exact("Work queue"))).toBeFocused();
  expect(await page.evaluate(() => location.hash)).toBe(hash);
});

test("all 60 candidates remain reachable through 20-item pages", async ({
  page,
}) => {
  const resultId = "77777777-7777-4777-8777-777777777777";
  const candidates = Array.from({ length: 60 }, (_, i) => ({
    id: crypto.randomUUID(),
    original_invoice_number: "C" + i,
    score: "90.00",
    rank: i + 1,
    hard_gates_passed: true,
    currently_available: true,
    invoice_date: "2024-04-10",
    amount_differences: {},
    reason_codes: [],
  }));
  const result = {
    id: resultId,
    version: 1,
    canonical: {
      invoice_number: "P1",
      supplier_gstin: reg.gstin,
      total_tax: "-0.50",
    },
    status: "FUZZY_SUGGESTION",
    reason_codes: [],
    candidates,
    review_timeline: [],
  };
  const state = {
    run: { ...run, state: "COMPLETED" },
    handler: async (route, url) => {
      if (url.pathname.endsWith("/results")) {
        await route.fulfill({
          json: { data: { results: [result], next_cursor: null } },
        });
        return true;
      }
      if (url.pathname.endsWith(resultId)) {
        await route.fulfill({ json: { data: result } });
        return true;
      }
      return false;
    },
  };
  await fixture(page, state);
  await openSection(page, "Reconciliation");
  await page.getByRole("button", exact("Open comparison")).click();
  await expect(page.getByText("₹-0.50", { exact: true })).toBeVisible();
  await page.getByRole("button", exact("Open result")).click();
  const titles = page.locator("strong").filter({ hasText: /^Candidate C\d+$/ });
  await expect(titles).toHaveCount(20);
  await expect(
    page.getByRole("combobox", exact("Candidate")).locator("option"),
  ).toHaveCount(21);
  for (const number of [20, 40]) {
    await page.getByRole("button", exact("Next candidates")).click();
    await expect(
      page.getByText("Candidate C" + number, { exact: true }),
    ).toBeVisible();
    await expect(titles).toHaveCount(20);
  }
  await page
    .getByRole("combobox", exact("Candidate"))
    .selectOption(candidates[59].id);
  await expect(page.getByRole("combobox", exact("Candidate"))).toHaveValue(
    candidates[59].id,
  );
  await expect(
    page.getByRole("button", exact("Next candidates")),
  ).toBeDisabled();
  await page.getByRole("button", exact("First candidates")).click();
  await expect(page.getByRole("combobox", exact("Candidate"))).toHaveValue("");
});
