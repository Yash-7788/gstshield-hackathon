import { existsSync } from "node:fs";
import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  testMatch:
    process.env.GSTSHIELD_TEST_PERFORMANCE === "1"
      ? "performance.mjs"
      : process.env.GSTSHIELD_TEST_PREVIEW === "1"
        ? "preview.smoke.mjs"
        : "*.spec.mjs",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "node scripts/test-server.mjs",
    url: "http://127.0.0.1:3000",
    timeout: 90000,
    reuseExistingServer: false,
  },
  projects: [
    {
      name: "chromium",
      use: {
        browserName: "chromium",
        ...(process.env.GSTSHIELD_BROWSER_CHANNEL
          ? { channel: process.env.GSTSHIELD_BROWSER_CHANNEL }
          : process.platform === "win32" &&
              existsSync(
                "C:/Program Files/Google/Chrome/Application/chrome.exe",
              )
            ? { channel: "chrome" }
            : {}),
      },
    },
  ],
});
