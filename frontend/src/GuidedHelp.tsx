import { useState } from "react";
import type { Context } from "./shared";
import { path, useResource, LoadState, money } from "./shared";
import type { Schemas } from "./contracts";

type Term = {
  term: string;
  meaning: string;
  reference?: string;
  source?: string;
  review_note?: string;
};
type Guide = {
  steps: {
    id: string;
    title: string;
    state: string;
    why: string;
    staff: string;
  }[];
  next_step: { title: string } | null;
  staff: { name: string; scope: string; tasks: string[] }[];
  recorded_tax_under_review: string | null;
  example: string;
};

export default function GuidedHelp({ c }: { c: Context }) {
  const [open, setOpen] = useState(false);
  const result = useResource<{ terms: Term[]; example: string }>(
    c.api,
    open ? path(c, "command-center/glossary") : null,
  );
  return (
    <details
      className="guided-help"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>New to finance? Start here</summary>
      {open && (
        <>
          <p>
            One invoice tells you what was billed. An order, a delivery record
            and a GST statement tell you different parts of the story.
          </p>
          <LoadState {...result} empty={!result.data} />
          {result.data && (
            <>
              <p className="notice">{result.data.example}</p>
              <div className="glossary-grid">
                {result.data.terms.map((t) => (
                  <details key={t.term}>
                    <summary title={t.meaning}>{t.term}</summary>
                    <p>{t.meaning}</p>
                    {t.reference && (
                      <p>
                        <a href={t.source} target="_blank" rel="noreferrer">
                          {t.reference}
                        </a>{" "}
                        · {t.review_note}
                      </p>
                    )}
                  </details>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </details>
  );
}

export function InvoiceGuide({
  c,
  invoice,
}: {
  c: Context;
  invoice: Schemas["PassportData"];
}) {
  const [open, setOpen] = useState(false);
  const result = useResource<Guide>(
    c.api,
    open
      ? path(
          c,
          `command-center/invoices/${invoice.id}/guide?version=${invoice.version}`,
        )
      : null,
  );
  return (
    <details
      className="guided-help"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>Guide me through this invoice</summary>
      {open && (
        <>
          <LoadState {...result} empty={!result.data} />
          {result.data && (
            <>
              <p>
                {result.data.next_step
                  ? `Next: ${result.data.next_step.title}`
                  : "The supplied evidence checklist is complete. This is not a filed return or payment."}
              </p>
              <p>
                Recorded tax under review:{" "}
                {money(result.data.recorded_tax_under_review)}
              </p>
              <ol className="guided-steps">
                {result.data.steps.map((s) => (
                  <li key={s.id}>
                    <strong>
                      {s.state === "DONE" ? "✓ " : "○ "}
                      {s.title}
                    </strong>
                    <p>{s.why}</p>
                    <small>{s.staff}</small>
                  </li>
                ))}
              </ol>
              <details>
                <summary>Your digital staff views</summary>
                {result.data.staff.map((s) => (
                  <article key={s.name}>
                    <strong>{s.name}</strong>
                    <p>{s.scope}</p>
                    <p>
                      {s.tasks.length
                        ? s.tasks.join("; ")
                        : "No outstanding checklist task in this view."}
                    </p>
                  </article>
                ))}
              </details>
            </>
          )}
        </>
      )}
    </details>
  );
}
