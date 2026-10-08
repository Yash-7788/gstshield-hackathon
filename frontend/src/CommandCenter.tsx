import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { Schemas } from "./contracts";
import InvoiceItems, { itemsFrom } from "./InvoiceItems";
import { InvoiceGuide } from "./GuidedHelp";
import InvoiceReview from "./InvoiceReview";
import type { InvoiceNavigate } from "./InvoiceJourney";
import {
  Field,
  LoadState,
  money,
  Notice,
  path,
  text,
  useCommand,
  useResource,
  writable,
} from "./shared";
import type { Context } from "./shared";

type Passport = Schemas["PassportData"];
type Result = Record<string, unknown>;
const display = (value: unknown) => (value == null ? "" : String(value));
const formValues = (event: FormEvent<HTMLFormElement>) => {
  event.preventDefault();
  return Object.fromEntries(new FormData(event.currentTarget).entries());
};
const today = () => new Date().toISOString().slice(0, 10);
const valueLabels: Record<string, string> = {
  supplier_gstin: "Supplier GST number",
  supplier_name: "Supplier name",
  invoice_number: "Invoice number",
  invoice_date: "Invoice date",
  taxable_value: "Goods value",
  igst: "IGST",
  cgst: "CGST",
  sgst: "SGST",
  cess: "Cess",
  other_charges: "Other charges",
  round_off: "Rounding",
  gross_total: "Invoice total",
  quantity: "Total quantity",
  irn: "E-invoice reference",
};
const labels: Record<string, string> = {
  MATCHED: "Matches",
  MISSING: "Missing",
  MISMATCH: "Does not match",
  REVIEW: "Needs review",
  DUPLICATE: "Possible duplicate",
  PAY: "Pay",
  HOLD: "Hold payment",
  ESCALATE: "Ask an approver",
  PARTIAL_CONTROLLED_PAYMENT: "Part payment",
  HUMAN_REVIEW: "Review first",
  ACCEPT: "Accept",
  REJECT: "Reject",
  PENDING: "Keep pending",
  CORRECTION_RECEIVED: "Correction reported; checking records",
  VERIFIED: "Phone verified",
  AWAITING_CONSENT: "Waiting for supplier opt-in",
  NOT_CONNECTED: "Supplier phone not connected",
  QUEUED: "Message queued",
  DELIVERED: "Delivered",
  READ: "Read",
  UNKNOWN: "Send outcome uncertain",
  CANCELLED: "Send cancelled",
  FAILED: "Send failed",
  CURRENT: "Current",
  SHARED_BANK_ACCOUNT: "Shared bank account",
  REPEATED_AMOUNT: "Repeated invoice amount",
  AMOUNT_OUTLIER: "Unusual invoice amount",
  TAX_RATE_PATTERN: "Tax ratio needs review",
  MISSING_IRN: "Required e-invoice reference missing",
  IRN_FORMAT: "E-invoice reference needs review",
  FUTURE_INVOICE_DATE: "Future invoice date",
  RECORD_MISMATCH: "Records differ",
  APPROVED: "Approved",
  STALE: "Review again",
  NOT_STARTED: "Not started",
  DRAFT: "Request prepared",
  ACKNOWLEDGED: "Supplier acknowledged",
  PROMISED: "Correction promised",
  RESOLVED: "Resolved",
  ESCALATED: "Escalated",
  REVIEW_REQUIRED: "Review again",
  E_INVOICE_REFERENCE_FORMAT: "E-invoice reference needs review",
};
const plain = (value: unknown) => labels[display(value)] || display(value);
const nested = (value: unknown): Result =>
  value && typeof value === "object" ? (value as Result) : {};

export default function CommandCenter({
  c,
  initialInvoiceId,
  navigate,
}: {
  c: Context;
  initialInvoiceId?: string;
  navigate: InvoiceNavigate;
}) {
  const [tab, setTab] = useState("Invoices");
  const [selected, select] = useState(initialInvoiceId || "");
  const query =
    "registration_id=" +
    c.registration.id +
    "&period=" +
    encodeURIComponent(c.period);
  const records = useResource<Schemas["PassportListData"]>(
    c.api,
    path(c, "passports?" + query),
    8000,
  );
  const sources = useResource<Schemas["ImportListData"]>(
    c.api,
    path(c, "imports?" + query + "&limit=100"),
    8000,
  );
  const cases = useResource<Schemas["CaseListData"]>(
    c.api,
    path(c, "cases?" + query + "&limit=100"),
  );
  const action = useCommand();
  const [answer, setAnswer] = useState<Result | null>(null);
  const [watch, setWatch] = useState(false);
  const [invitation, setInvitation] = useState<{
    id: string;
    data: Result;
  } | null>(null);
  const invoices = records.data?.passports || [];
  const current = invoices.find((p) => p.id === selected);
  const canWrite = writable(c);
  const update = (invoice: Passport) => {
    select(invoice.id);
    records.reload();
    sources.reload();
  };
  const submit = (suffix: string, payload: unknown) =>
    void action.run(
      () =>
        c.api.command<Passport>(
          path(c, "passports/" + selected + "/" + suffix),
          payload,
        ),
      update,
      "Saved.",
    );
  useEffect(() => {
    if (!invitation) return;
    const milliseconds = Math.max(
      0,
      Number(invitation.data.expires_at) * 1000 - Date.now(),
    );
    const timer = window.setTimeout(() => setInvitation(null), milliseconds);
    return () => window.clearTimeout(timer);
  }, [invitation]);
  useEffect(() => {
    setInvitation(null);
  }, [selected]);
  useEffect(() => {
    if (!watch || !canWrite || !selected) return;
    let cancelled = false;
    const controller = new AbortController();
    const timer = window.setInterval(() => {
      if (document.hidden || cancelled) return;
      void c.api
        .command<Passport>(path(c, "passports/" + selected + "/refresh"), {})
        .then(() => {
          if (!cancelled) records.reload();
        })
        .catch(() => {
          if (!cancelled) setWatch(false);
        });
    }, 15000);
    return () => {
      cancelled = true;
      controller.abort();
      clearInterval(timer);
    };
  }, [watch, canWrite, selected, c.api, c.workspace.id, records.reload]);
  return (
    <section className="command-center">
      <header>
        <h2>One invoice. Every next step.</h2>
        <p>
          Bring in the bill, connect its evidence and review what happens next.
        </p>
      </header>
      <nav className="desk-tabs" aria-label="Invoice desk tools">
        {["Invoices", "Suppliers", "Finance", "Watch & outcomes"].map(
          (name) => (
            <button
              key={name}
              aria-current={tab === name ? "page" : undefined}
              onClick={() => setTab(name)}
            >
              {name}
            </button>
          ),
        )}
      </nav>
      {action.feedback}
      <LoadState
        loading={records.loading}
        refreshing={records.refreshing}
        error={records.error}
        reload={records.reload}
        empty={false}
      />
      {tab === "Invoices" && (
        <>
          <details className="card" open={!invoices.length}>
            <summary>Start with an invoice</summary>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                data.set("registration_id", c.registration.id);
                data.set("period", c.period);
                data.set("consent", data.get("consent") ? "true" : "false");
                const file = data.get("file") as File;
                void action.run(
                  () =>
                    c.api.upload<Passport>(
                      path(c, "passports/documents"),
                      data,
                      c.registration.id +
                        c.period +
                        file.name +
                        file.size +
                        file.lastModified,
                    ),
                  update,
                  "Invoice saved. Review the proposed details.",
                );
              }}
            >
              <label>
                Invoice PDF or photo
                <input
                  name="file"
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  required
                />
              </label>
              <label className="check">
                <input type="checkbox" name="consent" required />
                Allow Google AI to read this invoice.
              </label>
              <button disabled={!canWrite || action.busy}>Read invoice</button>
            </form>
            <details>
              <summary>Use an invoice already uploaded</summary>
              <form
                onSubmit={(event) => {
                  const data = formValues(event);
                  void action.run(
                    () =>
                      c.api.command<Passport>(
                        path(c, "passports/from-source"),
                        {
                          registration_id: c.registration.id,
                          period: c.period,
                          purchase_import_id: data.source,
                          row_number: Number(data.row),
                        },
                      ),
                    update,
                  );
                }}
              >
                <label>
                  Purchase source
                  <select name="source" required>
                    <option value="">Choose a source</option>
                    {(sources.data?.imports || [])
                      .filter(
                        (s) => s.kind === "PURCHASE" && s.state === "READY",
                      )
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.id.slice(0, 8)} · {s.accepted_rows} invoices
                        </option>
                      ))}
                  </select>
                </label>
                <Field name="row" type="number" value="1" required>
                  Invoice row
                </Field>
                <button disabled={!canWrite || action.busy}>
                  Open invoice
                </button>
              </form>
            </details>
          </details>
          <div className="desk-layout">
            <aside className="invoice-list" aria-label="Saved invoices">
              {!invoices.length && <p>Your invoices will appear here.</p>}
              {invoices.map((p) => (
                <button
                  key={p.id}
                  aria-current={selected === p.id ? "true" : undefined}
                  onClick={() => {
                    select(p.id);
                    setAnswer(null);
                  }}
                >
                  <strong>
                    {display(p.fields.invoice_number) || p.filename}
                  </strong>
                  <span>
                    {display(p.fields.supplier_name) ||
                      "Supplier details pending"}
                  </span>
                  <small>
                    {plain(p.findings.summary)} · {money(p.fields.gross_total)}
                  </small>
                </button>
              ))}
            </aside>
            {current ? (
              <main className="invoice-detail">
                <header>
                  <h3>
                    {display(current.fields.invoice_number) || current.filename}
                  </h3>
                  <p>{display(current.fields.supplier_name)}</p>
                </header>
                {current.confirmed && (
                  <div className="controls" aria-label="Continue this invoice">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => navigate("Cases & evidence", current.id)}
                    >
                      Cases for this invoice
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => navigate("Payment drafts", current.id)}
                    >
                      Payment drafts for this invoice
                    </button>
                  </div>
                )}
                {!current.confirmed ? (
                  <section className="card">
                    <h3>1. Confirm invoice details</h3>
                    {["FAILED", "PENDING"].includes(
                      display(current.extraction.status),
                    ) && (
                      <Notice error>
                        {current.extraction.status === "PENDING"
                          ? "Invoice reading is waiting. Try again shortly."
                          : text(current.extraction.message)}{" "}
                        <button
                          disabled={action.busy || !canWrite}
                          onClick={() => submit("retry-extraction", {})}
                        >
                          Try AI again
                        </button>
                      </Notice>
                    )}
                    {current.extraction.status === "AWAITING_REVIEW" && (
                      <Notice>
                        Check these proposed details against your invoice before
                        continuing.
                      </Notice>
                    )}
                    <form
                      key={current.id + ":" + current.version}
                      className="desk-form"
                      onSubmit={(event) => {
                        const data = formValues(event);
                        const fields = Object.fromEntries(
                          Object.keys(valueLabels).map((k) => [
                            k,
                            data[k] ||
                              ([
                                "igst",
                                "cgst",
                                "sgst",
                                "cess",
                                "quantity",
                              ].includes(k)
                                ? null
                                : ["other_charges", "round_off"].includes(k)
                                  ? "0.00"
                                  : ""),
                          ]),
                        );
                        submit("confirm", {
                          expected_version: current.version,
                          fields: {
                            ...fields,
                            items: itemsFrom(data),
                            supplier_bank_account: data.bank || null,
                          },
                        });
                      }}
                    >
                      {Object.entries(valueLabels).map(([name, label]) => (
                        <Field
                          key={name}
                          name={name}
                          type={name === "invoice_date" ? "date" : "text"}
                          value={display(current.fields[name])}
                          required={[
                            "supplier_gstin",
                            "invoice_number",
                            "invoice_date",
                            "taxable_value",
                            "gross_total",
                          ].includes(name)}
                        >
                          {label}
                        </Field>
                      ))}
                      <Field
                        name="bank"
                        value={display(current.fields.supplier_bank_account)}
                      >
                        Supplier bank account, if printed
                      </Field>
                      <InvoiceItems
                        key={current.id + ":" + current.version}
                        value={current.fields.items}
                      />
                      <button disabled={!canWrite || action.busy}>
                        Confirm details
                      </button>
                    </form>
                    {Array.isArray(current.extraction.uncertainties) && (
                      <ul>
                        {current.extraction.uncertainties.map((v, i) => (
                          <li key={i}>{text(v)}</li>
                        ))}
                      </ul>
                    )}
                  </section>
                ) : (
                  <>
                    <div className="desk-stats">
                      <div>
                        Invoice total
                        <strong>{money(current.fields.gross_total)}</strong>
                      </div>
                      <div>
                        Tax needs attention
                        <strong>
                          {money(current.gate.recorded_tax_under_review)}
                        </strong>
                      </div>
                      <div>
                        Unpaid balance
                        <strong>{money(current.gate.remaining_amount)}</strong>
                      </div>
                    </div>
                    <section className="card">
                      <h3>1. Check the four records</h3>
                      <div className="match-grid">
                        {[
                          ["Invoice", "invoice"],
                          ["Purchase order", "po"],
                          ["Delivery receipt", "receipt"],
                          ["GST statement", "gst"],
                        ].map(([name, k]) => (
                          <div key={k}>
                            <strong>{name}</strong>
                            <span>
                              {k === "invoice"
                                ? "Confirmed"
                                : plain(current.findings[k])}
                            </span>
                          </div>
                        ))}
                      </div>
                      {nested(current.findings.gst_source).provenance ===
                        "SYNTHETIC_DEMO" && (
                        <Notice>
                          GST comparison uses a simulated statement.
                        </Notice>
                      )}
                      <p>
                        Compare the actual items, quantities, units and goods
                        values. Missing item details require review.
                      </p>
                      {["PO", "RECEIPT"].map((kind) => (
                        <details key={kind}>
                          <summary>
                            {kind === "PO"
                              ? "Add purchase order details"
                              : "Add delivery receipt details"}
                          </summary>
                          <form
                            className="desk-form"
                            onSubmit={(event) => {
                              const data = formValues(event);
                              submit("evidence", {
                                expected_version: current.version,
                                kind,
                                reference: data.reference,
                                taxable_value: data.taxable_value,
                                quantity: data.quantity || null,
                                items: itemsFrom(data),
                                observed_on: data.observed_on,
                                note: data.note || "",
                              });
                            }}
                          >
                            <Field name="reference" required>
                              Reference number
                            </Field>
                            <Field name="taxable_value" required>
                              Goods value
                            </Field>
                            <Field name="quantity">
                              Total quantity, if known
                            </Field>
                            <Field
                              name="observed_on"
                              type="date"
                              value={today()}
                              required
                            >
                              Date
                            </Field>
                            <Field name="note">Note</Field>
                            <InvoiceItems
                              key={
                                current.id + ":" + kind + ":" + current.version
                              }
                            />
                            <button disabled={!canWrite || action.busy}>
                              Save {kind === "PO" ? "order" : "receipt"}
                            </button>
                          </form>
                        </details>
                      ))}
                      {["po", "receipt"].map((kind) => (
                        <details key={kind}>
                          <summary>
                            {kind === "po"
                              ? "Order item comparison"
                              : "Delivery item comparison"}
                          </summary>
                          <p>
                            {text(
                              nested(current.findings[kind + "_items"]).reason,
                            )}
                          </p>
                          {Array.isArray(
                            nested(current.findings[kind + "_items"]).lines,
                          ) &&
                            (
                              nested(current.findings[kind + "_items"])
                                .lines as Result[]
                            ).map((line, index) => (
                              <p key={index}>
                                <strong>{text(line.item)}</strong> ·{" "}
                                {plain(line.status)}. Invoice:{" "}
                                {text(line.invoice_quantity)} /{" "}
                                {money(line.invoice_value)}. Record:{" "}
                                {text(line.record_quantity)} /{" "}
                                {money(line.record_value)}.
                              </p>
                            ))}
                        </details>
                      ))}
                      <details>
                        <summary>Choose GST statement</summary>
                        <form
                          onSubmit={(event) => {
                            const data = formValues(event);
                            submit("portal", {
                              expected_version: current.version,
                              import_id: data.source,
                            });
                          }}
                        >
                          <label>
                            Confirmed statement
                            <select name="source" required>
                              <option value="">Choose a source</option>
                              {(sources.data?.imports || [])
                                .filter(
                                  (s) =>
                                    s.kind === "PORTAL_2B" &&
                                    s.state === "READY",
                                )
                                .map((s) => (
                                  <option key={s.id} value={s.id}>
                                    {s.provenance === "SYNTHETIC_DEMO"
                                      ? "Sample statement"
                                      : "Uploaded statement"}{" "}
                                    · {s.id.slice(0, 8)}
                                  </option>
                                ))}
                            </select>
                          </label>
                          <button disabled={!canWrite || action.busy}>
                            Compare statement
                          </button>
                        </form>
                      </details>
                    </section>
                    <section className="card">
                      <h3>2. Review payment dates</h3>
                      <div className="match-grid">
                        {[
                          ["Supplier pay-by", current.clocks.pay_by],
                          [
                            "Buyer payment review",
                            current.clocks.buyer_payment_review_on,
                          ],
                          [
                            "Supplier filing review",
                            current.clocks.supplier_filing_review_on,
                          ],
                        ].map(([name, val]) => (
                          <div key={display(name)}>
                            <strong>{display(name)}</strong>
                            <span>{display(val) || "Details needed"}</span>
                          </div>
                        ))}
                      </div>
                      <details>
                        <summary>Record payment and timing facts</summary>
                        <form
                          className="desk-form"
                          onSubmit={(event) => {
                            const data = formValues(event);
                            submit("clocks", {
                              expected_version: current.version,
                              msme_covered:
                                data.msme === "" ? null : data.msme === "yes",
                              accepted_on: data.accepted_on || null,
                              agreed_days: data.agreed_days
                                ? Number(data.agreed_days)
                                : null,
                              claimed_on: data.claimed_on || null,
                              supplier_3b_due_on: data.supplier_due || null,
                              amount_paid: data.paid || null,
                              payment_observed_on:
                                data.payment_observed_on || null,
                              note: data.note || "",
                            });
                          }}
                        >
                          <label>
                            MSME timing applies?
                            <select name="msme">
                              <option value="">Not confirmed</option>
                              <option value="yes">Yes</option>
                              <option value="no">No</option>
                            </select>
                          </label>
                          <Field name="accepted_on" type="date">
                            Goods accepted on
                          </Field>
                          <Field name="agreed_days" type="number">
                            Agreed payment days, up to 45
                          </Field>
                          <Field name="claimed_on" type="date">
                            Tax credit claimed on
                          </Field>
                          <Field name="supplier_due" type="date">
                            Supplier filing review date
                          </Field>
                          <Field
                            name="paid"
                            value={
                              display(
                                nested(current.clocks.facts).amount_paid,
                              ) || ""
                            }
                          >
                            Already paid
                          </Field>
                          <Field name="payment_observed_on" type="date">
                            Payment checked on
                          </Field>
                          <Field name="note">Note</Field>
                          <button disabled={!canWrite || action.busy}>
                            Save dates
                          </button>
                        </form>
                      </details>
                    </section>
                    <section className="card">
                      <h3>3. Decide payment</h3>
                      {!current.gate.payment_facts_confirmed && (
                        <Notice>
                          Record the already-paid amount in step 2 before
                          approving a payment.
                        </Notice>
                      )}
                      <h4>{plain(current.gate.recommendation)}</h4>
                      <p>{text(current.gate.reason)}</p>
                      {current.approval && (
                        <Notice>
                          Decision: {plain(current.approval.decision)} ·{" "}
                          {money(current.approval.amount)} ·{" "}
                          {plain(current.approval.state)}
                          {current.approval.state === "STALE" &&
                            " — evidence changed. Review before proceeding."}
                        </Notice>
                      )}
                      <p>
                        Save an approval here. Transfer money through your
                        normal bank process.
                      </p>
                      <form
                        className="desk-form"
                        key={current.id + ":gate:" + current.source_signature}
                        onSubmit={(event) => {
                          const data = formValues(event);
                          submit("approve", {
                            expected_version: current.version,
                            source_signature: current.source_signature,
                            decision: data.decision,
                            amount: data.amount,
                            reason: data.reason,
                          });
                        }}
                      >
                        <label>
                          Decision
                          <select
                            name="decision"
                            defaultValue={
                              current.gate.recommendation === "REVIEW"
                                ? "HOLD"
                                : display(current.gate.recommendation)
                            }
                          >
                            <option value="PAY">Full payment</option>
                            <option value="PARTIAL_CONTROLLED_PAYMENT">
                              Part payment
                            </option>
                            <option value="HOLD">Hold payment</option>
                            <option value="ESCALATE">Ask an approver</option>
                          </select>
                        </label>
                        <Field
                          name="amount"
                          value={
                            current.gate.recommendation ===
                            "PARTIAL_CONTROLLED_PAYMENT"
                              ? display(current.gate.suggested_part_payment)
                              : "0.00"
                          }
                          required
                        >
                          Approved amount
                        </Field>
                        <Field name="reason" required>
                          Reason, at least 10 characters
                        </Field>
                        <button disabled={!canWrite || action.busy}>
                          Save decision
                        </button>
                      </form>
                    </section>
                    <details className="card">
                      <summary>
                        Simulated bank — check payment protection
                      </summary>
                      <Notice>
                        Simulated money. This does not contact a bank or change
                        recorded real payments.
                      </Notice>
                      <div className="desk-stats">
                        <div>
                          Simulated money released
                          <strong>
                            {money(nested(current.demo_bank).released_amount)}
                          </strong>
                        </div>
                        <div>
                          Simulated balance held
                          <strong>
                            {money(nested(current.demo_bank).remaining_amount)}
                          </strong>
                        </div>
                        <div>
                          Tax still protected
                          <strong>
                            {money(nested(current.demo_bank).tax_protected)}
                          </strong>
                        </div>
                      </div>
                      <p>
                        Permitted release now:{" "}
                        {money(nested(current.demo_bank).allowed_amount)}. A
                        changed record needs a fresh approval.
                      </p>
                      <div className="button-row">
                        <button
                          disabled={!canWrite || action.busy}
                          onClick={() =>
                            submit("demo-bank-payment", {
                              expected_version: current.version,
                              source_signature: current.source_signature,
                              amount:
                                nested(current.demo_bank).remaining_amount ||
                                current.fields.gross_total,
                            })
                          }
                        >
                          Try paying the balance
                        </button>
                        <button
                          disabled={
                            !canWrite ||
                            action.busy ||
                            nested(current.demo_bank).allowed_amount === "0.00"
                          }
                          onClick={() =>
                            submit("demo-bank-payment", {
                              expected_version: current.version,
                              source_signature: current.source_signature,
                              amount: nested(current.demo_bank).allowed_amount,
                            })
                          }
                        >
                          Release permitted simulated amount
                        </button>
                      </div>
                      {nested(current.demo_bank).last_attempt != null && (
                        <Notice
                          error={
                            nested(nested(current.demo_bank).last_attempt)
                              .status === "BLOCKED"
                          }
                        >
                          <strong>
                            {nested(nested(current.demo_bank).last_attempt)
                              .status === "BLOCKED"
                              ? "Payment blocked"
                              : "Simulated payment released"}
                          </strong>{" "}
                          ·{" "}
                          {money(
                            nested(nested(current.demo_bank).last_attempt)
                              .amount,
                          )}
                          .{" "}
                          {text(
                            nested(nested(current.demo_bank).last_attempt)
                              .reason,
                          )}
                        </Notice>
                      )}
                      <details>
                        <summary>Simulated transfer history</summary>
                        {Array.isArray(nested(current.demo_bank).attempts) &&
                          (nested(current.demo_bank).attempts as Result[]).map(
                            (attempt, index) => (
                              <p key={index}>
                                {attempt.status === "BLOCKED"
                                  ? "Blocked"
                                  : "Released"}{" "}
                                · {money(attempt.amount)} ·{" "}
                                {text(attempt.reason)}
                              </p>
                            ),
                          )}
                      </details>
                    </details>
                    <section className="card">
                      <h3>4. Request correction</h3>
                      <p>{plain(current.resolution.state)}</p>
                      {typeof current.resolution.draft === "string" && (
                        <blockquote>{current.resolution.draft}</blockquote>
                      )}
                      {current.resolution.delivery === "NOT_SENT" &&
                        current.resolution.state !== "NOT_STARTED" && (
                          <Notice>
                            Request prepared. Send through your connected
                            messaging channel.
                          </Notice>
                        )}
                      <div className="button-row">
                        <button
                          disabled={!canWrite || action.busy}
                          onClick={() =>
                            submit("resolution", {
                              expected_version: current.version,
                              action: "DRAFT",
                            })
                          }
                        >
                          Prepare supplier request
                        </button>
                        {typeof current.resolution.draft === "string" && (
                          <button
                            onClick={() =>
                              void navigator.clipboard.writeText(
                                display(current.resolution.draft),
                              )
                            }
                          >
                            Copy message
                          </button>
                        )}
                        <a href="#WhatsApp">WhatsApp setup</a>
                      </div>
                      <details>
                        <summary>Connect supplier WhatsApp</summary>
                        <p>
                          {plain(nested(current.supplier_channel).state)}{" "}
                          {display(
                            nested(current.supplier_channel).masked_phone,
                          )}
                        </p>
                        {!records.data?.provider.whatsapp_configured && (
                          <Notice>
                            Set up the business WhatsApp account and callback in
                            WhatsApp setup to send and receive messages.
                          </Notice>
                        )}
                        <form
                          onSubmit={(event) => {
                            const data = formValues(event);
                            void action.run(
                              () =>
                                c.api.command<Result>(
                                  path(
                                    c,
                                    "passports/" +
                                      selected +
                                      "/supplier-invite",
                                  ),
                                  {
                                    expected_version: current.version,
                                    phone: data.phone,
                                  },
                                ),
                              (result) => {
                                setInvitation({ id: current.id, data: result });
                                records.reload();
                              },
                              "Supplier invitation ready.",
                            );
                          }}
                        >
                          <Field name="phone" required>
                            Supplier phone with country code
                          </Field>
                          <button
                            disabled={
                              !canWrite ||
                              action.busy ||
                              !records.data?.provider.whatsapp_configured
                            }
                          >
                            Create opt-in invitation
                          </button>
                        </form>
                        {invitation?.id === current.id && (
                          <Notice>
                            {text(invitation.data.instruction)} Code expires in
                            10 minutes.
                          </Notice>
                        )}
                        <button
                          disabled={
                            !canWrite ||
                            action.busy ||
                            nested(current.supplier_channel).state !==
                              "VERIFIED" ||
                            !nested(current.supplier_channel)
                              .sending_configured ||
                            !current.resolution.draft
                          }
                          onClick={() =>
                            submit("supplier-send", {
                              expected_version: current.version,
                            })
                          }
                        >
                          Send correction request
                        </button>
                        {nested(current.supplier_channel).delivery != null && (
                          <p>
                            WhatsApp delivery:{" "}
                            {plain(
                              nested(nested(current.supplier_channel).delivery)
                                .state,
                            )}
                            .
                          </p>
                        )}
                        <p>
                          Supplier replies update this invoice automatically. A
                          reported correction is resolved after the saved
                          records match.
                        </p>
                      </details>
                      <details>
                        <summary>Record supplier response</summary>
                        <form
                          onSubmit={(event) => {
                            const data = formValues(event);
                            submit("resolution", {
                              expected_version: current.version,
                              action: data.state,
                              promised_on: data.promised_on || null,
                              note: data.note || "",
                            });
                          }}
                        >
                          <label>
                            Response
                            <select name="state">
                              <option value="ACKNOWLEDGED">Acknowledged</option>
                              <option value="PROMISED">
                                Correction promised
                              </option>
                              <option value="RESOLVED">Resolved</option>
                              <option value="ESCALATED">Escalate</option>
                            </select>
                          </label>
                          <Field name="promised_on" type="date">
                            Promised correction date
                          </Field>
                          <Field name="note">Supplier response</Field>
                          <button disabled={!canWrite || action.busy}>
                            Save response
                          </button>
                        </form>
                      </details>
                    </section>
                    <details className="card">
                      <summary>GST action guidance</summary>
                      <p>
                        {plain(current.findings.ims_recommendation)}.{" "}
                        {text(current.findings.ims_reason)}
                      </p>
                      <form
                        key={current.id + ":ims:" + current.version}
                        onSubmit={(event) => {
                          const data = formValues(event);
                          submit("ims-review", {
                            expected_version: current.version,
                            source_signature: current.source_signature,
                            action: data.action,
                            reason: data.reason,
                            confirm_rejection: data.confirm_rejection === "on",
                          });
                        }}
                      >
                        <label>
                          Reviewed action
                          <select
                            name="action"
                            defaultValue={display(
                              current.findings.ims_recommendation,
                            )}
                          >
                            <option value="ACCEPT">Accept</option>
                            <option value="REJECT">Reject</option>
                            <option value="PENDING">Keep pending</option>
                            <option value="HUMAN_REVIEW">
                              Needs a reviewer
                            </option>
                          </select>
                        </label>
                        <Field name="reason" required>
                          Reason, at least 10 characters
                        </Field>
                        <label className="check">
                          <input type="checkbox" name="confirm_rejection" />I
                          reviewed the reason for rejection, if rejecting.
                        </label>
                        <button disabled={!canWrite || action.busy}>
                          Save GST review
                        </button>
                      </form>
                      {current.findings.ims_review != null && (
                        <Notice>
                          Saved action:{" "}
                          {plain(nested(current.findings.ims_review).action)} ·{" "}
                          {plain(nested(current.findings.ims_review).state)}.{" "}
                          {text(nested(current.findings.ims_review).reason)}
                        </Notice>
                      )}
                      <p>
                        Review saved here. Take any submission action in your
                        authorized GST portal.
                      </p>
                    </details>
                    <details className="card">
                      <summary>Invoice details and history</summary>
                      <dl className="facts">
                        {Object.entries(valueLabels).map(([k, v]) => (
                          <div key={k}>
                            <dt>{v}</dt>
                            <dd>
                              {display(current.fields[k]) || "Not recorded"}
                            </dd>
                          </div>
                        ))}
                      </dl>
                      <details>
                        <summary>Update item and supplier facts</summary>
                        <form
                          key={current.id + ":details:" + current.version}
                          onSubmit={(event) => {
                            const data = formValues(event);
                            submit("details", {
                              expected_version: current.version,
                              items: itemsFrom(data),
                              supplier_bank_account: data.bank || null,
                              irn_required:
                                data.irn_required === ""
                                  ? null
                                  : data.irn_required === "yes",
                              payment_dispute:
                                data.dispute === ""
                                  ? null
                                  : data.dispute === "yes",
                            });
                          }}
                        >
                          <InvoiceItems value={current.fields.items} />
                          <Field
                            name="bank"
                            value={display(
                              current.fields.supplier_bank_account,
                            )}
                          >
                            Recorded supplier bank account
                          </Field>
                          <label>
                            E-invoice reference required?
                            <select
                              name="irn_required"
                              defaultValue={
                                current.fields.irn_required == null
                                  ? ""
                                  : current.fields.irn_required
                                    ? "yes"
                                    : "no"
                              }
                            >
                              <option value="">Not established</option>
                              <option value="yes">Yes, checked</option>
                              <option value="no">No, checked</option>
                            </select>
                          </label>
                          <label>
                            Payment disputed?
                            <select
                              name="dispute"
                              defaultValue={
                                current.fields.payment_dispute == null
                                  ? ""
                                  : current.fields.payment_dispute
                                    ? "yes"
                                    : "no"
                              }
                            >
                              <option value="">Not recorded</option>
                              <option value="yes">Yes</option>
                              <option value="no">No</option>
                            </select>
                          </label>
                          <button disabled={!canWrite || action.busy}>
                            Save item and supplier facts
                          </button>
                        </form>
                      </details>
                      <button
                        onClick={() =>
                          void action.run(() =>
                            c.api.download(
                              path(c, "passports/" + selected + "/dossier"),
                              "gstshield-passport_" + selected + ".pdf",
                            ),
                          )
                        }
                      >
                        Download history PDF
                      </button>
                      <ol className="timeline">
                        {current.history.map((e, i) => (
                          <li key={i}>
                            <strong>
                              {display(e.action)
                                .replaceAll("_", " ")
                                .toLowerCase()}
                            </strong>
                            <span>
                              {new Date(Number(e.at) * 1000).toLocaleString()}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </details>
                  </>
                )}
              </main>
            ) : (
              <div className="card">
                <p>Choose an invoice to continue.</p>
              </div>
            )}
          </div>
        </>
      )}

      {tab === "Invoices" && current && (
        <>
          <InvoiceGuide c={c} invoice={current} />
          <InvoiceReview
            key={current.id + current.source_signature}
            c={c}
            invoice={current}
          />
        </>
      )}
      {tab === "Suppliers" && (
        <>
          <section className="card">
            <h3>Supplier reliability</h3>
            <p>
              Scores use up to 250 saved invoices across periods. Small samples
              have limited history. Open the score explanation before deciding.
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th>Score</th>
                    <th>Invoices</th>
                    <th>Need attention</th>
                  </tr>
                </thead>
                <tbody>
                  {(records.data?.vendors || []).map((v) => (
                    <tr key={display(v.gstin)}>
                      <td>
                        {display(v.name) || display(v.gstin)}
                        <small>{display(v.gstin)}</small>
                      </td>
                      <td>
                        {display(v.score)}/100
                        <details>
                          <summary>Why this score?</summary>
                          <p>{text(v.basis)}</p>
                          <p>
                            {v.confidence === "LIMITED_HISTORY"
                              ? "Limited invoice history."
                              : "Based on observed invoice history."}
                          </p>
                          {Array.isArray(v.factors) &&
                            v.factors.map((factor: Result, index: number) => (
                              <p key={index}>
                                {text(factor.name)}: {text(factor.passed)} of{" "}
                                {text(factor.observed)}.
                              </p>
                            ))}
                          <p>
                            Tax under review:{" "}
                            {money(v.recorded_tax_under_review)}. Recorded
                            disputes: {text(v.recorded_disputes)}. Corrections
                            observed: {text(v.corrections_observed)}.
                          </p>
                          {Array.isArray(v.unknowns) &&
                            v.unknowns.length > 0 && (
                              <p>
                                Still unknown: {v.unknowns.map(text).join(", ")}
                                .
                              </p>
                            )}
                        </details>
                      </td>
                      <td>{display(v.invoices)}</td>
                      <td>{display(v.issues)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="card">
            <h3>Unusual invoices</h3>
            <p>These signals need review before treating them as fraud.</p>
            {!records.data?.anomalies.length && (
              <p>No flagged patterns in saved invoices.</p>
            )}
            {records.data?.anomalies.map((v, i) => (
              <button
                key={i}
                onClick={() => {
                  select(display(v.invoice_id));
                  setTab("Invoices");
                }}
              >
                {display(v.invoice_number)} · {plain(v.signal)}
                <small>{text(v.meaning)}</small>
              </button>
            ))}
          </section>
        </>
      )}
      {tab === "Finance" && (
        <>
          <div className="desk-stats">
            <div>
              Tax needs attention
              <strong>
                {money(records.data?.metrics.recorded_itc_under_review)}
              </strong>
            </div>
            <div>
              Tax in matching records
              <strong>
                {money(records.data?.metrics.evidence_aligned_itc)}
              </strong>
            </div>
            <div>
              Invoices tracked
              <strong>
                {text(records.data?.metrics.unique_confirmed_invoices)}
              </strong>
            </div>
          </div>
          <section className="card">
            <h3>Ask about today's priorities</h3>
            <form
              onSubmit={(event) => {
                const data = formValues(event);
                void action.run(
                  () =>
                    c.api.command<Result>(path(c, "passports/intelligence"), {
                      registration_id: c.registration.id,
                      period: c.period,
                      question: data.question,
                      use_ai: data.ai === "on",
                    }),
                  setAnswer,
                  "Summary ready.",
                );
              }}
            >
              <Field
                name="question"
                value="What should I worry about today?"
                required
              >
                Your question
              </Field>
              <label className="check">
                <input name="ai" type="checkbox" />
                Use Google AI to explain saved finance facts.
              </label>
              <button disabled={action.busy}>Show priorities</button>
            </form>
            {answer?.answer != null && (
              <article>
                <p>{text(answer.answer)}</p>
                {Array.isArray(answer.tasks) &&
                  answer.tasks.map((t: Result, i) => (
                    <p key={i}>
                      <strong>{text(t.invoice)}</strong> ·{" "}
                      {money(t.recorded_tax_under_review)} ·{" "}
                      {plain(t.recommended_action)} — {text(t.reason)}
                    </p>
                  ))}
              </article>
            )}
          </section>
          <section className="card">
            <h3>Explore a payment</h3>
            <p>See the cash effect before making a decision.</p>
            <form
              onSubmit={(event) => {
                const data = formValues(event);
                const invoice = invoices.find((p) => p.id === data.invoice);
                if (!invoice) return;
                void action.run(
                  () =>
                    c.api.command<Result>(
                      path(c, "passports/" + invoice.id + "/scenario"),
                      {
                        expected_version: invoice.version,
                        cash_available: data.cash,
                        proposed_payment: data.payment,
                      },
                    ),
                  setAnswer,
                  "Scenario ready.",
                );
              }}
            >
              <label>
                Invoice
                <select name="invoice" required>
                  <option value="">Choose invoice</option>
                  {invoices
                    .filter((p) => p.confirmed)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {text(p.fields.invoice_number)}
                      </option>
                    ))}
                </select>
              </label>
              <Field name="cash" required>
                Available cash
              </Field>
              <Field name="payment" required>
                Proposed payment
              </Field>
              <button disabled={action.busy}>Compare</button>
            </form>
            {answer?.cash_after_payment != null && (
              <Notice>
                Cash after this scenario: {money(answer.cash_after_payment)}.
                Invoice balance: {money(answer.invoice_remaining)}. No payment
                was made.
              </Notice>
            )}
          </section>
          <section className="card">
            <h3>Prepare an evidence note</h3>
            <p>
              Start a response from the saved invoice facts. Review it against
              the actual notice before submitting.
            </p>
            <form
              onSubmit={(event) => {
                const data = formValues(event);
                void action.run(
                  () =>
                    c.api.command<Result>(
                      path(
                        c,
                        "passports/" +
                          display(data.invoice) +
                          "/notice-assistance",
                      ),
                      {
                        case_id: data.case || null,
                        notice_text: data.notice,
                        use_ai: data.ai === "on",
                      },
                    ),
                  setAnswer,
                  "Draft ready.",
                );
              }}
            >
              <label>
                Invoice
                <select name="invoice" required>
                  <option value="">Choose invoice</option>
                  {invoices
                    .filter((p) => p.confirmed)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {text(p.fields.invoice_number)}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Recorded notice case, if available
                <select name="case">
                  <option value="">Choose a case</option>
                  {(cases.data?.cases || [])
                    .filter((v) => v.kind === "NOTICE_REVIEW")
                    .map((v) => (
                      <option key={v.id} value={v.id}>
                        {display(v.facts.notice_reference) || v.id.slice(0, 8)}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Notice concerns
                <textarea
                  name="notice"
                  minLength={20}
                  maxLength={8000}
                  required
                />
              </label>
              <label className="check">
                <input name="ai" type="checkbox" />
                Allow Google AI to draft from this notice and saved evidence.
              </label>
              <button disabled={action.busy}>Prepare note</button>
            </form>
            {answer?.draft != null && (
              <>
                <blockquote>{text(answer.draft)}</blockquote>
                {Array.isArray(answer.missing_evidence) && (
                  <Notice>
                    Still needed: {answer.missing_evidence.map(text).join("; ")}
                    .
                  </Notice>
                )}
              </>
            )}
          </section>
        </>
      )}
      {tab === "Watch & outcomes" && (
        <>
          <section className="card">
            <h3>Watch for changes</h3>
            <label>
              Invoice
              <select value={selected} onChange={(e) => select(e.target.value)}>
                <option value="">Choose invoice</option>
                {invoices
                  .filter((p) => p.confirmed)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {text(p.fields.invoice_number)}
                    </option>
                  ))}
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={watch}
                disabled={!current?.confirmed || !canWrite}
                onChange={(e) => setWatch(e.target.checked)}
              />
              Recheck this invoice while this desk is open.
            </label>
            <p>
              Changed evidence updates the payment recommendation. Existing
              approvals then need review.
            </p>
            <div className="button-row">
              <button
                disabled={!current?.confirmed || !canWrite || action.busy}
                onClick={() =>
                  current &&
                  submit("watch", {
                    expected_version: current.version,
                    enabled: true,
                  })
                }
              >
                Monitor on this PC
              </button>
              <button
                disabled={!current?.confirmed || !canWrite || action.busy}
                onClick={() =>
                  current &&
                  submit("watch", {
                    expected_version: current.version,
                    enabled: false,
                  })
                }
              >
                Stop PC monitoring
              </button>
            </div>
            <p>
              PC monitoring checks saved evidence while the backend is running.
              It sends correction requests when the supplier has opted in and
              WhatsApp sending is enabled.
            </p>
            {current && (
              <p>
                Current decision: {plain(current.gate.recommendation)}.{" "}
                {current.approval
                  ? "Saved approval: " + plain(current.approval.state)
                  : "No saved approval."}
              </p>
            )}
          </section>
          <details className="card">
            <summary>Sample GST records</summary>
            <Notice>
              Simulation: these controls create sample GST records. They do not
              connect to the government.
            </Notice>
            <p>
              Choose a confirmed invoice above, then show a missing record
              followed by its correction.
            </p>
            <div className="button-row">
              <button
                disabled={!current?.confirmed || !canWrite || action.busy}
                onClick={() =>
                  current &&
                  submit("simulate-fetch", {
                    expected_version: current.version,
                    status: "MISSING",
                  })
                }
              >
                Fetch sample: invoice missing
              </button>
              <button
                disabled={!current?.confirmed || !canWrite || action.busy}
                onClick={() =>
                  current &&
                  submit("simulate-fetch", {
                    expected_version: current.version,
                    status: "MATCHED",
                  })
                }
              >
                Fetch sample: invoice corrected
              </button>
            </div>
          </details>
          <section className="card">
            <h3>Resolution progress</h3>
            <p>
              Supplier requests prepared:{" "}
              {text(records.data?.metrics.requests_prepared)}. Approvals to
              review: {text(records.data?.metrics.approvals_need_review)}.
            </p>
            <div className="desk-stats">
              <div>
                Reviewed resolutions
                <strong>
                  {text(records.data?.metrics.reviewed_resolutions)}
                </strong>
              </div>
              <div>
                Still being tracked
                <strong>
                  {text(records.data?.metrics.unresolved_invoices)}
                </strong>
              </div>
              <div>
                Tax needs attention
                <strong>
                  {money(records.data?.metrics.recorded_itc_under_review)}
                </strong>
              </div>
            </div>
            <p>
              Resolution counts reflect reviewed cases, rather than cash
              recovered or tax credit legally approved.
            </p>
          </section>
        </>
      )}
    </section>
  );
}
