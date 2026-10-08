// Isolated browser-test servers. Never reads the presenter's backend .env or database.
import { spawn, spawnSync } from "node:child_process";
import {
  mkdtemp,
  rm,
  mkdir,
  writeFile,
  access,
  unlink,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, dirname, basename } from "node:path";
const webPort = Number(process.env.GSTSHIELD_TEST_WEB_PORT || 3000);
if (!Number.isInteger(webPort) || webPort < 1024 || webPort > 65535)
  throw new Error("Invalid isolated browser port");
const backend = resolve("../backend");
const python = join(
  backend,
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
const root = await mkdtemp(join(tmpdir(), "gstshield-browser-"));
const program = `import os
from pathlib import Path
import app.config as config
from app.config import Settings
from app.storage.local import LocalStore
from app.services.access import AccessService
from app.main import create_app
import uvicorn
for key in list(os.environ):
 if key.lower() in Settings.model_fields: del os.environ[key]
config.BACKEND_DIR=Path(os.environ["GSTSHIELD_TEST_ROOT"])
settings=Settings(_env_file=None,app_env="test",port=8027,public_api_url="http://127.0.0.1:8027",public_web_url="http://127.0.0.1:${webPort}",cors_origins=["http://127.0.0.1:${webPort}"],read_requests_per_minute=5000,mutation_requests_per_minute=1000,import_requests_per_minute=100,max_imports_per_workspace=40)
store=LocalStore(settings)
store.acquire()
store.initialize()
with store.transaction(write=False) as connection:
 populated=connection.execute("SELECT count(*) FROM users").fetchone()[0]
if not populated:
 access=AccessService(store)
 user,ws=access.provision("alice","synthetic-passphrase-only","Synthetic demonstration")
 access.add_registration(ws,"27ABCDE1234F1Z5","Synthetic company")
 access.add_registration(ws,"29ABCDE1234F1Z5","Second registration")
 other,second=access.provision("bob","synthetic-passphrase-only","Other workspace")
 access.add_registration(second,"27ABCDE1234F1Z5","Other company")
 access.grant("alice",second,"VIEWER")
store.close()
if os.environ.get("GSTSHIELD_TEST_CONTROLLED_OCR") == "1":
 assert settings.app_env == "test"
 from app.adapters import gemini
 from tests.integration.test_passports import FIELDS
 gemini.extract=lambda *_: FIELDS | {"uncertainties":[],"evidence_quotes":{}}
 gemini.extract_commercial=lambda _settings,_content,_mime,kind: {"document_kind":kind,"reference":kind+"-SYNTHETIC","observed_on":"2024-05-10","taxable_value":"100000.00" if kind=="PO" else None,"quantity":"10","items":[FIELDS["items"][0] | ({"taxable_value":None} if kind=="RECEIPT" else {})],"uncertainties":[]}
uvicorn.run(create_app(settings),host="127.0.0.1",port=8027,log_level="warning")`;
let website;
let restartTimer;
let stopping = false;
let restarting = false;
function startApi() {
  const child = spawn(python, ["-c", program], {
    cwd: backend,
    env: { ...process.env, GSTSHIELD_TEST_ROOT: root, PYTHONUTF8: "1" },
    stdio: "inherit",
    windowsHide: true,
  });
  child.on("exit", () => {
    if (!stopping && !restarting) void stop();
  });
  return child;
}
let api = startApi();
function kill(child) {
  if (!child) return;
  if (child.exitCode !== null || child.signalCode !== null) return;
  if (process.platform === "win32")
    spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      windowsHide: true,
      stdio: "ignore",
    });
  else child.kill("SIGTERM");
}
async function ended(child) {
  if (!child) return;
  if (child.exitCode === null && child.signalCode === null)
    await new Promise((resolve) => child.once("exit", resolve));
}
// Do not advertise the website before the isolated API is actually listening.
let ready = false;
for (let attempt = 0; attempt < 150; attempt++) {
  try {
    const response = await fetch("http://127.0.0.1:8027/health/ready");
    if (response.ok) {
      ready = true;
      break;
    }
  } catch {}
  await new Promise((resolve) => setTimeout(resolve, 200));
}
if (!ready) {
  stopping = true;
  kill(api);
  throw new Error("Isolated test API failed readiness.");
}
if (process.env.GSTSHIELD_TEST_PREVIEW === "1") {
  let baselineRoot;
  if (process.env.GSTSHIELD_MEASUREMENT_LABEL === "before") {
    const commit = process.env.GSTSHIELD_MEASUREMENT_COMMIT;
    if (!/^[a-f0-9]{7,40}$/.test(commit || ""))
      throw new Error("Specify a baseline commit hash");
    baselineRoot = resolve("test-results/measurement-baseline");
    const listed = spawnSync(
      "git",
      [
        "ls-tree",
        "-r",
        "--name-only",
        commit,
        "frontend/src",
        "frontend/index.html",
      ],
      { cwd: resolve(".."), encoding: "utf8", windowsHide: true },
    );
    if (listed.status !== 0) throw new Error("Cannot read baseline tree");
    for (const file of listed.stdout.trim().split("\n")) {
      if (!/^frontend\/(src\/[a-zA-Z0-9_.-]+|index\.html)$/.test(file))
        throw new Error("Unexpected baseline path");
      const saved = spawnSync("git", ["show", `${commit}:${file}`], {
        cwd: resolve(".."),
        windowsHide: true,
      });
      if (saved.status !== 0) throw new Error("Cannot read baseline file");
      const target = join(baselineRoot, file.slice("frontend/".length));
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, saved.stdout);
    }
  }
  const built = spawnSync(
    process.execPath,
    [
      "node_modules/vite/bin/vite.js",
      "build",
      ...(baselineRoot
        ? [baselineRoot, "--outDir", resolve("dist"), "--emptyOutDir"]
        : []),
    ],
    {
      env: {
        ...process.env,
        VITE_API_BASE_URL: "http://127.0.0.1:8027",
        VITE_PRIVILEGED_CANARY: "synthetic-secret-must-not-be-public",
        GSTSHIELD_PROVIDER_CANARY: "synthetic-provider-secret-not-public",
      },
      stdio: "inherit",
      windowsHide: true,
    },
  );
  if (built.status !== 0) {
    stopping = true;
    kill(api);
    throw new Error("Test preview build failed.");
  }
}
website = spawn(
  process.execPath,
  [
    "node_modules/vite/bin/vite.js",
    ...(process.env.GSTSHIELD_TEST_PREVIEW === "1" ? ["preview"] : []),
    "--port",
    String(webPort),
  ],
  {
    env: {
      ...process.env,
      VITE_API_BASE_URL: "http://127.0.0.1:8027",
      VITE_PRIVILEGED_CANARY: "synthetic-secret-must-not-be-public",
      GSTSHIELD_PROVIDER_CANARY: "synthetic-provider-secret-not-public",
    },
    stdio: "inherit",
    windowsHide: true,
  },
);

async function stop() {
  if (stopping) return;
  stopping = true;
  clearInterval(restartTimer);
  for (const child of [website, api]) kill(child);
  await Promise.all([website, api].map(ended));
  if (
    dirname(resolve(root)) !== resolve(tmpdir()) ||
    !basename(root).startsWith("gstshield-browser-")
  )
    throw new Error("Refusing cleanup outside the isolated test directory.");
  await rm(root, { recursive: true, force: true });
  process.exit();
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
website.on("exit", () => {
  if (!stopping) void stop();
});

await mkdir("test-results", { recursive: true });
await writeFile("test-results/server.json", JSON.stringify({ root }));
restartTimer = setInterval(async () => {
  if (stopping || restarting) return;
  try {
    await access(join(root, "restart-request"));
  } catch {
    return;
  }
  restarting = true;
  try {
    await unlink(join(root, "restart-request"));
    kill(api);
    await ended(api);
    api = startApi();
    await writeFile(join(root, "restart-completed"), "1");
  } finally {
    restarting = false;
  }
}, 250);
