import SupplierDelivery from "./SupplierDelivery";
import { useState } from "react";

import type { Schemas } from "./contracts";

import {
  Badge,
  Field,
  Facts,
  History,
  LoadState,
  Notice,
  label,
  date,
  money,
  path,
  text,
  useCommand,
  useResource,
  utcDay,
  values,
  writable,
} from "./shared";

import type { Context } from "./shared";

function ActionDetail({
  c,
  id,
  reload,
}: {
  c: Context;
  id: string;
  reload: () => void;
}) {
  const detail = useResource<Schemas["ActionData"]>(
    c.api,
    path(c, `actions/${id}`),
  );
  const row = detail.data;
  const evidenceCase = useResource<Schemas["CaseData"]>(
    c.api,
    row?.case_id ? path(c, `cases/${row.case_id}`) : null,
  );
  const action = useCommand();
  const [worksheet, setWorksheet] = useState<Record<string, unknown> | null>(
    null,
  );

  const save = (kind: string, payload: unknown) =>
    c.api.command<Schemas["ActionData"]>(
      path(c, `actions/${id}/${kind}`),
      payload,
    );

  const done = () => {
    detail.reload();
    reload();
    setWorksheet(null);
  };

  const drafts = row?.timeline.filter((e) => e.kind === "FOLLOWUP_DRAFT") || [];

  return (
    <article>
      <h2>Tracked business action</h2>
      <LoadState {...detail} empty={false} />
      {row && (
        <>
          <div className="controls">
            <Badge value={row.kind} />
            <Badge value={row.state} />
            <button className="secondary" onClick={detail.reload}>
              Refresh action
            </button>
          </div>
          <Facts
            values={{
              recorded_tax: money(row.source.recorded_tax),
              review_date: date(row.due_at),
              last_reminder: date(row.reminded_at),
              assigned_to: row.assigned_to,
              comparison_status: row.source.status,
              evidence_current: row.sources_current,
            }}
          />
          {!row.sources_current && (
            <Notice error>
              This action is historical or waiting on changed evidence. Refresh
              the current comparison/case before editing.
            </Notice>
          )}
          {row.source.review && (
            <Facts values={row.source.review as Record<string, unknown>} />
          )}
          <History rows={row.timeline} />
          {writable(c) && !detail.loading && (
            <SupplierDelivery c={c} item={row} changed={done} />
          )}
          {row.outcome && (
            <>
              <h3>Recorded review / observation</h3>
              <Facts values={row.outcome} />
            </>
          )}

          {writable(c) && row.sources_current && (
            <>
              <details>
                <summary>State, assignment and next review</summary>
                <form
                  key={row.version}
                  onSubmit={(e) => {
                    e.preventDefault();
                    const v = values(e.currentTarget);
                    void action.run(
                      () =>
                        save("update", {
                          expected_version: row.version,
                          reason: v.reason,
                          state: v.state,
                          assigned_to: v.assignee || null,
                          review_on: v.date || null,
                        }),
                      done,
                    );
                  }}
                >
                  <div className="grid">
                    <label>
                      Action state
                      <select name="state" defaultValue={row.state}>
                        {[
                          "OPEN",
                          "AWAITING_SUPPLIER",
                          "EVIDENCE_REQUIRED",
                          "REVIEW_REQUIRED",
                          "CLOSED",
                        ].map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Assignment
                      <select
                        name="assignee"
                        defaultValue={
                          row.assigned_to === c.user.user_id
                            ? c.user.user_id
                            : row.assigned_to || ""
                        }
                      >
                        <option value="">Unassigned</option>
                        <option value={c.user.user_id}>Assign to me</option>
                        {row.assigned_to &&
                          row.assigned_to !== c.user.user_id && (
                            <option value={row.assigned_to}>
                              Keep existing reviewer
                            </option>
                          )}
                      </select>
                    </label>
                    <Field
                      name="date"
                      type="date"
                      value={
                        row.due_at
                          ? new Date(row.due_at * 1000)
                              .toISOString()
                              .slice(0, 10)
                          : ""
                      }
                    >
                      Next recorded review date
                    </Field>
                  </div>
                  <Field name="reason" required>
                    Change reason
                  </Field>
                  <p className="muted">
                    Closing requires a recorded review outcome. Reopening clears
                    the previous closure outcome.
                  </p>
                  <button disabled={action.busy || detail.loading}>
                    Save action state
                  </button>
                </form>
              </details>

              {row.state !== "CLOSED" && (
                <>
                  <details>
                    <summary>Create supplier follow-up draft</summary>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const v = values(e.currentTarget);
                        void action.run(
                          () =>
                            save("followups", {
                              expected_version: row.version,
                              reason: v.reason,
                              kind: "DRAFT",
                              contact: v.contact,
                              request: v.request,
                            }),
                          done,
                        );
                      }}
                    >
                      <Field name="contact" required maxLength={200}>
                        Explicit supplier phone (+country code) or email
                      </Field>
                      <Field name="request" required>
                        Requested correction / evidence
                      </Field>
                      <Field name="reason" required>
                        Draft reason
                      </Field>
                      <button disabled={action.busy || detail.loading}>
                        Save private draft
                      </button>
                      <small>No message is sent by this website.</small>
                    </form>
                  </details>

                  {drafts.length > 0 && (
                    <details>
                      <summary>Record an operator contact attempt</summary>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          const v = values(e.currentTarget);
                          const draft = drafts.find((x) => x.id === v.draft);
                          const source = draft?.snapshot as
                            Record<string, unknown> | undefined;
                          if (!draft || !source) return;
                          void action.run(
                            () =>
                              save("followups", {
                                expected_version: row.version,
                                reason: v.reason,
                                kind: "ATTEMPT_RECORDED",
                                draft_id: draft.id,
                                contact: source.contact,
                                request: source.request,
                                observed_on: v.observed,
                              }),
                            done,
                          );
                        }}
                      >
                        <label>
                          Saved draft
                          <select name="draft">
                            {drafts.map((d) => (
                              <option key={String(d.id)} value={String(d.id)}>
                                {String(d.id).slice(0, 8)} ·{" "}
                                {text(
                                  (d.snapshot as Record<string, unknown>)
                                    ?.contact,
                                )}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Actual attempt observation date
                          <input
                            type="date"
                            name="observed"
                            required
                            max={utcDay()}
                          />
                        </label>
                        <Field name="reason" required>
                          What happened
                        </Field>
                        <button disabled={action.busy || detail.loading}>
                          Record unverified contact attempt
                        </button>
                      </form>
                    </details>
                  )}

                  <details>
                    <summary>Record a review decision</summary>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const v = values(e.currentTarget);
                        void action.run(
                          () =>
                            save("outcomes", {
                              expected_version: row.version,
                              reason: v.reason,
                              kind: "REVIEW_DECISION",
                              decision: v.decision,
                              amount: v.amount || null,
                            }),
                          done,
                        );
                      }}
                    >
                      <label>
                        Review decision
                        <select name="decision">
                          <option value="EVIDENCE_REQUIRED">
                            More evidence required
                          </option>
                          <option value="REVIEW_ACCEPTED">
                            Review accepted
                          </option>
                          <option value="REJECTED">Review rejected</option>
                        </select>
                      </label>
                      <Field name="amount">
                        Reviewed amount (INR, optional)
                      </Field>
                      <Field name="reason" required>
                        Review reason
                      </Field>
                      <button disabled={action.busy || detail.loading}>
                        Save review outcome
                      </button>
                    </form>
                  </details>

                  {row.case_id &&
                    ["RULE37A_REVIEW", "NOTICE_REVIEW"].includes(row.kind) && (
                      <details>
                        <summary>
                          Record an actual filing / notice submission
                          observation
                        </summary>
                        <Notice>
                          This records what the operator reports. GSTShield does
                          not submit or government-verify it. First accept the
                          review and select matching document evidence in the
                          linked case.
                        </Notice>
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            const v = new FormData(e.currentTarget);
                            void action.run(
                              () =>
                                save("outcomes", {
                                  expected_version: row.version,
                                  reason: v.get("reason"),
                                  kind:
                                    row.kind === "RULE37A_REVIEW"
                                      ? "FILING_OBSERVATION"
                                      : "NOTICE_SUBMISSION_OBSERVATION",
                                  reference: v.get("reference"),
                                  amount: v.get("amount") || null,
                                  observed_on: v.get("observed"),
                                  evidence_event_ids: v.getAll("evidence"),
                                }),
                              done,
                            );
                          }}
                        >
                          <Field name="reference" required maxLength={200}>
                            Actual filing / submission reference
                          </Field>
                          {row.kind === "RULE37A_REVIEW" && (
                            <Field name="amount" required>
                              Reported reclaimed GST (INR)
                            </Field>
                          )}
                          <label>
                            Observation date
                            <input
                              name="observed"
                              type="date"
                              required
                              max={utcDay()}
                            />
                          </label>
                          <fieldset>
                            <legend>Selected case evidence</legend>
                            <LoadState {...evidenceCase} empty={false} />
                            {Array.isArray(row.source.evidence_event_ids) &&
                              row.source.evidence_event_ids.map((ref) => (
                                <label className="check" key={String(ref)}>
                                  <input
                                    name="evidence"
                                    type="checkbox"
                                    value={String(ref)}
                                  />
                                  {label(
                                    String(
                                      evidenceCase.data?.timeline.find(
                                        (e) => e.id === ref,
                                      )?.kind || "Recorded evidence",
                                    ),
                                  )}{" "}
                                  · {String(ref).slice(0, 8)}
                                </label>
                              ))}
                          </fieldset>
                          <Field name="reason" required>
                            Observation reason
                          </Field>
                          <button disabled={action.busy || detail.loading}>
                            Record user-reported submission
                          </button>
                        </form>
                      </details>
                    )}
                </>
              )}
            </>
          )}
          {action.feedback}
          <div className="controls">
            <button
              className="secondary"
              disabled={action.busy || detail.loading}
              onClick={() =>
                void action.run(
                  () =>
                    c.api.get<Record<string, unknown>>(
                      path(c, `actions/${id}/worksheet`),
                    ),
                  setWorksheet,
                  "Worksheet loaded.",
                )
              }
            >
              Open review worksheet
            </button>
          </div>
          {worksheet && (
            <>
              <Notice>
                Review worksheet only. No return has been filed; recovery is not
                guaranteed.
              </Notice>
              <Facts values={worksheet} />
            </>
          )}
        </>
      )}
    </article>
  );
}

export default function Actions({ c }: { c: Context }) {
  const [cursor, setCursor] = useState("");
  const [state, setState] = useState("");
  const [due, setDue] = useState(false);
  const [selected, setSelected] = useState("");

  const list = useResource<Schemas["ActionListData"]>(
    c.api,
    path(
      c,
      `actions?limit=20&registration_id=${c.registration.id}&period=${c.period}&due_only=${due}${state ? `&state=${state}` : ""}${cursor ? `&cursor=${cursor}` : ""}`,
    ),
    10000,
  );

  return (
    <>
      <p>
        Retained issues move through evidence changes, review and follow-up.
        Reminders run locally while the backend is on.
      </p>
      <div className="controls">
        <label>
          Action state
          <select
            value={state}
            onChange={(e) => {
              setState(e.target.value);
              setCursor("");
            }}
          >
            <option value="">All states</option>
            {[
              "OPEN",
              "AWAITING_SUPPLIER",
              "EVIDENCE_REQUIRED",
              "REVIEW_REQUIRED",
              "CLOSED",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={due}
            onChange={(e) => {
              setDue(e.target.checked);
              setCursor("");
            }}
          />
          Due for recorded review
        </label>
        <button className="secondary" onClick={list.reload}>
          Check latest actions
        </button>
      </div>
      <LoadState {...list} empty={!list.data?.actions.length} />
      {list.data && (
        <>
          {(list.data.automation.pending_sources > 0 ||
            list.data.automation.error_code) && (
            <Notice error>
              Checks are incomplete: {list.data.automation.pending_sources}{" "}
              sources pending.{" "}
              {list.data.automation.error_code || "Refresh after processing."}
            </Notice>
          )}
          <div
            className="table-wrap"
            tabIndex={0}
            role="region"
            aria-label="Business actions table"
          >
            <table>
              <thead>
                <tr>
                  <th>Issue / invoice</th>
                  <th>Recorded GST</th>
                  <th>State</th>
                  <th>Review date</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {list.data.actions
                  .filter(
                    (r) =>
                      r.registration_id === c.registration.id &&
                      r.period === c.period,
                  )
                  .map((row) => (
                    <tr key={row.id}>
                      <td>
                        {row.kind}
                        <br />
                        <small>
                          {text(
                            (row.source.invoice as Record<string, unknown>)
                              ?.invoice_number,
                          )}
                        </small>
                      </td>
                      <td>{money(row.source.recorded_tax)}</td>
                      <td>
                        <Badge value={row.state} />
                      </td>
                      <td>{date(row.due_at)}</td>
                      <td>
                        <button onClick={() => setSelected(row.id)}>
                          Open action
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
              First actions
            </button>
            <button
              className="secondary"
              disabled={!list.data.next_cursor}
              onClick={() => setCursor(list.data!.next_cursor!)}
            >
              Next actions
            </button>
          </div>
        </>
      )}
      {selected && !list.denied && (
        <ActionDetail key={selected} c={c} id={selected} reload={list.reload} />
      )}
    </>
  );
}
