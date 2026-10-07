import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer, resolveConfig } from "vite";

test("only the API origin is public; dev server denies tests and backend files", async () => {
  const before = process.env.VITE_PRIVILEGED_CANARY;
  process.env.VITE_PRIVILEGED_CANARY = "synthetic-secret-must-not-be-public";
  let server;
  try {
    const config = await resolveConfig({}, "serve");
    assert.equal(config.env.VITE_PRIVILEGED_CANARY, undefined);
    assert.equal(config.publicDir, "");
    server = await createServer({
      server: { port: 0, strictPort: false },
      logLevel: "silent",
    });
    await server.listen();
    const port = server.httpServer.address().port;
    const origin = `http://127.0.0.1:${port}`;
    const app = await fetch(`${origin}/src/App.tsx`);
    assert.equal(app.status, 200);
    assert.ok(!(await app.text()).includes(process.env.VITE_PRIVILEGED_CANARY));
    for (const path of [
      "/tests/client.test.mjs",
      "/benchmarks/results/after.json",
      "/scripts/test-server.mjs",
      "/@fs/" + process.cwd().replaceAll("\\", "/") + "/../backend/app/main.py",
    ]) {
      assert.equal((await fetch(origin + path)).status, 403, path);
    }
  } finally {
    await server?.close();
    if (before === undefined) delete process.env.VITE_PRIVILEGED_CANARY;
    else process.env.VITE_PRIVILEGED_CANARY = before;
  }
});
