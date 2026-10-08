import config from "./playwright.config.mjs";
export default {
  ...config,
  testMatch: "role-isolation.spec.mjs",
  use: { ...config.use, baseURL: "http://127.0.0.1:3127" },
  webServer: {
    ...config.webServer,
    url: "http://127.0.0.1:3127",
    env: {
      GSTSHIELD_TEST_WEB_PORT: "3127",
      GSTSHIELD_TEST_CONTROLLED_OCR: "1",
    },
  },
};
