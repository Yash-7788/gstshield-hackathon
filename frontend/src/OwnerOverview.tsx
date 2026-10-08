import type { Context } from "./shared";
import { useResource, LoadState, money } from "./shared";
import { productPath, selection } from "./product";
import type { Business, Member } from "./product";
type Summary = {
  business: Business;
  metrics: Record<string, unknown>;
  priorities: {
    passport_id: string;
    invoice: string;
    amount: string | null;
    reason: string;
    next_action: string;
    approval_state: string;
  }[];
};
export default function OwnerOverview({ c }: { c: Context }) {
  const summary = useResource<Summary>(
    c.api,
    productPath(c, `owner-summary?${selection(c)}`),
    15000,
  );
  const progress = useResource<{
    workflows: {
      id: string;
      invoice_group?: string;
      state: string;
      nodes: {
        title: string;
        state: string;
        why: string;
        assigned_to: string | null;
        due_on: string | null;
      }[];
      summary: { invoice_titles?: string[] };
    }[];
  }>(c.api, productPath(c, `workflows?${selection(c)}`), 15000);
  const team = useResource<{ members: Member[] }>(
    c.api,
    productPath(c, "team"),
    15000,
  );
  const person = (id: string | null) =>
    team.data?.members.find((m) => m.id === id)?.display_name ||
    "Not assigned yet";
  const p = summary.data?.business.profile;
  const groups = new Map<
    string,
    NonNullable<typeof progress.data>["workflows"]
  >();
  for (const w of progress.data?.workflows || []) {
    const key = w.invoice_group || w.id;
    groups.set(key, [...(groups.get(key) || []), w]);
  }
  const ownerProcesses = [...groups.values()].map((group) => ({
    ...group[0],
    related: group.length,
  }));
  return (
    <section className="owner-summary">
      <h2>Your business. Your team's progress.</h2>
      <p>
        Your team checks invoices and prepares decisions. You see what needs
        attention, why it matters and who is working on it.
      </p>
      <LoadState {...summary} empty={false} />
      {summary.data && (
        <>
          <dl className="role-figures">
            <div>
              <dt>Revenue reported</dt>
              <dd>{money(p?.monthly_revenue)}</dd>
            </div>
            <div>
              <dt>Profit reported</dt>
              <dd>{money(p?.monthly_profit)}</dd>
            </div>
            <div>
              <dt>Invoice tax needing review</dt>
              <dd>
                {Number(summary.data.metrics.unknown_tax_invoices) > 0 &&
                Number(summary.data.metrics.recorded_itc_under_review) === 0
                  ? "Awaiting invoice review"
                  : money(summary.data.metrics.recorded_itc_under_review)}
              </dd>
            </div>
          </dl>
          {Number(summary.data.metrics.unknown_tax_invoices) > 0 && (
            <p className="caption">
              {String(summary.data.metrics.unknown_tax_invoices)} invoices still
              need their tax figures checked. Known amounts do not include them.
            </p>
          )}
          <h3>What needs attention</h3>
          {summary.data.priorities.slice(0, 5).map((x) => (
            <article className="panel" key={x.passport_id}>
              <strong>{x.invoice}</strong>
              <p>{x.reason}</p>
              <span>
                {x.amount == null
                  ? "Tax amount awaiting invoice review"
                  : `${money(x.amount)} recorded tax needing review`}
              </span>
              <p className="muted">
                Next:{" "}
                {x.approval_state === "STALE"
                  ? "The team must review changed evidence again."
                  : "Your accounting and finance team checks the evidence before approving payment."}
              </p>
            </article>
          ))}
          {!summary.data.priorities.length && (
            <p>No invoice priorities in this month.</p>
          )}
        </>
      )}
      <h3>Where the work stands</h3>
      <LoadState {...progress} empty={false} />
      {ownerProcesses.map((w) => (
        <article key={w.id} className="panel">
          <strong>
            {w.summary.invoice_titles?.join(", ") || "Invoice review"}
          </strong>
          {w.related > 1 && (
            <p className="caption">
              {w.related} related review records. Your accounting team checks
              the copies; this summary shows the latest review.
            </p>
          )}
          <p>
            {w.nodes.filter((n) => n.state === "DONE").length} of{" "}
            {w.nodes.length} steps complete ·{" "}
            {w.state === "PROCESS_COMPLETED"
              ? "Internal review complete"
              : "In progress"}
          </p>
          {(() => {
            const next = w.nodes.find((n) => n.state !== "DONE");
            return (
              next && (
                <p>
                  <strong>Next: {next.title}</strong>
                  <br />
                  Who: {person(next.assigned_to)} · When:{" "}
                  {next.due_on || "No due date assigned"}
                  <br />
                  {next.why}
                </p>
              )
            );
          })()}
          <details>
            <summary>See the review steps</summary>
            <ol className="owner-progress">
              {w.nodes.map((n, i) => (
                <li key={i}>
                  <strong>{n.title}</strong>
                  <span>{n.state.toLowerCase().replaceAll("_", " ")}</span>
                  {n.state !== "DONE" && <small>{n.why}</small>}
                </li>
              ))}
            </ol>
          </details>
        </article>
      ))}
      {progress.data && !progress.data.workflows.length && (
        <p>
          Your team's invoice reviews will appear here automatically after
          confirmation.
        </p>
      )}
      <p className="caption">
        Amounts come from saved records. Tax needing review is not a proven
        loss. This overview does not submit GST returns or transfer money.
      </p>
    </section>
  );
}
