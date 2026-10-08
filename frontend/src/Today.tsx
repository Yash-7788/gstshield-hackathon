import type { Context } from "./shared";
import { path, useResource, LoadState, money, label } from "./shared";

type Briefing = {
  priorities: {
    passport_id: string;
    invoice: string;
    amount: string | null;
    reason: string;
    next_action: string;
    approval_state: string;
  }[];
  missing_data: string[];
  mode: string;
  fingerprint: string;
};
export default function Today({
  c,
  navigate,
  compact = false,
  limit = 100,
  title = "What should I do today?",
}: {
  c: Context;
  navigate: (section: string, id: string) => void;
  compact?: boolean;
  limit?: number;
  title?: string;
}) {
  const briefing = useResource<Briefing>(
    c.api,
    path(
      c,
      `product/owner-summary?registration_id=${c.registration.id}&period=${c.period}`,
    ),
    15000,
  );
  return (
    <>
      {!compact && (
        <>
          <p>
            Start with the next unanswered question. These priorities come from
            your saved invoices, not guesses about your bank balance.
          </p>
          <details className="guided-help">
            <summary>First time? Bring three records together</summary>
            <ol className="guided-steps">
              <li>
                <strong>1. Bring your purchase register</strong>
                <p>
                  Upload your accounting export or a supported CSV with supplier
                  GSTIN, invoice number, date, goods value and tax. Confirm the
                  columns before using it.
                </p>
                <a href="#Sources">Open Sources</a>
              </li>
              <li>
                <strong>2. Add your GST statement</strong>
                <p>
                  Upload the GSTR-2B JSON or supported statement file you
                  downloaded. Keep the original file. GSTShield does not need
                  your government login.
                </p>
                <a href="#Sources">Add the statement</a>
              </li>
              <li>
                <strong>3. Review the differences</strong>
                <p>
                  Compare the saved records, investigate missing bills and
                  review payment drafts. Follow-up sending needs a configured
                  supplier channel. A result is not tax approval.
                </p>
                <a href="#Reconciliation">See the comparison</a>
              </li>
            </ol>
          </details>
        </>
      )}
      <h2>{title}</h2>
      <LoadState {...briefing} empty={!briefing.data} />
      {briefing.data && (
        <>
          {briefing.data.priorities.length === 0 ? (
            <p className="notice">
              No outstanding invoice priority was found in this month. Open
              Invoice desk to add a bill.
            </p>
          ) : (
            briefing.data.priorities.slice(0, limit).map((p) => (
              <article key={p.passport_id} className="panel">
                <h3>{p.invoice}</h3>
                <p>
                  Recorded tax needing review:{" "}
                  <strong>{money(p.amount)}</strong>
                </p>
                <p>{p.reason}</p>
                <p>
                  Suggested next step: {label(p.next_action)}. Decision:{" "}
                  {label(p.approval_state)}.
                </p>
                <button onClick={() => navigate("Invoice desk", p.passport_id)}>
                  Continue this invoice
                </button>
              </article>
            ))
          )}
          {briefing.data.priorities.length > limit && (
            <a href="#Invoice%20desk">
              Open the invoice list ({briefing.data.priorities.length})
            </a>
          )}
          {!compact && (
            <p className="muted">
              Unknown amounts remain unknown. Review, payment approval and
              supplier confirmation remain separate steps.
            </p>
          )}
        </>
      )}
    </>
  );
}
