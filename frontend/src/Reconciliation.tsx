import { useState } from "react";
import type { InvoiceWorkflow } from "./InvoiceJourney";

import type { Schemas } from "./contracts";

import {
  Job,
  Badge,
  Field,
  Facts,
  History,
  LoadState,
  Notice,
  money,
  path,
  text,
  useCommand,
  useResource,
  values,
  writable,
} from "./shared";

import type { Context } from "./shared";

export function Results({
  c,
  run,
  updated,
}: {
  c: Context;
  run: Schemas["RunData"];
  updated: () => void;
}) {
  const [cursor, setCursor] = useState(0);
  const [status, setStatus] = useState("");
  const [candidateCursor, setCandidateCursor] = useState(0);
  const [selected, setSelected] = useState("");

  const results = useResource<Schemas["ResultListData"]>(
    c.api,
    path(
      c,
      `runs/${run.id}/results?limit=20&cursor=${cursor}${status ? `&status=${status}` : ""}`,
    ),
  );

  const detail = useResource<Schemas["ResultDetail"]>(
    c.api,
    selected ? path(c, `results/${selected}`) : null,
  );

  const action = useCommand();
  const item = detail.data;
  const candidatePage =
    item?.candidates.slice(candidateCursor, candidateCursor + 20) || [];

  return (
    <>
      <div className="controls">
        <label>
          Result category
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setCursor(0);
            }}
          >
            <option value="">All categories</option>
            {[
              "EXACT_MATCH",
              "FUZZY_SUGGESTION",
              "MISSING_IN_SNAPSHOT",
              "AMOUNT_MISMATCH",
              "AMBIGUOUS",
              "EVIDENCE_INCOMPLETE",
              "REVIEW_ACCEPTED",
              "REJECTED",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <button className="secondary" onClick={results.reload}>
          Refresh results
        </button>
      </div>
      <LoadState {...results} empty={!results.data?.results.length} />
      {results.data && (
        <>
          <div
            className="table-wrap"
            tabIndex={0}
            role="region"
            aria-label="Comparison records table"
          >
            <table>
              <thead>
                <tr>
                  <th>Invoice / supplier</th>
                  <th>Recorded GST</th>
                  <th>Category</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {results.data.results.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {text(row.canonical.invoice_number)}
                      <br />
                      <small>{text(row.canonical.supplier_gstin)}</small>
                    </td>
                    <td>{money(row.canonical.total_tax)}</td>
                    <td>
                      <Badge value={row.status} />
                    </td>
                    <td>
                      <button
                        onClick={() => {
                          setSelected(row.id);
                          setCandidateCursor(0);
                        }}
                      >
                        Open result
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
              onClick={() => setCursor(0)}
            >
              First results
            </button>
            <button
              className="secondary"
              disabled={results.data.next_cursor === null}
              onClick={() => setCursor(results.data!.next_cursor!)}
            >
              Next results
            </button>
          </div>
        </>
      )}

      <LoadState {...detail} empty={false} />
      {item && (
        <article>
          <h3>Review invoice {text(item.canonical.invoice_number)}</h3>
          <button className="secondary" onClick={detail.reload}>
            Reload result before retrying
          </button>
          <Facts values={item.canonical} />
          <Notice>
            {item.reason_codes.join(" · ") ||
              "No discrepancy reasons recorded."}{" "}
            A match is not a legal credit approval.
          </Notice>
          <History rows={item.review_timeline} />
          {item.candidates.length > 0 && (
            <p className="muted">
              Showing candidates {candidateCursor + 1} to{" "}
              {Math.min(candidateCursor + 20, item.candidates.length)} of{" "}
              {item.candidates.length}. All candidates remain available for
              review.
            </p>
          )}
          {candidatePage.map((candidate) => (
            <article key={candidate.id}>
              <strong>Candidate {candidate.original_invoice_number}</strong>
              <Facts
                values={{
                  similarity: candidate.score,
                  invoice_date: candidate.invoice_date,
                  eligible: candidate.hard_gates_passed,
                  available: candidate.currently_available,
                  ...candidate.amount_differences,
                }}
              />
            </article>
          ))}
          {item.candidates.length > 20 && (
            <div className="controls">
              <button
                type="button"
                className="secondary"
                disabled={!candidateCursor}
                onClick={() => setCandidateCursor(0)}
              >
                First candidates
              </button>
              <button
                type="button"
                className="secondary"
                disabled={candidateCursor + 20 >= item.candidates.length}
                onClick={() => setCandidateCursor((value) => value + 20)}
              >
                Next candidates
              </button>
            </div>
          )}
          {writable(c) && run.sources_current && run.state === "COMPLETED" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const v = values(e.currentTarget);
                void action.run(
                  () =>
                    c.api.command(path(c, `results/${item.id}/review`), {
                      expected_version: item.version,
                      action: v.action,
                      reason: v.reason,
                      candidate_id:
                        v.action === "ACCEPT_CANDIDATE" ? v.candidate : null,
                    }),
                  () => {
                    detail.reload();
                    results.reload();
                    updated();
                  },
                );
              }}
            >
              <label>
                Decision
                <select name="action">
                  <option value="REJECT_MATCH">
                    Reject match / record concern
                  </option>
                  <option value="ACCEPT_CANDIDATE">
                    Accept eligible candidate
                  </option>
                </select>
              </label>
              <label>
                Candidate
                <select key={`${item.id}:${candidateCursor}`} name="candidate">
                  <option value="">Select for acceptance</option>
                  {candidatePage
                    .filter((x) => x.hard_gates_passed && x.currently_available)
                    .map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.original_invoice_number} · similarity {x.score}
                      </option>
                    ))}
                </select>
              </label>
              <Field name="reason" required>
                Review reason
              </Field>
              <button disabled={action.busy || detail.loading}>
                Save review
              </button>
            </form>
          )}
          {action.feedback}
        </article>
      )}
    </>
  );
}

export default function Reconciliation({
  c,
  workflow,
}: {
  c: Context;
  workflow?: InvoiceWorkflow;
}) {
  const [cursor, setCursor] = useState("");
  const [selected, setSelected] = useState(workflow?.run?.id || "");
  const action = useCommand();

  const imports = useResource<Schemas["ImportListData"]>(
    c.api,
    path(
      c,
      `imports?registration_id=${c.registration.id}&period=${c.period}&limit=100`,
    ),
  );

  const runs = useResource<Schemas["RunListData"]>(
    c.api,
    path(
      c,
      `runs?limit=20&registration_id=${c.registration.id}&period=${c.period}${cursor ? `&cursor=${cursor}` : ""}`,
    ),
  );

  const detail = useResource<Schemas["RunData"]>(
    c.api,
    workflow?.run?.id || selected
      ? path(c, `runs/${workflow?.run?.id || selected}`)
      : null,
    true,
  );
  const run = detail.data;

  const ready = imports.data?.imports.filter((i) => i.state === "READY") || [];

  return (
    <>
      <p>
        Compare retained purchases with a confirmed supplier snapshot. Review
        suggestions instead of treating them as verified matches.
      </p>
      {writable(c) && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const v = values(e.currentTarget);
            void action.run(
              () =>
                c.api.command<Schemas["RunData"]>(path(c, "runs"), {
                  registration_id: c.registration.id,
                  period: c.period,
                  purchase_import_id:
                    workflow?.purchase_import_id || v.purchase,
                  portal_import_id: workflow?.portal_import_id || v.portal,
                }),
              (result) => {
                setSelected(result.id);
                runs.reload();
              },
            );
          }}
        >
          <div className="grid">
            <label>
              Confirmed purchases
              <select
                key={"purchase:" + ready.length}
                name="purchase"
                required
                defaultValue={workflow?.purchase_import_id || ""}
              >
                <option value="">Select a purchase source</option>
                {ready
                  .filter((i) => i.kind === "PURCHASE")
                  .map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.id.slice(0, 8)} · {i.accepted_rows} rows
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Confirmed supplier / 2B snapshot
              <select
                key={"portal:" + ready.length}
                name="portal"
                required
                defaultValue={workflow?.portal_import_id || ""}
              >
                <option value="">Select a supplier snapshot</option>
                {ready
                  .filter((i) => i.kind === "PORTAL_2B")
                  .map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.id.slice(0, 8)} · {i.accepted_rows} rows
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <button
            disabled={
              action.busy ||
              !ready.some((i) => i.kind === "PURCHASE") ||
              !ready.some((i) => i.kind === "PORTAL_2B")
            }
          >
            Compare sources
          </button>
          {action.feedback}
        </form>
      )}

      <LoadState {...imports} empty={false} />
      <div className="controls">
        <button className="secondary" onClick={runs.reload}>
          Refresh comparisons
        </button>
      </div>
      <LoadState {...runs} empty={!runs.data?.runs.length} />
      {runs.data && (
        <>
          <div
            className="table-wrap"
            tabIndex={0}
            role="region"
            aria-label="Comparison records table"
          >
            <table>
              <thead>
                <tr>
                  <th>Comparison</th>
                  <th>State / evidence</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.runs
                  .filter(
                    (r) =>
                      r.registration_id === c.registration.id &&
                      r.period === c.period,
                  )
                  .map((r) => (
                    <tr key={r.id}>
                      <td>
                        Revision {r.revision} · {r.id.slice(0, 8)}
                      </td>
                      <td>
                        <Badge value={r.state} /> <Badge value={r.provenance} />
                      </td>
                      <td>
                        <button onClick={() => setSelected(r.id)}>
                          Open comparison
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
              First comparisons
            </button>
            <button
              className="secondary"
              disabled={!runs.data.next_cursor}
              onClick={() => setCursor(runs.data!.next_cursor!)}
            >
              Next comparisons
            </button>
          </div>
        </>
      )}

      <LoadState {...detail} empty={false} />
      {run && (
        <article>
          <h2>Comparison revision {run.revision}</h2>
          <Badge value={run.state} />
          <Job
            key={`${run.job_id}:${run.state}:${run.version}`}
            c={c}
            id={run.job_id}
          />
          {!run.sources_current && (
            <Notice error>
              Earlier evidence changed. This comparison is historical; create a
              current comparison before consequential review.
            </Notice>
          )}
          {run.summary && (
            <>
              <p>
                Recorded GST needing review:{" "}
                <strong>{money(run.summary.tax_exposure_review)}</strong> ·
                unknown tax rows: {run.summary.unknown_tax_exposure_rows}
              </p>
              <Facts values={run.summary.counts} />
            </>
          )}
          <button className="secondary" onClick={detail.reload}>
            Refresh comparison
          </button>
          {run.state === "FAILED" && (
            <Notice error>
              Processing failed. See the job status; retry with a new comparison
              after correcting the cause.
            </Notice>
          )}
          {["COMPLETED", "SUPERSEDED"].includes(run.state) && (
            <Results
              key={run.id}
              c={c}
              run={run}
              updated={() => {
                detail.reload();
                runs.reload();
              }}
            />
          )}
        </article>
      )}
    </>
  );
}
