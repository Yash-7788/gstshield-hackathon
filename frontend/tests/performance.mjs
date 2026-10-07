// Opt-in, isolated real-HTTP browser measurement; never uses presenter data.
import { test, expect } from "@playwright/test";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { cpus, totalmem } from "node:os";
import { spawnSync } from "node:child_process";
import { readFile, readdir } from "node:fs/promises";
const origin = "http://127.0.0.1:8027";
const ROW = {
  voucher_id: "V1",
  recipient_gstin: "27ABCDE1234F1Z5",
  supplier_gstin: "27PQRSX5678L1Z2",
  invoice_number: "INV-1",
  invoice_date: "2024-04-10",
  document_type: "INVOICE",
  taxable_value: "1000.00",
  cgst: "90.00",
  sgst: "90.00",
  igst: "0.00",
  cess: "0.00",
  other_charges: "0.00",
  round_off: "0.00",
  gross_total: "1180.00",
};
const sections = [
  "Sources",
  "Reconciliation",
  "Cases & evidence",
  "Work queue",
  "Payment drafts",
  "Reports",
];
const exact = (name) => ({ name, exact: true });
async function paint(page) {
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
}
async function measure(page, steps, name, work) {
  const start = performance.now();
  await work();
  await paint(page);
  console.log("Measured: " + name);
  steps.push({
    name,
    elapsed_ms: Math.round((performance.now() - start) * 100) / 100,
  });
}
async function section(page, name) {
  await page.getByRole("link", exact(name)).click();
  await expect(page.getByRole("heading", exact(name))).toBeVisible();
}
async function send(page, suffix, click) {
  const wait = page.waitForResponse(
    (r) =>
      r.url().split("?")[0].endsWith(suffix) &&
      ["POST", "PATCH"].includes(r.request().method()),
  );
  await click();
  const response = await wait;
  expect(response.ok(), await response.text()).toBe(true);
  return (await response.json()).data;
}
async function get(page, base, suffix) {
  const response = await page.request.get(origin + base + suffix);
  expect(response.ok(), await response.text()).toBe(true);
  return (await response.json()).data;
}
function csv(count, portal) {
  const keys = Object.keys(ROW);
  return (
    keys.join(",") +
    "\n" +
    Array.from({ length: count }, (_, i) => {
      const number =
        "INV-" +
        createHash("sha256")
          .update(String(i))
          .digest("hex")
          .slice(0, 24)
          .toUpperCase();
      const row = {
        ...ROW,
        voucher_id: "V" + i,
        invoice_number:
          portal && i % 20 === 0 ? number.replace("-", "/") : number,
      };
      return keys
        .map((k) => '"' + row[k].replaceAll('"', '""') + '"')
        .join(",");
    }).join("\n")
  );
}
async function upload(page, steps, count, kind) {
  await section(page, "Sources");
  const form = page
    .locator("form")
    .filter({ has: page.getByRole("button", exact("Upload source")) });
  await form.getByRole("combobox", exact("Source kind")).selectOption(kind);
  await form.getByLabel("Source file", { exact: true }).setInputFiles({
    name: "synthetic.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv(count, kind === "PORTAL_2B")),
  });
  let item;
  await measure(page, steps, kind + " upload receipt", async () => {
    item = await send(page, "/imports", () =>
      form.getByRole("button", exact("Upload source")).click(),
    );
    await expect(
      page.getByRole("heading", exact("Source preview")),
    ).toBeVisible();
  });
  await measure(page, steps, kind + " parsed preview", async () => {
    await expect(page.getByRole("button", exact("Confirm source"))).toBeVisible(
      { timeout: 30000 },
    );
    await expect(page.getByText("View row", { exact: true })).toHaveCount(20);
  });
  await measure(page, steps, kind + " confirmation", async () => {
    await send(page, `/imports/${item.id}/confirm`, () =>
      page.getByRole("button", exact("Confirm source")).click(),
    );
    await expect(page.getByRole("button", exact("Confirm source"))).toHaveCount(
      0,
    );
  });
  return item;
}
async function heap(cdp) {
  await cdp.send("HeapProfiler.collectGarbage");
  const result = await cdp.send("Runtime.getHeapUsage");
  return result.usedSize;
}

test("connected browser workload: 100 and 2000 invoices, bounded pages, reports and repeated navigation", async ({
  page,
  context,
  browser,
}) => {
  test.setTimeout(240000);
  const report = {
    measured_at: new Date().toISOString(),
    commit: process.env.GSTSHIELD_MEASUREMENT_COMMIT || "working-tree",
    mode: "built preview; isolated real API; synthetic data",
    browser: browser.version(),
    platform: process.platform,
    cpu: cpus()[0]?.model,
    logical_cpus: cpus().length,
    ram_bytes: totalmem(),
    trials: [],
    complete: false,
  };
  const calls = [];
  const bad = [];
  page.on("request", (r) => {
    if (r.url().startsWith(origin))
      calls.push({ url: r.url(), method: r.method() });
  });
  page.on("response", (r) => {
    if (
      r.url().startsWith(origin) &&
      r.status() >= 400 &&
      !r.url().endsWith("auth/session")
    )
      bad.push({ url: r.url(), status: r.status() });
  });
  page.on("pageerror", (error) => bad.push({ page_error: error.message }));
  await page.addInitScript(() => {
    window.measurement = { long_tasks: [], layout_shifts: [] };
    new PerformanceObserver((list) => {
      for (const e of list.getEntries())
        window.measurement.long_tasks.push({
          start_ms: e.startTime,
          duration_ms: e.duration,
        });
    }).observe({ type: "longtask", buffered: true });
    new PerformanceObserver((list) => {
      for (const e of list.getEntries())
        if (!e.hadRecentInput) window.measurement.layout_shifts.push(e.value);
    }).observe({ type: "layout-shift", buffered: true });
  });
  await mkdir("benchmarks/screenshots", { recursive: true });
  const startup = performance.now();
  await page.goto("/");
  await expect(page.getByRole("button", exact("Sign in"))).toBeVisible();
  await paint(page);
  report.initial_login_ready_ms = Math.round(performance.now() - startup);
  report.initial_resources = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .filter((e) => /\.(js|css)(\?|$)/.test(e.name))
      .map((e) => ({
        name: new URL(e.name).pathname,
        bytes: e.decodedBodySize,
        duration_ms: e.duration,
      })),
  );
  await page.getByLabel("Username", { exact: true }).fill("alice");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-passphrase-only");
  await page.getByRole("button", exact("Sign in")).click();
  await expect(page.getByRole("heading", exact("Sources"))).toBeVisible();
  await page
    .getByRole("combobox", exact("Workspace"))
    .selectOption({ label: "Synthetic demonstration · owner" });
  await page
    .getByRole("combobox", exact("Registration"))
    .selectOption({ label: "Synthetic company · 27ABCDE1234F1Z5" });
  const workspace = await page
    .getByRole("combobox", exact("Workspace"))
    .inputValue();
  const base = `/api/v1/workspaces/${workspace}/`;
  const cdp = await context.newCDPSession(page);
  for (const count of [100, 2000]) {
    const steps = [];
    await page
      .getByLabel("Accounting month", { exact: true })
      .fill(count === 100 ? "2024-09" : "2024-10");
    const startCalls = calls.length;
    const purchase = await upload(page, steps, count, "PURCHASE");
    const portal = await upload(page, steps, count, "PORTAL_2B");
    await section(page, "Reconciliation");
    await page
      .getByRole("combobox", exact("Confirmed purchases"))
      .selectOption(purchase.id);
    await page
      .getByRole("combobox", exact("Confirmed supplier / 2B snapshot"))
      .selectOption(portal.id);
    let run;
    await measure(page, steps, "comparison receipt", async () => {
      run = await send(page, "/runs", () =>
        page.getByRole("button", exact("Compare sources")).click(),
      );
    });
    await measure(page, steps, "comparison results ready", async () => {
      await expect(page.getByRole("button", exact("Open result"))).toHaveCount(
        20,
        { timeout: 30000 },
      );
    });
    run = await get(page, base, `runs/${run.id}`);
    expect(run.summary.counts.EXACT_MATCH).toBe(count * 0.95);
    expect(run.summary.counts.FUZZY_SUGGESTION).toBe(count * 0.05);
    await measure(page, steps, "result filtering", async () => {
      await page
        .getByRole("combobox", exact("Result category"))
        .selectOption("FUZZY_SUGGESTION");
      await expect(page.getByRole("button", exact("Open result"))).toHaveCount(
        Math.min(count / 20, 20),
      );
    });
    await measure(page, steps, "review detail", async () => {
      await page.getByRole("button", exact("Open result")).first().click();
      await expect(
        page.getByRole("button", exact("Save review")),
      ).toBeVisible();
    });
    await page
      .getByRole("combobox", exact("Decision"))
      .selectOption("ACCEPT_CANDIDATE");
    await page
      .getByRole("combobox", exact("Candidate"))
      .selectOption({ index: 1 });
    await page
      .getByLabel("Review reason", { exact: true })
      .fill("Synthetic performance review.");
    await measure(
      page,
      steps,
      "review saved and results refreshed",
      async () => {
        await send(page, "/review", () =>
          page.getByRole("button", exact("Save review")).click(),
        );
        await expect(
          page.getByText("Loading saved records…", { exact: true }),
        ).toHaveCount(0);
        await expect(
          page.getByRole("button", exact("Open result")).first(),
        ).toBeVisible();
      },
    );
    const filterAfterReview = await page
      .getByRole("combobox", exact("Result category"))
      .inputValue();
    await page.getByRole("combobox", exact("Result category")).selectOption("");
    await expect(page.getByRole("button", exact("Open result"))).toHaveCount(
      20,
    );
    await measure(page, steps, "next results page", async () => {
      const pending = page.waitForResponse(
        (r) =>
          r.url().includes(`/runs/${run.id}/results?`) &&
          !r.url().includes("cursor=0"),
      );
      await page.getByRole("button", exact("Next results")).click();
      await pending;
      await expect(page.getByRole("button", exact("Open result"))).toHaveCount(
        20,
      );
    });
    await measure(page, steps, "table scroll frames", async () => {
      await page
        .locator("table")
        .last()
        .evaluate((e) => e.scrollIntoView());
      await page.mouse.wheel(0, 600);
    });
    await section(page, "Work queue");
    await expect(
      page.getByRole("button", exact("Open action")).first(),
    ).toBeVisible();
    await measure(page, steps, "action detail", async () => {
      await page.getByRole("button", exact("Open action")).first().click();
      await expect(
        page.getByRole("heading", exact("Tracked business action")),
      ).toBeVisible();
    });
    const history = page
      .locator("details")
      .filter({
        has: page.locator("summary", {
          hasText: "Evidence and action history",
        }),
      })
      .first();
    await expect(history.locator("summary")).toBeVisible();
    const historyDom = await history.locator("*").count();
    await measure(page, steps, "expand action history", async () => {
      await history.locator("summary").click();
      await expect(history.locator("article").first()).toBeVisible();
    });
    await history.locator("summary").click();
    await section(page, "Reports");
    await page.getByText("Generate a report", { exact: true }).click();
    await page
      .getByRole("combobox", exact("Recorded source"))
      .selectOption(run.id);
    let artifact;
    await measure(page, steps, "report initiation", async () => {
      artifact = await send(page, "/artifacts", () =>
        page.getByRole("button", exact("Generate private report")).click(),
      );
    });
    await measure(page, steps, "report ready", async () => {
      await expect(
        page.getByRole("button", exact("Download private report")),
      ).toBeEnabled({ timeout: 30000 });
    });
    await measure(page, steps, "private report download", async () => {
      const pending = page.waitForEvent("download");
      await page.getByRole("button", exact("Download private report")).click();
      const download = await pending;
      expect(await download.failure()).toBeNull();
    });
    const memoryStart = await heap(cdp);
    const nav = [];
    for (let round = 0; round < 3; round++)
      for (const name of sections) {
        await measure(page, nav, `${round + 1}: ${name}`, async () => {
          await section(page, name);
          await expect(
            page.getByText("Loading saved records…", { exact: true }),
          ).toHaveCount(0);
        });
      }
    const memoryEnd = await heap(cdp);
    await page.setViewportSize({ width: 390, height: 844 });
    await section(page, "Reconciliation");
    await page.getByRole("button", exact("Open comparison")).first().click();
    await expect(page.getByRole("button", exact("Open result"))).toHaveCount(
      20,
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `benchmarks/screenshots/performance-${count}-mobile.png`,
      fullPage: true,
    });
    const mobileFrames = [];
    await measure(page, mobileFrames, "mobile table scroll", async () => {
      await page
        .locator("table")
        .last()
        .evaluate((e) => e.scrollIntoView());
      await page.mouse.wheel(0, 500);
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    const second = await context.newPage();
    await second.goto("/#Reports");
    await expect(second.getByRole("heading", exact("Reports"))).toBeVisible();
    await second.close();
    report.trials.push({
      rows: count,
      filter_after_review: filterAfterReview,
      expected_initial_counts: run.summary.counts,
      steps,
      navigation: nav,
      mobile: mobileFrames,
      collapsed_history_descendants: historyDom,
      heap_before_navigation: memoryStart,
      heap_after_navigation: memoryEnd,
      heap_delta: memoryEnd - memoryStart,
      requests: calls.slice(startCalls),
      artifact_kind: artifact.kind,
    });
  }
  report.browser_observations = await page.evaluate(() => window.measurement);
  const sourceHash = createHash("sha256");
  const baseline = process.env.GSTSHIELD_MEASUREMENT_LABEL === "before";
  for (const file of (await readdir("src"))
    .filter((name) => /\.(tsx?|css)$/.test(name))
    .sort()) {
    const result = baseline
      ? spawnSync("git", ["show", `${report.commit}:frontend/src/${file}`], {
          encoding: "utf8",
          windowsHide: true,
        })
      : null;
    if (result && result.status !== 0)
      throw new Error("Cannot hash baseline source");
    const source = result
      ? result.stdout
      : await readFile(`src/${file}`, "utf8");
    sourceHash.update(file + "\n" + source.replaceAll("\r\n", "\n"));
  }
  report.source_sha256 = sourceHash.digest("hex");
  report.budgets = {
    initial_ms: 2000,
    navigation_max_ms: 1000,
    interaction_ms: 1000,
    parsing_ms: 6000,
    matching_ms: 10000,
    report_ready_ms: 15000,
    download_ms: 3000,
    heap_growth_bytes: 2097152,
  };
  const failures = [];
  if (report.initial_login_ready_ms > report.budgets.initial_ms)
    failures.push("Initial load");
  for (const trial of report.trials) {
    if (
      Math.max(...trial.navigation.map((step) => step.elapsed_ms)) >
      report.budgets.navigation_max_ms
    )
      failures.push(`${trial.rows}: navigation`);
    if (trial.heap_delta > report.budgets.heap_growth_bytes)
      failures.push(`${trial.rows}: retained heap growth`);
    if (!baseline && trial.filter_after_review !== "FUZZY_SUGGESTION")
      failures.push(`${trial.rows}: lost result filter`);
    for (const step of trial.steps) {
      const limit = step.name.includes("parsed preview")
        ? report.budgets.parsing_ms
        : step.name === "comparison results ready"
          ? report.budgets.matching_ms
          : step.name === "report ready"
            ? report.budgets.report_ready_ms
            : step.name === "private report download"
              ? report.budgets.download_ms
              : report.budgets.interaction_ms;
      if (step.elapsed_ms > limit) failures.push(`${trial.rows}: ${step.name}`);
    }
  }
  report.budget_failures = failures;
  report.measurement_passed = bad.length === 0 && failures.length === 0;
  report.errors = bad;
  expect(bad).toEqual([]);
  report.complete = true;
  await mkdir("benchmarks/results", { recursive: true });
  const name = process.env.GSTSHIELD_MEASUREMENT_LABEL || "after";
  if (!/^[a-z-]+$/.test(name)) throw new Error("Use a safe measurement label");
  await writeFile(
    `benchmarks/results/${name}.json`,
    JSON.stringify(report, null, 2) + "\n",
  );
  expect(failures).toEqual([]);
  console.log(
    JSON.stringify({
      label: name,
      initial_ms: report.initial_login_ready_ms,
      trials: report.trials.map((t) => ({
        rows: t.rows,
        steps: t.steps,
        heap_delta: t.heap_delta,
      })),
      errors: bad,
    }),
  );
});
