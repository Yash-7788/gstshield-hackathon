import { useState } from "react";
import type { Context } from "./shared";
import {
  useResource,
  useCommand,
  LoadState,
  Notice,
  money,
  label,
} from "./shared";
import { productPath, roleNames } from "./product";
import type { Portal } from "./product";
type Answer = {
  role: string;
  answer: string;
  ai_explanation?: string;
  amounts: Record<string, string | null>;
  facts_used: Record<string, unknown>[];
  recommended_actions: string[];
  missing_data: string[];
  provider: string;
  fingerprint: string;
};
export default function Assistants({
  c,
  initialRole,
  approvedPortal,
}: {
  c: Context;
  initialRole?: string;
  approvedPortal?: Portal;
}) {
  const portalRequest = useResource<Portal>(
    c.api,
    approvedPortal ? null : productPath(c, "portal"),
  );
  const portal = {
    ...portalRequest,
    data: approvedPortal || portalRequest.data,
  };
  const assistantRoles =
    portal.data?.roles.filter((r) =>
      ["CFO", "CMA", "CMO", "CA", "CEO", "COO", "CTO"].includes(r),
    ) || [];
  const [answer, setAnswer] = useState<Answer | null>(null);
  const action = useCommand();
  return (
    <div className="assistant-workspace">
      <p>
        Your assigned assistant explains saved business facts and says what is
        missing. It cannot approve money or tax.
      </p>
      <LoadState {...portal} empty={!portal.data} />
      {portal.data && !assistantRoles.length && (
        <Notice>
          Your role uses the invoice guide and shared process. Ask your owner
          for an assistant role if you need a business briefing.
        </Notice>
      )}
      {portal.data && !!assistantRoles.length && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            setAnswer(null);
            void action.run(
              () =>
                c.api.command<Answer>(
                  productPath(c, `assistants/${f.get("role")}`),
                  {
                    registration_id: c.registration.id,
                    period: c.period,
                    question: f.get("question"),
                    use_ai: f.get("use_ai") === "on",
                  },
                ),
              setAnswer,
              "Briefing ready. Based on saved facts; no decision was changed.",
            );
          }}
        >
          <input
            type="hidden"
            name="role"
            value={initialRole || assistantRoles[0]}
          />
          <h2>{roleNames[initialRole || assistantRoles[0]]} briefing</h2>
          <label>
            What would you like to understand?
            <textarea
              name="question"
              required
              minLength={3}
              maxLength={1000}
              defaultValue="What should I pay attention to today?"
            />
          </label>
          <label>
            <input name="use_ai" type="checkbox" />
            Explain with AI (sends these facts to Google)
          </label>
          <button
            disabled={
              action.busy ||
              !portal.data.roles.some((r) =>
                ["CFO", "CMA", "CMO", "CA", "CEO", "COO", "CTO"].includes(r),
              )
            }
          >
            Ask about saved records
          </button>
          {action.feedback}
        </form>
      )}
      {answer && (
        <article className="panel">
          <h2>{roleNames[answer.role]}</h2>
          <p>{answer.answer}</p>
          <dl className="facts">
            {Object.entries(answer.amounts).map(([k, v]) => (
              <div key={k}>
                <dt>{label(k)}</dt>
                <dd>{money(v)}</dd>
              </div>
            ))}
          </dl>
          <h3>Next actions</h3>
          <ul>
            {answer.recommended_actions.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          <h3>Missing information</h3>
          <ul>
            {answer.missing_data.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          <details>
            <summary>Facts used ({answer.facts_used.length})</summary>
            {answer.facts_used.map((f, i) => (
              <dl key={i} className="facts">
                {Object.entries(f).map(([k, v]) => (
                  <div key={k}>
                    <dt>{label(k)}</dt>
                    <dd>
                      {v == null
                        ? "Unknown"
                        : typeof v === "boolean"
                          ? v
                            ? "Yes"
                            : "No"
                          : String(v)}
                    </dd>
                  </div>
                ))}
              </dl>
            ))}
          </details>
          {answer.ai_explanation && <p>{answer.ai_explanation}</p>}
          <small>
            Saved facts first. AI explanation does not change decisions.
          </small>
        </article>
      )}
    </div>
  );
}
