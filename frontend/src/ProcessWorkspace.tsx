import { useState } from "react";
import type { Context } from "./shared";
import type { Schemas } from "./contracts";
import {
  useResource,
  useCommand,
  LoadState,
  Notice,
  path,
  label,
  money,
  date,
} from "./shared";
import { productPath, selection, roleNames } from "./product";
import type { Member, Portal } from "./product";
type Node = {
  id: string;
  ordinal: number;
  kind: string;
  title: string;
  state: string;
  version: number;
  assigned_to: string | null;
  due_on: string | null;
  active: boolean;
  can_update: boolean;
  can_assign: boolean;
  assignment_roles: string[];
  exit_ready: boolean;
  why: string;
  output: { review_note?: string };
};
type Process = {
  id: string;
  state: string;
  fingerprint: string;
  passport_id: string | null;
  batch_id: string | null;
  nodes: Node[];
  invoice_ids: string[];
  coverage_complete: boolean;
  tax_under_review: (string | null)[];
  events: {
    id: string;
    kind: string;
    username: string;
    note: string;
    created_at: number;
  }[];
  summary: { invoice_titles?: string[]; completed_at?: number };
};
type Notification = {
  id: string;
  kind: string;
  read: number;
  created_at: number;
  payload: { title?: string; summary?: string; note?: string };
};
export default function ProcessWorkspace({
  c,
  navigate,
  compact = false,
}: {
  c: Context;
  navigate: (section: string, id: string) => void;
  compact?: boolean;
}) {
  const readOnly = !["CA", "CFO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"].includes(
    c.staffRole || "",
  );
  const [open, setOpen] = useState(!compact);
  const [selected, setSelected] = useState("");
  const list = useResource<{ workflows: Process[] }>(
    c.api,
    open ? productPath(c, `workflows?${selection(c)}`) : null,
    open ? 15000 : false,
  );
  const invoices = useResource<Schemas["PassportListData"]>(
    c.api,
    open && !readOnly ? path(c, `passports?${selection(c)}`) : null,
  );
  const batches = useResource<Schemas["RunListData"]>(
    c.api,
    open && ["CA", "CFO"].includes(c.staffRole || "")
      ? path(c, `runs?limit=20&${selection(c)}`)
      : null,
  );
  const team = useResource<{ members: Member[] }>(
    c.api,
    open ? productPath(c, "team") : null,
  );
  const portal = useResource<Portal>(
    c.api,
    open ? productPath(c, "portal") : null,
  );
  const notifications = useResource<{ notifications: Notification[] }>(
    c.api,
    open ? productPath(c, "notifications") : null,
    open ? 15000 : false,
  );
  const process =
    list.data?.workflows.find((w) => w.id === selected) ||
    list.data?.workflows[0];
  const action = useCommand();
  const change = () => {
    list.reload();
    notifications.reload();
  };
  const content = (
    <>
      <p>
        Follow the same saved process as the owner and your teammates. A step
        opens only after its earlier steps pass. Completion means internal
        review finished.
      </p>
      <LoadState {...list} empty={!list.data} />
      {!readOnly && portal.data?.financial_write && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const value = String(f.get("source") || "");
            const [kind, id] = value.split(":");
            void action.run(
              () =>
                c.api.command<Process>(
                  productPath(c, "workflows"),
                  kind === "invoice" ? { passport_id: id } : { batch_id: id },
                ),
              (p) => {
                setSelected(p.id);
                change();
              },
            );
          }}
        >
          <label>
            Start from a saved invoice or batch
            <select name="source" required>
              <option value="">Choose a record</option>
              {invoices.data?.passports.map((p) => (
                <option key={p.id} value={`invoice:${p.id}`}>
                  Invoice · {String(p.fields.invoice_number || p.filename)}
                </option>
              ))}
              {batches.data?.runs.map((b) => (
                <option key={b.id} value={`batch:${b.id}`}>
                  Batch · {b.period} · {label(b.state)}
                </option>
              ))}
            </select>
          </label>
          <button disabled={action.busy}>Start or open its process</button>
        </form>
      )}
      {action.feedback}
      {list.data?.workflows.length === 0 && (
        <Notice>
          No process yet. Your accounting team uploads and confirms an invoice;
          its review starts automatically.
        </Notice>
      )}
      {!!list.data?.workflows.length && (
        <label>
          Process
          <select
            value={process?.id || ""}
            onChange={(e) => setSelected(e.target.value)}
          >
            {list.data.workflows.map((w) => (
              <option key={w.id} value={w.id}>
                {w.summary.invoice_titles?.join(", ") || w.id.slice(0, 8)} ·{" "}
                {label(w.state)}
              </option>
            ))}
          </select>
        </label>
      )}
      {process && (
        <>
          <p className="notice">
            <strong>{label(process.state)}</strong> ·{" "}
            {process.nodes.filter((n) => n.state === "DONE").length}/
            {process.nodes.length} steps complete.
            {!process.coverage_complete &&
              " Batch coverage is incomplete: create invoice passports for every accepted purchase row."}
          </p>
          <div className="controls">
            {!readOnly &&
              process.invoice_ids.map((id) => (
                <button key={id} onClick={() => navigate("Invoice desk", id)}>
                  Open invoice evidence
                </button>
              ))}
            {!readOnly && (
              <button
                className="secondary"
                disabled={action.busy}
                onClick={() =>
                  void action.run(
                    () =>
                      c.api.command(
                        productPath(c, `workflows/${process.id}/refresh`),
                        {},
                      ),
                    change,
                  )
                }
              >
                Recheck process evidence
              </button>
            )}
          </div>
          <ProcessGraph
            key={process.id}
            c={c}
            process={
              readOnly
                ? {
                    ...process,
                    nodes: process.nodes.map((n) => ({
                      ...n,
                      can_update: false,
                      can_assign: false,
                    })),
                  }
                : process
            }
            members={team.data?.members || []}
            portal={portal.data || undefined}
            reload={change}
          />
          <details>
            <summary>Who did what?</summary>
            {process.events.map((e) => (
              <article key={e.id}>
                <strong>
                  {e.username} · {label(e.kind)}
                </strong>
                <p>{e.note}</p>
                <small>{date(e.created_at)}</small>
              </article>
            ))}
          </details>
        </>
      )}
      <details>
        <summary>Team workload</summary>
        {team.data?.members
          .filter((m) => m.active)
          .map((m) => (
            <p key={m.id}>
              <strong>{m.display_name}</strong>:{" "}
              {list.data?.workflows
                .flatMap((w) => w.nodes)
                .filter((n) => n.assigned_to === m.id && n.state !== "DONE")
                .length || 0}{" "}
              assigned open steps
            </p>
          ))}
      </details>
      <details>
        <summary>Handoffs and completed work</summary>
        {notifications.data?.notifications.map((n) => (
          <article key={n.id}>
            <strong>{label(n.kind)}</strong>
            <p>{n.payload.title || n.payload.summary}</p>
            {n.payload.note && <p>{n.payload.note}</p>}
            <small>{date(n.created_at)}</small>
            {!n.read && (
              <button
                className="secondary"
                disabled={action.busy}
                onClick={() =>
                  void action.run(
                    () =>
                      c.api.command(
                        productPath(c, `notifications/${n.id}/read`),
                        {},
                      ),
                    notifications.reload,
                  )
                }
              >
                Mark read
              </button>
            )}
          </article>
        ))}
      </details>
    </>
  );
  return compact ? (
    <details className="panel" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>Shared invoice process and team progress</summary>
      {open && content}
    </details>
  ) : (
    content
  );
}
function ProcessGraph({
  c,
  process,
  members,
  portal,
  reload,
}: {
  c: Context;
  process: Process;
  members: Member[];
  portal: Portal | undefined;
  reload: () => void;
}) {
  const [selected, setSelected] = useState("");
  const node =
    process.nodes.find((n) => n.id === selected) ||
    process.nodes.find((n) => n.active && n.state !== "DONE") ||
    process.nodes[0];
  const action = useCommand();
  return (
    <div className="process-workspace">
      <ol className="process-nodes" aria-label="Sequential invoice process">
        {process.nodes.map((n) => (
          <li key={n.id} data-state={n.state}>
            <button
              className="secondary"
              aria-current={node.id === n.id ? "step" : undefined}
              onClick={() => setSelected(n.id)}
            >
              <span>{n.ordinal + 1}</span>
              <strong>{n.title}</strong>
              <small>
                {label(n.state)}
                {!n.active ? " · waiting for earlier steps" : ""}
              </small>
            </button>
          </li>
        ))}
      </ol>
      <article className="panel process-detail">
        <h3>{node.title}</h3>
        <p>{node.why}</p>
        <p>
          Status: <strong>{label(node.state)}</strong>
        </p>
        <p>
          Owner:{" "}
          {members.find((m) => m.id === node.assigned_to)?.display_name ||
            "Not assigned"}{" "}
          · Due: {node.due_on || "Not set"}
        </p>
        {process.tax_under_review.map((v, i) => (
          <p key={i}>
            Invoice {i + 1} tax under review: {money(v)}
          </p>
        ))}
        {node.active && node.state !== "DONE" && !node.can_update && (
          <Notice>
            The assigned reviewer or an approved role moves this step forward.
            You can read the evidence and share context in Team desk.
          </Notice>
        )}
        {node.output.review_note && (
          <p>Last review: {node.output.review_note}</p>
        )}
        {!node.exit_ready && (
          <Notice>This step still needs the evidence described above.</Notice>
        )}
        {node.can_update && (
          <form
            key={`transition:${node.id}`}
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void action.run(
                () =>
                  c.api.command(productPath(c, `nodes/${node.id}/transition`), {
                    expected_version: node.version,
                    fingerprint: process.fingerprint,
                    state: f.get("state"),
                    note: f.get("note"),
                  }),
                reload,
              );
            }}
          >
            <label>
              Update this step
              <select name="state">
                <option value="IN_PROGRESS">Working on it</option>
                <option value="BLOCKED">Blocked: needs something</option>
                <option value="DONE" disabled={!node.exit_ready}>
                  Done: exit checks passed
                </option>
              </select>
            </label>
            <label>
              What did you check or need next?
              <textarea name="note" required minLength={3} maxLength={2000} />
            </label>
            <button disabled={action.busy || !portal?.roles.length}>
              Save step update
            </button>
          </form>
        )}
        {node.can_assign && (
          <details key={`assignment:${node.id}`}>
            <summary>Assign or hand off this step</summary>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                void action.run(
                  () =>
                    c.api.command(productPath(c, `nodes/${node.id}/assign`), {
                      expected_version: node.version,
                      user_id: f.get("user_id"),
                      due_on: f.get("due_on") || null,
                      note: f.get("note"),
                    }),
                  reload,
                );
              }}
            >
              <label>
                Teammate
                <select name="user_id" required>
                  {members
                    .filter(
                      (m) =>
                        m.active &&
                        (m.membership_role === "OWNER" ||
                          m.roles.some((r) =>
                            node.assignment_roles.includes(r),
                          )),
                    )
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.display_name} ·{" "}
                        {m.roles.map((r) => roleNames[r] || r).join(", ")}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Review date
                <input name="due_on" type="date" />
              </label>
              <label>
                Handoff note
                <textarea name="note" required minLength={3} maxLength={2000} />
              </label>
              <button disabled={action.busy}>Assign step</button>
            </form>
          </details>
        )}
        {action.feedback}
        <p className="muted">
          Evidence changes reopen the affected review. Completion records your
          team's work; it does not file tax or transfer money.
        </p>
      </article>
    </div>
  );
}
