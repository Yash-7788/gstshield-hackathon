import { useState } from "react";

import { importFields } from "./contracts";
import type { Schemas } from "./contracts";

import {
  Job,
  Badge,
  Field,
  Facts,
  LoadState,
  Notice,
  path,
  text,
  useCommand,
  useResource,
  values,
  writable,
} from "./shared";

import type { Context } from "./shared";

const fields = importFields;

function ImportDetail({
  c,
  id,
  changed,
}: {
  c: Context;
  id: string;
  changed: (id?: string) => void;
}) {
  const detail = useResource<Schemas["ImportData"]>(
    c.api,
    path(c, `imports/${id}`),
    true,
  );
  const item = detail.data;

  const [cursor, setCursor] = useState(0);
  const [filter, setFilter] = useState("ALL");

  const preview = useResource<Schemas["PreviewData"]>(
    c.api,
    item &&
      ["AWAITING_CONFIRMATION", "READY", "SUPERSEDED"].includes(item.state)
      ? path(c, `imports/${id}/rows?limit=20&cursor=${cursor}&state=${filter}`)
      : null,
  );

  const action = useCommand();

  return (
    <article>
      <h2>Source preview</h2>
      <LoadState {...detail} empty={!item} />
      {item && (
        <>
          <div className="controls">
            <Badge value={item.state} />
            <Badge value={item.provenance} />
            <button className="secondary" onClick={detail.reload}>
              Refresh source
            </button>
          </div>
          <Job
            key={`${item.job_id}:${item.state}:${item.version}`}
            c={c}
            id={item.job_id}
          />
          <Facts
            values={{
              kind: item.kind,
              accepted_rows: item.accepted_rows,
              rejected_rows: item.rejected_rows,
              duplicate_rows: item.duplicate_rows,
              source_id: item.id,
            }}
          />
          {item.errors.length > 0 && (
            <Notice error>
              {item.errors.map((e) => `${e.field}: ${e.reason}`).join(" · ")}
            </Notice>
          )}

          {writable(c) &&
            ["AWAITING_CONFIRMATION", "FAILED"].includes(item.state) && (
              <details>
                <summary>
                  Map exported columns or select a workbook sheet
                </summary>
                <form
                  key={item.version}
                  onSubmit={(e) => {
                    e.preventDefault();
                    const v = values(e.currentTarget);
                    const mapping = Object.fromEntries(
                      fields.filter((f) => v[f]).map((f) => [f, v[f]]),
                    );
                    void action.run(
                      () =>
                        c.api.command<Schemas["ImportData"]>(
                          path(c, `imports/${id}/mapping`),
                          {
                            expected_version: item.version,
                            mapping,
                            sheet_name: v.sheet || null,
                          },
                          "PATCH",
                        ),
                      (result) => {
                        changed(result.id);
                        detail.reload();
                      },
                    );
                  }}
                >
                  <div className="grid">
                    {fields.map((f) => (
                      <label key={f}>
                        {f.replaceAll("_", " ")}
                        <select
                          name={f}
                          defaultValue={
                            item.mapping[f] ||
                            (item.columns.includes(f) ? f : "")
                          }
                        >
                          <option value="">Not supplied</option>
                          {item.columns.map((col) => (
                            <option key={col}>{col}</option>
                          ))}
                        </select>
                      </label>
                    ))}
                    {item.adapter_version === "xlsx-v1" && (
                      <Field name="sheet" value={item.sheet_name || ""}>
                        Workbook sheet
                      </Field>
                    )}
                  </div>
                  <button disabled={action.busy || detail.loading}>
                    Create mapped preview
                  </button>
                </form>
              </details>
            )}

          <div className="controls">
            <label>
              Preview rows
              <select
                value={filter}
                onChange={(e) => {
                  setFilter(e.target.value);
                  setCursor(0);
                }}
              >
                <option value="ALL">All</option>
                <option value="ACCEPTED">Accepted</option>
                <option value="REJECTED">Rejected</option>
              </select>
            </label>
          </div>
          <LoadState {...preview} empty={!preview.data?.rows.length} />
          {preview.data && (
            <>
              <div
                className="table-wrap"
                tabIndex={0}
                role="region"
                aria-label="Source records table"
              >
                <table>
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Invoice / supplier</th>
                      <th>Validation</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.data.rows.map((row) => (
                      <tr key={row.row_number}>
                        <td>{row.row_number}</td>
                        <td>
                          {text(row.canonical?.invoice_number)}
                          <br />
                          <small>{text(row.canonical?.supplier_gstin)}</small>
                        </td>
                        <td>
                          {row.accepted ? "Accepted" : "Rejected"}
                          {row.duplicate && " · Duplicate"}
                          <br />
                          {row.errors
                            .map((e) => `${e.field}: ${e.reason}`)
                            .join(" · ")}
                        </td>
                        <td>
                          <details>
                            <summary>View row</summary>
                            <Facts values={row.original} />
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="controls">
                <button
                  className="secondary"
                  disabled={!cursor}
                  onClick={() => setCursor(0)}
                >
                  First rows
                </button>
                <button
                  className="secondary"
                  disabled={preview.data.next_cursor === null}
                  onClick={() => setCursor(preview.data!.next_cursor!)}
                >
                  Next rows
                </button>
              </div>
            </>
          )}

          {item.state === "AWAITING_CONFIRMATION" && writable(c) && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const v = new FormData(e.currentTarget);
                void action.run(
                  () =>
                    c.api.command(path(c, `imports/${id}/confirm`), {
                      expected_version: item.version,
                      allow_rejected_rows: v.get("partial") === "on",
                      confirmed_supersession: v.get("supersede") === "on",
                    }),
                  () => {
                    detail.reload();
                    changed();
                  },
                );
              }}
            >
              <label className="check">
                <input type="checkbox" name="partial" />I reviewed and accept
                excluding rejected rows
              </label>
              {item.supersedes_import_id && (
                <label className="check">
                  <input type="checkbox" name="supersede" required />
                  Replace the selected earlier snapshot while retaining its
                  history
                </label>
              )}
              <button disabled={action.busy || item.accepted_rows === 0}>
                Confirm source
              </button>
            </form>
          )}
          {action.feedback}
        </>
      )}
    </article>
  );
}

export default function Sources({ c }: { c: Context }) {
  const [cursor, setCursor] = useState("");
  const [selected, setSelected] = useState("");
  const action = useCommand();

  const list = useResource<Schemas["ImportListData"]>(
    c.api,
    path(
      c,
      `imports?registration_id=${c.registration.id}&period=${c.period}&limit=20${cursor ? `&cursor=${cursor}` : ""}`,
    ),
  );

  return (
    <>
      <p>
        Upload purchases once. Add a later supplier/2B snapshot when new
        evidence arrives; history stays recorded.
      </p>
      <Notice>
        Supported: CSV, XLSX and synthetic canonical JSON. Official government
        fetching is unavailable.
      </Notice>
      {writable(c) && (
        <details open>
          <summary>Upload a source</summary>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const v = new FormData(form);
              const file = v.get("file") as File;
              if (!file || !file.size || file.size > 5242880) {
                void action.run(() =>
                  Promise.reject(
                    new Error(
                      "Choose a non-empty source no larger than 5 MiB.",
                    ),
                  ),
                );
                return;
              }
              const metadata = {
                kind: String(v.get("kind")),
                registration_id: c.registration.id,
                period: c.period,
                adapter_version: String(v.get("adapter")),
                sheet_name: String(v.get("sheet") || ""),
                supersedes_import_id: String(v.get("supersedes") || ""),
              };
              const data = new FormData();
              data.set("file", file);
              for (const [key, val] of Object.entries(metadata))
                if (val) data.set(key, val);
              void action.run(
                async () => {
                  const hash = [
                    ...new Uint8Array(
                      await crypto.subtle.digest(
                        "SHA-256",
                        await file.arrayBuffer(),
                      ),
                    ),
                  ]
                    .map((x) => x.toString(16).padStart(2, "0"))
                    .join("");
                  return c.api.upload<Schemas["ImportData"]>(
                    path(c, "imports"),
                    data,
                    JSON.stringify(metadata) + file.name + hash,
                  );
                },
                (result) => {
                  setSelected(result.id);
                  list.reload();
                  form.reset();
                },
              );
            }}
          >
            <div className="grid">
              <label>
                Source kind
                <select name="kind">
                  <option value="PURCHASE">Purchases</option>
                  <option value="PORTAL_2B">Supplier / 2B snapshot</option>
                </select>
              </label>
              <label>
                File format
                <select name="adapter">
                  <option value="csv-v1">CSV</option>
                  <option value="xlsx-v1">XLSX</option>
                  <option value="canonical-demo-v1">
                    Synthetic canonical JSON (2B only)
                  </option>
                </select>
              </label>
              <label>
                Source file
                <input
                  name="file"
                  type="file"
                  accept=".csv,.xlsx,.json"
                  required
                />
              </label>
              <Field name="sheet" maxLength={128}>
                Workbook sheet (optional)
              </Field>
              <label>
                Replace earlier snapshot (optional)
                <select name="supersedes">
                  <option value="">Keep as a separate source</option>
                  {list.data?.imports
                    .filter(
                      (i) => i.kind === "PORTAL_2B" && i.state === "READY",
                    )
                    .map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.id.slice(0, 8)} · {i.period}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            <button disabled={action.busy}>
              {action.busy ? "Receiving source…" : "Upload source"}
            </button>
            {action.feedback}
          </form>
        </details>
      )}

      <div className="controls">
        <button className="secondary" onClick={list.reload}>
          Refresh sources
        </button>
      </div>
      <LoadState {...list} empty={!list.data?.imports.length} />
      {list.data && (
        <>
          <div
            className="table-wrap"
            tabIndex={0}
            role="region"
            aria-label="Source records table"
          >
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>State</th>
                  <th>Rows accepted / rejected</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {list.data.imports.map((item) => (
                  <tr key={item.id}>
                    <td>
                      {item.kind === "PURCHASE" ? "Purchases" : "Supplier / 2B"}
                      <br />
                      <small>
                        {item.id.slice(0, 8)} · {item.period}
                      </small>
                    </td>
                    <td>
                      <Badge value={item.state} />
                    </td>
                    <td>
                      {item.accepted_rows} / {item.rejected_rows}
                    </td>
                    <td>
                      <button onClick={() => setSelected(item.id)}>
                        Preview source
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="controls">
            <button
              className="secondary"
              disabled={!cursor}
              onClick={() => setCursor("")}
            >
              First sources
            </button>
            <button
              className="secondary"
              disabled={!list.data.next_cursor}
              onClick={() => setCursor(list.data!.next_cursor!)}
            >
              Next sources
            </button>
          </div>
        </>
      )}
      {selected && (
        <ImportDetail
          key={selected}
          c={c}
          id={selected}
          changed={(id) => {
            list.reload();
            if (id) setSelected(id);
          }}
        />
      )}
    </>
  );
}
