import { test } from "node:test";
import assert from "node:assert/strict";
import { ApiClient, apiOrigin, ApiError } from "../src/client.ts";
const origin = { hostname: "localhost", protocol: "http:" };
test("local configuration rejects cross-host, credentials, paths and remote origins", () => {
  assert.equal(apiOrigin(undefined, origin), "http://localhost:8000");
  for (const url of [
    "http://127.0.0.1:8000",
    "https://localhost:8000",
    "http://evil.test",
    "http://localhost:8000/api",
    "http://a:b@localhost:8000",
    "http://localhost:8000?q=1",
  ])
    assert.throws(() => apiOrigin(url, origin));
});
test("mutations carry credentials, CSRF and stable receipt after lost reply", async () => {
  const original = globalThis.fetch;
  const calls = [];
  try {
    globalThis.fetch = async (url, options) => {
      calls.push(options);
      if (calls.length === 1) throw new Error("lost response");
      return Response.json({ data: { id: "saved" } });
    };
    const api = new ApiClient("http://localhost:8000");
    api.csrf = "memory-only";
    await assert.rejects(
      api.command("/api/v1/workspaces/a/update", { expected_version: 1 }),
      (e) => e instanceof ApiError && e.uncertain,
    );
    assert.deepEqual(
      await api.command("/api/v1/workspaces/a/update", { expected_version: 1 }),
      { id: "saved" },
    );
    assert.equal(
      calls[0].headers["Idempotency-Key"],
      calls[1].headers["Idempotency-Key"],
    );
    assert.equal(calls[0].headers["X-CSRF-Token"], "memory-only");
    assert.equal(calls[0].credentials, "include");
    assert.equal(calls[0].cache, "no-store");
    assert.equal(calls.length, 2);
  } finally {
    globalThis.fetch = original;
  }
});
test("uncertain 500 retains receipt; explicit conflict releases it", async () => {
  const original = globalThis.fetch;
  const keys = [];
  let count = 0;
  try {
    globalThis.fetch = async (_, o) => {
      keys.push(o.headers["Idempotency-Key"]);
      const status = [500, 409, 200][count++];
      return Response.json(
        status === 200
          ? { data: true }
          : { error: { message: "Retry", code: "CONFLICT" } },
        { status },
      );
    };
    const api = new ApiClient("http://localhost:8000");
    const path = "/api/v1/workspaces/a/command";
    await assert.rejects(api.command(path, {}), (e) => e.uncertain);
    await assert.rejects(api.command(path, {}), (e) => e.status === 409);
    await api.command(path, {});
    assert.equal(keys[0], keys[1]);
    assert.notEqual(keys[1], keys[2]);
  } finally {
    globalThis.fetch = original;
  }
});
test("double submit shares one mutation and session reset rejects late data", async () => {
  const original = globalThis.fetch;
  let finish;
  let calls = 0;
  try {
    globalThis.fetch = () => {
      calls++;
      return new Promise((resolve) => (finish = resolve));
    };
    const api = new ApiClient("http://localhost:8000");
    const first = api.command("/api/v1/workspaces/a/command", {});
    const second = api.command("/api/v1/workspaces/a/command", {});
    assert.equal(first, second);
    assert.equal(calls, 1);
    api.reset();
    finish(Response.json({ data: "private old state" }));
    await assert.rejects(first, (e) => e.code === "OBSOLETE");
    assert.equal(api.csrf, "");
  } finally {
    globalThis.fetch = original;
  }
});
test("invalid envelopes are uncertain for writes and 401 notifies once", async () => {
  const original = globalThis.fetch;
  let expired = 0;
  try {
    globalThis.fetch = async () => Response.json({ wrong: true });
    const api = new ApiClient("http://localhost:8000", () => expired++);
    await assert.rejects(
      api.command("/api/v1/workspaces/a/command", {}),
      (e) => e.uncertain,
    );
    globalThis.fetch = async () =>
      Response.json({ error: { message: "Sign in" } }, { status: 401 });
    await assert.rejects(api.get("/api/v1/workspaces"));
    assert.equal(expired, 1);
  } finally {
    globalThis.fetch = original;
  }
});
test("download validates MIME and caps streaming bytes before exposing a file", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () =>
      new Response("<script>bad</script>", {
        headers: { "content-type": "text/html" },
      });
    const api = new ApiClient("http://localhost:8000");
    await assert.rejects(
      api.download("/api/v1/workspaces/a/artifacts/b/download", "bad"),
      /Unsupported/,
    );
    globalThis.fetch = async () =>
      new Response(new Uint8Array(5242881), {
        headers: { "content-type": "application/pdf" },
      });
    await assert.rejects(
      api.download("/api/v1/workspaces/a/artifacts/b/download", "bad"),
      /exceeds/,
    );
  } finally {
    globalThis.fetch = original;
  }
});

test("encoded traversal, separators and controls are rejected before fetch", async () => {
  const original = globalThis.fetch;
  let calls = 0;
  try {
    globalThis.fetch = async () => {
      calls++;
      return Response.json({ data: true });
    };
    const api = new ApiClient("http://localhost:8000");
    for (const path of [
      "/api/v1/%2e%2e/auth",
      "/api/v1/workspaces/a%2fb",
      "/api/v1/workspaces/a\\b",
      "/api/v1/auth/session\n",
      "/api/v1/%252e%252e/auth",
    ]) {
      await assert.rejects(api.get(path), /Unsupported request path/);
    }
    assert.equal(calls, 0);
    assert.equal(
      await api.get("/api/v1/workspaces/a/imports?limit=20&period=2026-05"),
      true,
    );
  } finally {
    globalThis.fetch = original;
  }
});

test("late error body cannot expire a replacement session", async () => {
  const original = globalThis.fetch;
  let finish;
  let started;
  const reading = new Promise((resolve) => (started = resolve));
  let expired = 0;
  try {
    globalThis.fetch = async () => ({
      ok: false,
      status: 401,
      json: () => {
        started();
        return new Promise((resolve) => (finish = resolve));
      },
    });
    const api = new ApiClient("http://localhost:8000", () => expired++);
    const request = api.get("/api/v1/workspaces");
    await reading;
    api.reset();
    api.csrf = "replacement-session";
    finish({ error: { message: "Old session expired" } });
    await assert.rejects(request, (e) => e.code === "OBSOLETE");
    assert.equal(expired, 0);
    assert.equal(api.csrf, "replacement-session");
  } finally {
    globalThis.fetch = original;
  }
});

test("aborted report context cannot expose a completed file", async () => {
  const original = globalThis.fetch;
  const originalURL = URL.createObjectURL;
  let exposed = 0;
  try {
    const scope = new AbortController();
    globalThis.fetch = async () => {
      scope.abort();
      return new Response("%PDF-synthetic", {
        headers: { "content-type": "application/pdf" },
      });
    };
    URL.createObjectURL = () => {
      exposed++;
      throw new Error("Unexpected exposure");
    };
    const api = new ApiClient("http://localhost:8000");
    await assert.rejects(
      api.download(
        "/api/v1/workspaces/a/artifacts/b/download",
        "bad",
        scope.signal,
      ),
      (e) => e.code === "OBSOLETE",
    );
    assert.equal(exposed, 0);
  } finally {
    globalThis.fetch = original;
    URL.createObjectURL = originalURL;
  }
});

test("read errors expose bounded server retry hints without retrying mutations", async () => {
  const original = globalThis.fetch;
  try {
    for (const [header, expected] of [
      ["60", 60000],
      ["999999", 300000],
      ["-1", 0],
      ["invalid", 0],
    ]) {
      let count = 0;
      globalThis.fetch = async () => {
        count++;
        return Response.json(
          { error: { message: "Limited", code: "RATE_LIMITED" } },
          { status: 429, headers: { "Retry-After": header } },
        );
      };
      const api = new ApiClient("http://localhost:8000");
      await assert.rejects(
        api.get("/api/v1/workspaces"),
        (error) => error.retryAfterMs === expected,
      );
      await assert.rejects(
        api.command("/api/v1/workspaces/a/update", {}),
        (error) => error.status === 429,
      );
      assert.equal(count, 2);
    }
  } finally {
    globalThis.fetch = original;
  }
});
