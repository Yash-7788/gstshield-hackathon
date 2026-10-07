import { useState } from "react";
import type { InvoiceWorkflow } from "./InvoiceJourney";

import type { Schemas } from "./contracts";

import {
  Badge,
  Field,
  Facts,
  History,
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

type Line = {
  result: Schemas["ResultData"];
  evidence: Schemas["CaseData"];
  amount: string;
  purpose: Schemas["Allocation"]["purpose"];
};

function Builder({
  c,
  run,
  created,
  workflow,
}: {
  c: Context;
  run: Schemas["RunData"];
  created: (id: string) => void;
  workflow?: InvoiceWorkflow;
}) {
  const [cursor, setCursor] = useState(0);
  const [caseCursor, setCaseCursor] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const action = useCommand();

  const results = useResource<Schemas["ResultListData"]>(
    c.api,
    path(c, `runs/${run.id}/results?limit=20&cursor=${cursor}`),
  );

  const cases = useResource<Schemas["CaseListData"]>(
    c.api,
    path(
      c,
      `cases?limit=20&registration_id=${c.registration.id}&period=${c.period}${caseCursor ? `&cursor=${caseCursor}` : ""}`,
    ),
  );

  const resultRecords = workflow
    ? workflow.result
      ? [workflow.result]
      : []
    : results.data?.results || [];
  const evidenceRecords = workflow?.cases || cases.data?.cases || [];
  const eligibleEvidence = evidenceRecords.filter(
    (x) =>
      ["REVIEW_READY", "CLOSED"].includes(x.state) &&
      x.facts.amount_paid != null &&
      x.facts.payment_observed_on != null &&
      (!workflow || x.purchase_document_id === workflow.purchase_document_id),
  );
  const eligibleResult = resultRecords.find((x) =>
    ["EXACT_MATCH", "REVIEW_ACCEPTED"].includes(x.status),
  );
  return (
    <article>
      <h3>Allocate against reviewed balances</h3>
      {workflow && !eligibleEvidence.length && (
        <Notice>
          Record and review payment evidence in this invoice's case before
          saving a payment draft.
        </Notice>
      )}
      <Notice>
        These are recorded payment proposals. GSTShield does not execute bank
        payments or certify statutory timing.
      </Notice>

      <LoadState {...results} empty={false} />
      <LoadState {...cases} empty={false} />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const v = values(e.currentTarget);
          const result = resultRecords.find((x) => x.id === v.result);
          const evidence = eligibleEvidence.find((x) => x.id === v.evidence);
          if (
            !result ||
            !evidence ||
            evidence.purchase_document_id !== result.purchase_document_id
          ) {
            void action.run(() =>
              Promise.reject(
                new Error(
                  "Choose a reviewed payment case for the same invoice.",
                ),
              ),
            );
            return;
          }
          if (
            lines.length >= 200 ||
            lines.some(
              (l) => l.result.id === result.id && l.purpose === v.purpose,
            )
          ) {
            void action.run(() =>
              Promise.reject(
                new Error(
                  "This allocation already exists or the 200-allocation limit was reached.",
                ),
              ),
            );
            return;
          }
          setLines((old) => [
            ...old,
            {
              result,
              evidence,
              amount: v.amount,
              purpose: v.purpose as Line["purpose"],
            },
          ]);
        }}
      >
        <div className="grid">
          <label>
            Accepted invoice
            <select
              name="result"
              required
              defaultValue={workflow ? eligibleResult?.id || "" : ""}
            >
              <option value="">Choose invoice</option>
              {resultRecords
                .filter(
                  (x) =>
                    ["EXACT_MATCH", "REVIEW_ACCEPTED"].includes(x.status) &&
                    x.canonical.document_type !== "CREDIT_NOTE",
                )
                .map((x) => (
                  <option key={x.id} value={x.id}>
                    {text(x.canonical.invoice_number)} ·{" "}
                    {x.purchase_document_id.slice(0, 8)}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Reviewed payment evidence
            <select
              name="evidence"
              required
              defaultValue={workflow ? eligibleEvidence[0]?.id || "" : ""}
            >
              <option value="">Choose matching evidence case</option>
              {eligibleEvidence.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.kind} · invoice {x.purchase_document_id.slice(0, 8)} · paid{" "}
                  {text(x.facts.amount_paid)}
                </option>
              ))}
            </select>
          </label>
          <Field name="amount" required>
            Allocation amount (INR, e.g. 100.00)
          </Field>
          <label>
            Purpose
            <select name="purpose">
              <option value="SUPPLIER_PROPOSED">
                Proposed supplier payment
              </option>
              <option value="INTERNAL_RESERVE_ILLUSTRATIVE">
                Illustrative internal reserve
              </option>
            </select>
          </label>
        </div>
        <button className="secondary" disabled={action.busy}>
          Add allocation
        </button>
      </form>

      <div className="controls">
        <button disabled={!cursor} onClick={() => setCursor(0)}>
          First invoices
        </button>
        <button
          disabled={results.data?.next_cursor == null}
          onClick={() => setCursor(results.data!.next_cursor!)}
        >
          Next invoices
        </button>
        <button disabled={!caseCursor} onClick={() => setCaseCursor("")}>
          First evidence cases
        </button>
        <button
          disabled={!cases.data?.next_cursor}
          onClick={() => setCaseCursor(cases.data!.next_cursor!)}
        >
          Next evidence cases
        </button>
      </div>

      {lines.map((line, i) => (
        <article key={`${line.result.id}:${line.purpose}`}>
          <strong>{text(line.result.canonical.invoice_number)}</strong>
          <Facts
            values={{
              amount: line.amount,
              purpose: line.purpose,
              evidence_case_id: line.evidence.id,
            }}
          />
          <button
            className="secondary"
            disabled={action.busy}
            onClick={() => setLines((old) => old.filter((_, j) => i !== j))}
          >
            Remove allocation
          </button>
        </article>
      ))}

      <button
        disabled={action.busy || !lines.length}
        onClick={() =>
          void action.run(
            () => {
              const distinct = [
                ...new Map(lines.map((l) => [l.result.id, l])).values(),
              ];
              if (
                lines.some(
                  (l) =>
                    l.evidence.id !==
                    distinct.find((d) => d.result.id === l.result.id)?.evidence
                      .id,
                )
              )
                throw new Error("Use one evidence case per invoice.");
              return c.api.command<Schemas["ProposalData"]>(
                path(c, "proposals"),
                {
                  run_id: run.id,
                  expected_run_version: run.version,
                  expected_result_versions: Object.fromEntries(
                    distinct.map((l) => [l.result.id, l.result.version]),
                  ),
                  balance_observations: distinct.map((l) => ({
                    document_id: l.result.purchase_document_id,
                    evidence_case_id: l.evidence.id,
                    expected_case_version: l.evidence.version,
                  })),
                  allocations: lines.map((l) => ({
                    document_id: l.result.purchase_document_id,
                    amount: l.amount,
                    purpose: l.purpose,
                  })),
                },
              );
            },
            (data) => created(data.id),
          )
        }
      >
        Save payment draft ({lines.length} allocations)
      </button>
      {action.feedback}
    </article>
  );
}

export default function Proposals({
  c,
  workflow,
}: {
  c: Context;
  workflow?: InvoiceWorkflow;
}) {
  const [cursor, setCursor] = useState("");
  const [selected, setSelected] = useState(workflow?.proposals[0]?.id || "");
  const [runId, setRun] = useState(workflow?.run?.id || "");
  const action = useCommand();

  const list = useResource<Schemas["ProposalListData"]>(
    c.api,
    path(
      c,
      `proposals?limit=20&registration_id=${c.registration.id}&period=${c.period}${cursor ? `&cursor=${cursor}` : ""}`,
    ),
  );

  const runs = useResource<Schemas["RunListData"]>(
    c.api,
    path(
      c,
      `runs?limit=100&registration_id=${c.registration.id}&period=${c.period}`,
    ),
  );
  const run = workflow
    ? workflow.run
    : runs.data?.runs.find((x) => x.id === runId);
  const draftRecords = workflow?.proposals || list.data?.proposals || [];

  const detail = useResource<Schemas["ProposalData"]>(
    c.api,
    selected ? path(c, `proposals/${selected}`) : null,
  );
  const item = detail.data;

  return (
    <>
      <p>
        Prepare allocations from accepted invoices and explicitly supported
        payment observations.
      </p>
      {writable(c) && (!workflow || workflow.result) && (
        <details open={workflow && !draftRecords.length ? true : undefined}>
          <summary>Create a payment draft</summary>
          <LoadState {...runs} empty={false} />
          <label>
            Current comparison
            <select
              value={workflow?.run?.id || runId}
              disabled={Boolean(workflow)}
              onChange={(e) => setRun(e.target.value)}
            >
              <option value="">Choose comparison</option>
              {(workflow?.run ? [workflow.run] : runs.data?.runs || [])
                .filter(
                  (x) =>
                    x.registration_id === c.registration.id &&
                    x.period === c.period &&
                    x.state === "COMPLETED" &&
                    x.sources_current,
                )
                .map((x) => (
                  <option key={x.id} value={x.id}>
                    Revision {x.revision} · {x.id.slice(0, 8)}
                  </option>
                ))}
            </select>
          </label>
          {run && (
            <Builder
              key={run.id + ":" + run.version}
              c={c}
              run={run}
              workflow={workflow}
              created={(id) => {
                setSelected(id);
                list.reload();
                workflow?.reload();
                setRun("");
              }}
            />
          )}
        </details>
      )}

      <button className="secondary" onClick={list.reload}>
        Refresh drafts
      </button>
      <LoadState {...list} empty={!draftRecords.length} />
      {list.data && (
        <>
          <div
            className="table-wrap"
            tabIndex={0}
            role="region"
            aria-label="Payment proposals table"
          >
            <table>
              <thead>
                <tr>
                  <th>Payment draft</th>
                  <th>State</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {draftRecords.map((p) => (
                  <tr key={p.id}>
                    <td>{p.id.slice(0, 8)}</td>
                    <td>
                      <Badge value={p.state} />
                    </td>
                    <td>
                      <button onClick={() => setSelected(p.id)}>
                        Open draft
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="controls">
            <button disabled={!cursor} onClick={() => setCursor("")}>
              First drafts
            </button>
            <button
              disabled={!list.data.next_cursor}
              onClick={() => setCursor(list.data!.next_cursor!)}
            >
              Next drafts
            </button>
          </div>
        </>
      )}

      <LoadState {...detail} empty={false} />
      {item && (
        <article>
          <h2>Payment proposal</h2>
          <button className="secondary" onClick={detail.reload}>
            Refresh proposal
          </button>
          <Badge value={item.state} />
          <Notice>
            This draft has not transferred money. CSV export is available in
            Reports after approval.
          </Notice>
          {workflow && item.run_id !== workflow.run?.id && (
            <Notice>
              This draft uses an earlier comparison. Create a new draft from
              this invoice's current evidence.
            </Notice>
          )}
          {!item.sources_current && (
            <Notice error>
              Evidence changed; this proposal is stale. Create a new proposal
              from current evidence.
            </Notice>
          )}
          <Facts values={item.snapshot} />
          <History rows={item.timeline} />
          {writable(c) &&
            item.state === "DRAFT" &&
            item.sources_current &&
            (!workflow || item.run_id === workflow.run?.id) && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const v = values(e.currentTarget);
                  void action.run(
                    () =>
                      c.api.command(path(c, `proposals/${item.id}/approve`), {
                        expected_version: item.version,
                        reason: v.reason,
                      }),
                    () => {
                      detail.reload();
                      list.reload();
                      workflow?.reload();
                    },
                  );
                }}
              >
                <Field name="reason" required>
                  Approval reason
                </Field>
                <button disabled={action.busy || detail.loading}>
                  Approve recorded draft
                </button>
              </form>
            )}
          {action.feedback}
        </article>
      )}
    </>
  );
}
