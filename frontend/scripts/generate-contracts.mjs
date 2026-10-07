import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const backend = resolve(root, "../backend");
const python = resolve(
  backend,
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
const code = `import os,json
from app.config import Settings
for name in list(os.environ):
 if name.lower() in Settings.model_fields: del os.environ[name]
Settings.model_config['env_file']=None
from app.main import create_app
from app.domain.imports import FIELDS
print(json.dumps({'schemas':create_app(Settings(app_env='test')).app.app.openapi()['components']['schemas'],'import_fields':sorted(FIELDS)},sort_keys=True))`;
const description = JSON.parse(
  execFileSync(python, ["-c", code], {
    cwd: backend,
    encoding: "utf8",
    windowsHide: true,
  }),
);
const schemas = description.schemas;
function type(s) {
  if (s.$ref) return `Schemas[${JSON.stringify(s.$ref.split("/").at(-1))}]`;
  if (s.enum) return s.enum.map(JSON.stringify).join(" | ");
  if (s.const !== undefined) return JSON.stringify(s.const);
  if (s.anyOf || s.oneOf) return (s.anyOf || s.oneOf).map(type).join(" | ");
  if (s.allOf) return s.allOf.map(type).join(" & ");
  if (s.type === "null") return "null";
  if (s.type === "array") return `Array<${type(s.items || {})}>`;
  if (s.type === "integer" || s.type === "number") return "number";
  if (s.type === "string") return "string";
  if (s.type === "boolean") return "boolean";
  if (s.properties)
    return `{ ${Object.entries(s.properties)
      .map(
        ([k, v]) =>
          `${JSON.stringify(k)}${(s.required || []).includes(k) ? "" : "?"}: ${type(v)};`,
      )
      .join(" ")} }`;
  if (s.type === "object")
    return `Record<string, ${typeof s.additionalProperties === "object" ? type(s.additionalProperties) : "unknown"}>`;
  return "unknown";
}
const output =
  "// Generated from the actual backend OpenAPI. Run pnpm generate:api after contract changes.\nexport interface Schemas {\n" +
  Object.entries(schemas)
    .map(([k, v]) => `  ${JSON.stringify(k)}: ${type(v)};`)
    .join("\n") +
  "\n}\n" +
  `export const importFields = ${JSON.stringify(description.import_fields)} as const;\n`;
const target = resolve(root, "src/contracts.ts");
if (process.argv.includes("--check")) {
  if (readFileSync(target, "utf8").replaceAll("\r\n", "\n") !== output)
    throw new Error(
      "Backend contract changed; run pnpm generate:api and review the diff.",
    );
  console.log(
    `Backend contract alignment passed (${Object.keys(schemas).length} types).`,
  );
} else {
  writeFileSync(target, output);
  console.log(`Generated ${Object.keys(schemas).length} types.`);
}
