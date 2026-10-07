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
  money,
  path,
  text,
  useCommand,
  useResource,
  values,
  writable,
} from "./shared";

import type { Context } from "./shared";

type Spec = { name: string; title: string; type?: string; options?: string[] };

const payment: Spec[] = [
  { name: "amount_paid", title: "Recorded amount paid (INR)" },
  {
    name: "payment_observed_on",
    title: "Payment observation date",
    type: "date",
  },
];

export const factSpecs: Record<string, Spec[]> = {
  MSME_REVIEW: [
    ...payment,
    {
      name: "supplier_classification",
      title: "Supplier classification",
      options: ["UNKNOWN", "MICRO", "SMALL", "MEDIUM", "OTHER"],
    },
    { name: "acceptance_date", title: "Acceptance date", type: "date" },
    { name: "agreed_credit_days", title: "Agreed credit days", type: "number" },
    { name: "dispute_note", title: "Dispute note" },
  ],

  RULE37_REVIEW: [
    ...payment,
    {
      name: "original_claim_period",
      title: "Original claim month",
      type: "month",
    },
    { name: "original_claim_amount", title: "Original claimed GST (INR)" },
    {
      name: "payment_due_date",
      title: "Recorded payment review date",
      type: "date",
    },
  ],

  RULE37A_REVIEW: [
    {
      name: "original_claim_period",
      title: "Original claim month",
      type: "month",
    },
    { name: "original_claim_amount", title: "Original claimed GST (INR)" },
    { name: "reversal_period", title: "Reversal month", type: "month" },
    { name: "reversal_amount", title: "Recorded reversal (INR)" },
    {
      name: "supplier_return_period",
      title: "Supplier return month",
      type: "month",
    },
    {
      name: "supplier_return_status",
      title: "Supplier return observation",
      options: ["UNKNOWN", "FILED", "NOT_FILED"],
    },
    {
      name: "filing_observed_on",
      title: "Filing observation date",
      type: "date",
    },
  ],

  IRN_REVIEW: [
    { name: "irn", title: "Recorded IRN" },
    {
      name: "applicability",
      title: "E-invoice applicability observation",
      options: ["UNKNOWN", "APPLIES", "DOES_NOT_APPLY"],
    },
  ],

  NOTICE_REVIEW: [
    { name: "notice_reference", title: "Notice reference" },
    { name: "notice_date", title: "Notice date", type: "date" },
    {
      name: "response_due_date",
      title: "Recorded response review date",
      type: "date",
    },
  ],
};

export function FactInputs({
  kind,
  facts = {},
}: {
  kind: string;
  facts?: Record<string, unknown>;
}) {
  return (
    <div className="grid">
      {factSpecs[kind].map((f) =>
        f.options ? (
          <label key={f.name}>
            {f.title}
            <select
              name={f.name}
              defaultValue={
                typeof facts[f.name] === "string"
                  ? String(facts[f.name])
                  : f.options[0]
              }
            >
              {f.options.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          </label>
        ) : (
          <Field
            key={f.name}
            name={f.name}
            type={f.type}
            value={
              facts[f.name] === null || facts[f.name] === undefined
                ? ""
                : String(facts[f.name])
            }
          >
            {f.title}
          </Field>
        ),
      )}
    </div>
  );
}

function factsFrom(kind: string, v: Record<string, string>) {
  return Object.fromEntries(
    factSpecs[kind].map((f) => [
      f.name,
      v[f.name] ? (f.type === "number" ? Number(v[f.name]) : v[f.name]) : null,
    ]),
  );
}

function CaseDetail({
  c,
  id,
  reload,
}: {
  c: Context;
  id: string;
  reload: () => void;
}) {
  const detail = useResource<Schemas["CaseData"]>(
    c.api,
    path(c, `cases/${id}`),
  );
  const item = detail.data;
  const action = useCommand();

  const imports = useResource<Schemas["ImportListData"]>(
    c.api,
    path(c, `imports?registration_id=${c.registration.id}&limit=100`),
  );

  const saved = () => {
    detail.reload();
    reload();
  };

  return (
    <article>
      <h2>Evidence case</h2>
      <LoadState {...detail} empty={false} />
      {item && (
        <>
          <div className="controls">
            <Badge value={item.kind} />
            <Badge value={item.state} />
            <Badge value={item.provenance} />
            <button className="secondary" onClick={detail.reload}>
              Refresh case
            </button>
          </div>
          <p>
            Recorded amount: <strong>{money(item.amount)}</strong>
          </p>
          {item.missing_facts.length > 0 ? (
            <Notice>
              Still needed:{" "}
              {item.missing_facts
                .map((x) => x.replaceAll("_", " "))
                .join(" · ")}
            </Notice>
          ) : (
            <Notice>
              Recorded evidence is ready for human review. It does not establish
              legal eligibility.
            </Notice>
          )}
          {item.kind === "IRN_REVIEW" && (
            <Notice>
              IRN: {text(item.irn_observation)}. Government authenticity is
              unverified.
            </Notice>
          )}
          <Facts values={item.facts} />
          <History rows={item.timeline} />

          {writable(c) && (
            <>
              <details>
                <summary>Add or update evidence and recorded facts</summary>
                <form
                  key={item.version}
                  onSubmit={(e) => {
                    e.preventDefault();
                    const v = values(e.currentTarget);
                    void action.run(
                      () =>
                        c.api.command(path(c, `cases/${id}/evidence`), {
                          expected_version: item.version,
                          reason: v.reason,
                          event_kind: v.event,
                          import_id: v.source || null,
                          facts_patch: factsFrom(item.kind, v),
                        }),
                      saved,
                    );
                  }}
                >
                  <label>
                    Observation kind
                    <select name="event">
                      {[
                        "NOTE",
                        "DOCUMENT",
                        "PAYMENT_OBSERVATION",
                        "FILING_OBSERVATION",
                        "ACCEPTANCE_OBSERVATION",
                        "IRN_OBSERVATION",
                      ].map((k) => (
                        <option key={k}>{k}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Supporting confirmed source (for document evidence)
                    <select name="source">
                      <option value="">No source reference</option>
                      {imports.data?.imports
                        .filter(
                          (i) =>
                            i.state === "READY" &&
                            i.registration_id === item.registration_id,
                        )
                        .map((i) => (
                          <option key={i.id} value={i.id}>
                            {i.kind} · {i.period} · {i.id.slice(0, 8)}
                          </option>
                        ))}
                    </select>
                  </label>
                  <FactInputs kind={item.kind} facts={item.facts} />
                  <Field name="reason" required>
                    Evidence note / reason
                  </Field>
                  <button disabled={action.busy || detail.loading}>
                    Save evidence
                  </button>
                </form>
              </details>

              <details>
                <summary>Select supporting observations</summary>
                <p>
                  Record an observation first, then explicitly support it here.
                  Changing facts can require a new observation.
                </p>
                {item.timeline
                  .filter(
                    (row) =>
                      !["CREATE", "TRANSITION", "NOTE"].includes(
                        String(row.kind),
                      ),
                  )
                  .map((event) => {
                    const refs = Array.isArray(item.facts.observation_refs)
                      ? item.facts.observation_refs.map(String)
                      : [];
                    const chosen = refs.includes(String(event.id));
                    return (
                      <div className="controls" key={String(event.id)}>
                        <span>
                          {text(event.kind)} · {String(event.id).slice(0, 8)}
                        </span>
                        <button
                          disabled={action.busy || detail.loading}
                          className="secondary"
                          onClick={() =>
                            void action.run(
                              () =>
                                c.api.command(path(c, `cases/${id}/evidence`), {
                                  expected_version: item.version,
                                  reason: chosen
                                    ? "Removed supporting observation."
                                    : "Selected supporting observation.",
                                  event_kind: "NOTE",
                                  facts_patch: {
                                    observation_refs: chosen
                                      ? refs.filter((x) => x !== event.id)
                                      : [...refs, event.id],
                                  },
                                }),
                              saved,
                            )
                          }
                        >
                          {chosen ? "Remove support" : "Support observation"}
                        </button>
                      </div>
                    );
                  })}
              </details>

              <form
                key={`state-${item.version}`}
                onSubmit={(e) => {
                  e.preventDefault();
                  const v = values(e.currentTarget);
                  void action.run(
                    () =>
                      c.api.command(path(c, `cases/${id}/transition`), {
                        expected_version: item.version,
                        state: v.state,
                        reason: v.reason,
                      }),
                    saved,
                  );
                }}
              >
                <label>
                  Case review state
                  <select name="state" defaultValue={item.state}>
                    {[
                      "OPEN",
                      "EVIDENCE_REQUIRED",
                      "REVIEW_READY",
                      "CLOSED",
                    ].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
                <Field name="reason" required>
                  Transition reason
                </Field>
                <button disabled={action.busy || detail.loading}>
                  Save case state
                </button>
              </form>
            </>
          )}
          {action.feedback}
        </>
      )}
    </article>
  );
}

export default function Cases({
  c,
  workflow,
}: {
  c: Context;
  workflow?: InvoiceWorkflow;
}) {
  const [cursor, setCursor] = useState("");
  const [selected, setSelected] = useState(workflow?.cases[0]?.id || "");
  const [runId, setRun] = useState(workflow?.run?.id || "");
  const [resultCursor, setResultCursor] = useState(0);
  const [kind, setKind] = useState("RULE37A_REVIEW");
  const action = useCommand();

  const list = useResource<Schemas["CaseListData"]>(
    c.api,
    path(
      c,
      `cases?limit=20&registration_id=${c.registration.id}&period=${c.period}${cursor ? `&cursor=${cursor}` : ""}`,
    ),
  );

  const runs = useResource<Schemas["RunListData"]>(
    c.api,
    path(
      c,
      `runs?limit=100&registration_id=${c.registration.id}&period=${c.period}`,
    ),
  );

  const results = useResource<Schemas["ResultListData"]>(
    c.api,
    runId
      ? path(c, `runs/${runId}/results?limit=20&cursor=${resultCursor}`)
      : null,
  );

  const caseRecords = workflow?.cases || list.data?.cases || [];
  const resultRecords = workflow?.result
    ? [workflow.result]
    : workflow
      ? []
      : results.data?.results || [];
  const comparisonRecords = workflow?.run
    ? [workflow.run]
    : runs.data?.runs || [];
  return (
    <>
      <p>
        Record payment, reversal, e-invoice and notice facts with their
        evidence. Unknown facts stay unknown.
      </p>
      {writable(c) && (!workflow || workflow.result) && (
        <details open={workflow && !caseRecords.length ? true : undefined}>
          <summary>Create an evidence case</summary>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const v = values(e.currentTarget);
              const result = resultRecords.find((r) => r.id === v.result);
              if (!result) return;
              void action.run(
                () =>
                  c.api.command<Schemas["CaseData"]>(path(c, "cases"), {
                    registration_id: c.registration.id,
                    result_id: result.id,
                    purchase_document_id: result.purchase_document_id,
                    kind,
                    amount: v.amount,
                    facts: factsFrom(kind, v),
                  }),
                (data) => {
                  setSelected(data.id);
                  list.reload();
                  workflow?.reload();
                },
              );
            }}
          >
            <div className="grid">
              <label>
                Current comparison
                <select
                  value={workflow?.run?.id || runId}
                  disabled={Boolean(workflow)}
                  onChange={(e) => {
                    setRun(e.target.value);
                    setResultCursor(0);
                  }}
                  required
                >
                  <option value="">Select comparison</option>
                  {comparisonRecords
                    .filter(
                      (r) =>
                        r.registration_id === c.registration.id &&
                        r.period === c.period &&
                        r.state === "COMPLETED" &&
                        r.sources_current,
                    )
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        Revision {r.revision} · {r.id.slice(0, 8)}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Invoice result
                <select
                  name="result"
                  required
                  defaultValue={workflow?.result?.id || ""}
                >
                  <option value="">Select invoice</option>
                  {resultRecords.map((r) => (
                    <option key={r.id} value={r.id}>
                      {text(r.canonical.invoice_number)} · {r.status}
                    </option>
                  ))}
                </select>
              </label>
              <div className="controls">
                <button
                  type="button"
                  disabled={!resultCursor}
                  onClick={() => setResultCursor(0)}
                >
                  First case invoices
                </button>
                <button
                  type="button"
                  disabled={results.data?.next_cursor == null}
                  onClick={() => setResultCursor(results.data!.next_cursor!)}
                >
                  Next case invoices
                </button>
              </div>
              <label>
                Case type
                <select value={kind} onChange={(e) => setKind(e.target.value)}>
                  {Object.keys(factSpecs).map((k) => (
                    <option key={k}>{k}</option>
                  ))}
                </select>
              </label>
              <Field name="amount" required>
                Recorded GST amount for this case (INR)
              </Field>
            </div>
            <FactInputs key={kind} kind={kind} />
            <button disabled={action.busy || !resultRecords.length}>
              Create case
            </button>
            {action.feedback}
          </form>
          <LoadState {...runs} empty={false} />
          <LoadState {...results} empty={false} />
        </details>
      )}

      <div className="controls">
        <button className="secondary" onClick={list.reload}>
          Refresh cases
        </button>
      </div>
      <LoadState {...list} empty={!caseRecords.length} />
      {list.data && (
        <>
          <div
            className="table-wrap"
            tabIndex={0}
            role="region"
            aria-label="Evidence cases table"
          >
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Amount</th>
                  <th>State</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {caseRecords
                  .filter((x) => x.registration_id === c.registration.id)
                  .map((item) => (
                    <tr key={item.id}>
                      <td>
                        {item.kind}
                        <br />
                        <small>{item.id.slice(0, 8)}</small>
                      </td>
                      <td>{money(item.amount)}</td>
                      <td>
                        <Badge value={item.state} />
                      </td>
                      <td>
                        <button onClick={() => setSelected(item.id)}>
                          Open case
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
              First cases
            </button>
            <button
              className="secondary"
              disabled={!list.data.next_cursor}
              onClick={() => setCursor(list.data!.next_cursor!)}
            >
              Next cases
            </button>
          </div>
        </>
      )}
      {selected && (
        <CaseDetail
          key={selected}
          c={c}
          id={selected}
          reload={() => {
            list.reload();
            workflow?.reload();
          }}
        />
      )}
    </>
  );
}
