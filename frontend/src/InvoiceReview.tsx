import { useState } from "react";
import type { Context } from "./shared";
import type { Schemas } from "./contracts";
import {
  useResource,
  useCommand,
  LoadState,
  Notice,
  money,
  label,
  Field,
} from "./shared";
import { productPath } from "./product";
import type { Portal } from "./product";
type Trap = {
  id: string;
  title: string;
  state: string;
  reason: string;
  action: string;
  recorded_amount: string | null;
  deadline: string | null;
  source: string;
  reference: string;
  review_note: string;
};
type Suggestion = {
  id: string;
  title: string;
  trigger: string;
  reference: string;
  source: string;
  estimate_range: "UNKNOWN" | { minimum: string; maximum: string };
  deadline: string | null;
  steps: string[];
  fingerprint: string;
  saved_review: { state: string; conclusion: string; note: string } | null;
};
type ReviewFacts = {
  version: number;
  state: string;
  source_signature: string;
  facts: Record<string, string | boolean | null>;
};
export default function InvoiceReview({
  c,
  invoice,
}: {
  c: Context;
  invoice: Schemas["PassportData"];
}) {
  const [open, setOpen] = useState(false);
  const base = `invoices/${invoice.id}`;
  const traps = useResource<{ traps: Trap[]; facts_state: string }>(
    c.api,
    open ? productPath(c, base + "/traps") : null,
  );
  const facts = useResource<ReviewFacts>(
    c.api,
    open ? productPath(c, base + "/review-facts") : null,
  );
  const tax = useResource<{ suggestions: Suggestion[]; fingerprint: string }>(
    c.api,
    open ? productPath(c, base + "/tax-suggestions") : null,
  );
  const portal = useResource<Portal>(
    c.api,
    open ? productPath(c, "portal") : null,
  );
  const reload = () => {
    traps.reload();
    facts.reload();
    tax.reload();
  };
  return (
    <details
      className="guided-help"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>Risks, deadlines and legal tax review</summary>
      <p>
        Six checks use the current saved evidence. Unknown information is a
        request for facts, not proof that tax is lost.
      </p>
      <LoadState {...traps} empty={!traps.data} />
      {traps.data?.facts_state === "STALE" && (
        <Notice>
          Additional review facts were recorded against older evidence.
          Reconfirm them against the current invoice before relying on them.
        </Notice>
      )}
      {traps.data?.traps.map((t) => (
        <article className="panel" key={t.id}>
          <h3>{t.title}</h3>
          <p>
            <strong>{label(t.state)}</strong> · {t.reason}
          </p>
          {t.recorded_amount !== null && (
            <p>Recorded amount for review: {money(t.recorded_amount)}</p>
          )}
          {t.deadline && <p>Recorded review date: {t.deadline}</p>}
          <p>{t.action}</p>
          <small>
            <a href={t.source} target="_blank" rel="noreferrer">
              {t.reference}
            </a>{" "}
            · Verify with CA
          </small>
        </article>
      ))}
      {facts.data && c.workspace.role !== "VIEWER" && (
        <ReviewForm
          key={`${facts.data.version}:${facts.data.source_signature}`}
          c={c}
          pid={invoice.id}
          facts={facts.data}
          reload={reload}
        />
      )}
      <h3>Legal ways to save tax for this bill</h3>
      <p>
        These are possibilities for a CA to review. A range is a recorded
        exposure bound, not a promised saving.
      </p>
      <LoadState {...tax} empty={!tax.data} />
      {tax.data?.suggestions.length === 0 && (
        <p>No triggered suggestion in the supplied facts.</p>
      )}
      {tax.data?.suggestions.map((s) => (
        <TaxCard
          key={s.id}
          c={c}
          pid={invoice.id}
          suggestion={s}
          canReview={!!portal.data?.roles.includes("CA")}
          reload={reload}
        />
      ))}
    </details>
  );
}
function ReviewForm({
  c,
  pid,
  facts,
  reload,
}: {
  c: Context;
  pid: string;
  facts: ReviewFacts;
  reload: () => void;
}) {
  const action = useCommand();
  const fields: [[string, string], ...[string, string][]] = [
    ["reversed_on", "When was credit reversed?"],
    ["supplier_3b_filed_on", "Supplier filing observed on"],
    ["supplier_3b_unfiled_as_of", "Supplier not filed as of"],
    ["notice_response_due_on", "Actual notice response deadline"],
    ["credit_review_due_on", "CA-confirmed credit review deadline"],
  ];
  return (
    <details className="panel">
      <summary>Record supporting review facts</summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const value = (k: string) => String(f.get(k) || "").trim() || null;
          const bool = (k: string) =>
            value(k) === null ? null : value(k) === "yes";
          void action.run(
            () =>
              c.api.command(productPath(c, `invoices/${pid}/review-facts`), {
                expected_version: facts.version,
                source_signature: facts.source_signature,
                credit_claimed: bool("credit_claimed"),
                notice_response_recorded: bool("notice_response_recorded"),
                reversed_tax: value("reversed_tax"),
                notice_reference: value("notice_reference") || "",
                note: value("note"),
                ...Object.fromEntries(fields.map(([k]) => [k, value(k)])),
              }),
            reload,
          );
        }}
      >
        <p>
          Record actual observations and their source in the note. These entries
          do not verify government filing.
        </p>
        <div className="form-grid">
          {[
            ["credit_claimed", "Was this credit claimed?"],
            ["notice_response_recorded", "Is a notice response recorded?"],
          ].map(([k, t]) => (
            <label key={k}>
              {t}
              <select
                name={k}
                defaultValue={
                  facts.facts[k] === null || facts.facts[k] === undefined
                    ? ""
                    : facts.facts[k]
                      ? "yes"
                      : "no"
                }
              >
                <option value="">Unknown</option>
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </label>
          ))}
          {fields.map(([k, t]) => (
            <Field
              key={k}
              name={k}
              type="date"
              value={String(facts.facts[k] || "")}
            >
              {t}
            </Field>
          ))}
          <Field
            name="reversed_tax"
            value={String(facts.facts.reversed_tax || "")}
            pattern="[0-9]+([.][0-9]{1,2})?"
          >
            Recorded reversed tax (₹)
          </Field>
          <Field
            name="notice_reference"
            value={String(facts.facts.notice_reference || "")}
            maxLength={128}
          >
            Actual notice reference
          </Field>
        </div>
        <label>
          Evidence source and context
          <textarea
            name="note"
            required
            minLength={3}
            maxLength={2000}
            defaultValue={String(facts.facts.note || "")}
          />
        </label>
        <button disabled={action.busy}>Save review facts</button>
        {action.feedback}
      </form>
    </details>
  );
}
function TaxCard({
  c,
  pid,
  suggestion: s,
  canReview,
  reload,
}: {
  c: Context;
  pid: string;
  suggestion: Suggestion;
  canReview: boolean;
  reload: () => void;
}) {
  const action = useCommand();
  return (
    <article className="panel">
      <h4>{s.title}</h4>
      <p>{s.trigger}</p>
      <p>
        Review amount:{" "}
        {s.estimate_range === "UNKNOWN"
          ? "Unknown"
          : `${money(s.estimate_range.minimum)} to ${money(s.estimate_range.maximum)}`}
      </p>
      {s.deadline && <p>Recorded deadline: {s.deadline}</p>}
      <ol>
        {s.steps.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ol>
      <p>
        <a href={s.source} rel="noreferrer" target="_blank">
          {s.reference}
        </a>{" "}
        · Verify with CA
      </p>
      {s.saved_review && (
        <p>
          Saved review: {label(s.saved_review.conclusion)} ·{" "}
          {label(s.saved_review.state)}
        </p>
      )}
      {canReview && (
        <details>
          <summary>Record the CA review</summary>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void action.run(
                () =>
                  c.api.command(productPath(c, "tax-suggestions/review"), {
                    passport_id: pid,
                    suggestion_id: s.id,
                    fingerprint: s.fingerprint,
                    conclusion: f.get("conclusion"),
                    note: f.get("note"),
                  }),
                reload,
              );
            }}
          >
            <label>
              Review outcome
              <select name="conclusion">
                <option value="MORE_EVIDENCE">More evidence needed</option>
                <option value="ACTION_REVIEWED">Action reviewed with CA</option>
                <option value="NOT_APPLICABLE">
                  Not applicable after review
                </option>
              </select>
            </label>
            <label>
              Reason and supporting context
              <textarea name="note" required minLength={3} maxLength={2000} />
            </label>
            <button disabled={action.busy}>Record review</button>
            {action.feedback}
          </form>
        </details>
      )}
    </article>
  );
}
