import { useEffect, useRef, useState } from "react";
import type { Context } from "./shared";
import type { Schemas } from "./contracts";
import {
  path,
  useResource,
  useCommand,
  LoadState,
  Notice,
  money,
  Field,
  date,
  label,
} from "./shared";
import { productPath, selection } from "./product";
import InvoiceItems, { itemsFrom } from "./InvoiceItems";
import InvoiceReview from "./InvoiceReview";
import type { InvoiceNavigate } from "./InvoiceJourney";
type Passport = Schemas["PassportData"];
type Values = Record<string, unknown>;
const str = (v: unknown) => (v == null ? "" : String(v));
const status = (v: unknown) =>
  ({
    MATCHED: "Matches",
    MISSING: "Missing",
    MISMATCH: "Differs",
    REVIEW: "Review needed",
    DUPLICATE: "Possible duplicate",
    PAY: "Full payment",
    PARTIAL_CONTROLLED_PAYMENT: "Controlled part payment",
    HOLD: "Hold payment",
    ESCALATE: "Ask an approver",
    STALE: "Review changed evidence",
  })[str(v)] || label(str(v));
const fields: Record<string, string> = {
  supplier_name: "Supplier",
  supplier_gstin: "Supplier GST number",
  invoice_number: "Invoice number",
  invoice_date: "Invoice date",
  taxable_value: "Goods value",
  gross_total: "Invoice total",
  cgst: "CGST",
  sgst: "SGST",
  igst: "IGST",
  cess: "Cess",
  other_charges: "Other charges",
  round_off: "Rounding",
  irn: "E-invoice reference",
  supplier_bank_account: "Printed bank account",
  quantity: "Quantity",
};
const required = [
  "supplier_gstin",
  "invoice_number",
  "invoice_date",
  "taxable_value",
  "gross_total",
];
function confirmedFields(raw: Values) {
  const result = { ...raw };
  for (const k of [
    "igst",
    "cgst",
    "sgst",
    "cess",
    "quantity",
    "supplier_bank_account",
  ])
    if (result[k] === "" || result[k] == null) result[k] = null;
  for (const k of ["supplier_name", "irn"]) result[k] = str(result[k]);
  for (const k of ["other_charges", "round_off"])
    result[k] = str(result[k] ?? "0.00");
  result.items = Array.isArray(raw.items)
    ? raw.items.map((item) =>
        Object.fromEntries(
          ["description", "sku", "unit", "quantity", "taxable_value"].map(
            (key) => [key, str(item[key])],
          ),
        ),
      )
    : [];
  const allowed = [
    ...Object.keys(fields),
    "items",
    "irn_required",
    "payment_dispute",
  ];
  return Object.fromEntries(
    Object.entries(result).filter(([k]) => allowed.includes(k)),
  );
}
function PrintedFacts({ values }: { values: Values }) {
  return (
    <dl className="facts">
      {Object.entries(fields)
        .filter(([k]) => values[k] != null && values[k] !== "")
        .map(([k, t]) => (
          <div key={k}>
            <dt>{t}</dt>
            <dd>
              {[
                "taxable_value",
                "gross_total",
                "cgst",
                "sgst",
                "igst",
                "cess",
                "other_charges",
              ].includes(k)
                ? money(str(values[k]))
                : str(values[k])}
            </dd>
          </div>
        ))}
    </dl>
  );
}
export default function FocusedInvoiceDesk({
  c,
  initialInvoiceId,
}: {
  c: Context;
  initialInvoiceId?: string;
  navigate: InvoiceNavigate;
}) {
  const [id, setId] = useState(initialInvoiceId || "");
  const [uploadOpen, setUploadOpen] = useState(false);
  const records = useResource<Schemas["PassportListData"]>(
    c.api,
    path(c, `passports?${selection(c)}`),
    15000,
  );
  const role = c.staffRole || "CA";
  const canIntake = ["CA", "ACCOUNTS"].includes(role);
  const canProof = ["CA", "WAREHOUSE"].includes(role);
  const canPay = ["CA", "CFO"].includes(role);
  const canFollow = ["CA", "FOLLOWUP"].includes(role);
  const invoice = records.data?.passports.find((p) => p.id === id);
  const action = useCommand();
  const update = (p: Passport) => {
    setId(p.id);
    setUploadOpen(false);
    records.reload();
  };
  const command = (suffix: string, payload: unknown, done?: () => void) => {
    if (invoice)
      void action.run(
        () =>
          c.api.command<Passport>(
            path(c, `passports/${invoice.id}/${suffix}`),
            payload,
          ),
        (saved) => {
          update(saved);
          done?.();
        },
        "Saved. Checks updated.",
      );
  };
  const current = invoice;
  const commercialReady =
    current?.findings.po === "MATCHED" &&
    current?.findings.receipt === "MATCHED";
  const hasStatement = !!current?.findings.gst_source;
  const watchEvent = current?.history
    .slice()
    .reverse()
    .find((h) => h.action === "WATCH_MODE_SET")?.facts as Values | undefined;
  const watching = watchEvent?.enabled === true;
  return (
    <section className="focused-invoices">
      <div className="controls">
        <h2>
          {role === "CFO"
            ? "Review payment decisions"
            : role === "WAREHOUSE"
              ? "Order and delivery records"
              : role === "FOLLOWUP"
                ? "Supplier corrections"
                : "Upload. Check. Move forward."}
        </h2>
        {canIntake && (
          <button onClick={() => setUploadOpen(!uploadOpen)}>
            Upload an invoice
          </button>
        )}
      </div>
      {action.feedback}
      <LoadState {...records} empty={false} />
      {canIntake && (uploadOpen || records.data?.passports.length === 0) && (
        <form
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            f.set("registration_id", c.registration.id);
            f.set("period", c.period);
            f.set("consent", f.get("consent") ? "true" : "false");
            const file = f.get("file") as File;
            void action.run(
              () =>
                c.api.upload<Passport>(
                  path(c, "passports/documents"),
                  f,
                  `${file.name}:${file.size}:${file.lastModified}`,
                ),
              update,
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
            <input name="consent" type="checkbox" required />
            Allow Google AI to read this invoice.
          </label>
          <button disabled={action.busy}>Read invoice</button>
          <p className="muted">
            PDF, PNG or JPEG, up to 4 MB. You confirm the result once.
          </p>
        </form>
      )}
      <div className="desk-layout">
        <aside className="invoice-list" aria-label="Saved invoices">
          {records.data?.passports.map((p) => (
            <button
              key={p.id}
              aria-current={p.id === id ? "true" : undefined}
              onClick={() => setId(p.id)}
            >
              <strong>{str(p.fields.invoice_number) || p.filename}</strong>
              <span>{str(p.fields.supplier_name) || "Reading supplier"}</span>
              <small>
                {p.confirmed
                  ? status(p.findings.summary)
                  : "Confirm extracted details"}{" "}
                · {money(str(p.fields.gross_total))}
              </small>
            </button>
          ))}
        </aside>
        {current ? (
          <article className="invoice-detail">
            <header>
              <h3>{str(current.fields.invoice_number) || current.filename}</h3>
              <p>{str(current.fields.supplier_name)}</p>
              {canIntake && (
                <details>
                  <summary>Remove a file or invoice</summary>
                  <p>
                    Removing the original deletes its saved file. Removing the
                    invoice also takes it out of active work. Recorded decisions
                    and payment history stay available for accountability.
                  </p>
                  {current.original_available && (
                    <button
                      disabled={action.busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Delete this saved original file? Recorded facts and history remain.",
                          )
                        )
                          command("remove", {
                            expected_version: current.version,
                            target: "ORIGINAL_FILE",
                          });
                      }}
                    >
                      Delete original file
                    </button>
                  )}
                  <button
                    disabled={action.busy}
                    onClick={() => {
                      if (
                        window.confirm(
                          "Remove this invoice from active work and delete its original file? Financial history remains.",
                        )
                      )
                        command(
                          "remove",
                          {
                            expected_version: current.version,
                            target: "INVOICE",
                          },
                          () => setId(""),
                        );
                    }}
                  >
                    Remove invoice
                  </button>
                </details>
              )}
            </header>
            {!current.confirmed ? (
              <InvoiceConfirmation
                key={current.id + current.version}
                invoice={current}
                enabled={canIntake}
                busy={action.busy}
                confirm={(f) =>
                  command("confirm", {
                    expected_version: current.version,
                    fields: f,
                  })
                }
                retry={() => command("retry-extraction", {})}
              />
            ) : (
              <>
                <dl className="role-figures">
                  <div>
                    <dt>Invoice total</dt>
                    <dd>{money(str(current.fields.gross_total))}</dd>
                  </div>
                  <div>
                    <dt>Recorded tax needing review</dt>
                    <dd>{money(current.gate.recorded_tax_under_review)}</dd>
                  </div>
                </dl>
                <div className="record-ribbon" aria-label="Four-way check">
                  {[
                    ["Invoice", "CONFIRMED"],
                    ["Order", current.findings.po],
                    ["Delivery", current.findings.receipt],
                    ["GST statement", current.findings.gst],
                  ].map(([t, s]) => (
                    <div key={str(t)}>
                      <strong>{str(t)}</strong>
                      <span>{status(s)}</span>
                    </div>
                  ))}
                </div>
                <NextEvidence
                  c={c}
                  invoice={current}
                  canProof={canProof}
                  busy={action.busy}
                  command={command}
                />
                {role === "CA" && commercialReady && (
                  <StatementChoice
                    c={c}
                    invoice={current}
                    reload={records.reload}
                  />
                )}
                {canPay && commercialReady && hasStatement && (
                  <PaymentStep
                    key={current.id + ":" + current.source_signature}
                    invoice={current}
                    busy={action.busy}
                    command={command}
                  />
                )}
                {canFollow &&
                  commercialReady &&
                  hasStatement &&
                  current.findings.summary !== "MATCHED" && (
                    <SupplierStep
                      key={current.id}
                      c={c}
                      configured={!!records.data?.provider.whatsapp_configured}
                      invoice={current}
                      busy={action.busy}
                      command={command}
                    />
                  )}
                {["CA", "CFO"].includes(role) && (
                  <details className="panel">
                    <summary>Supplier history and warning signs</summary>
                    {records.data?.vendors
                      .filter((v) => v.gstin === current.fields.supplier_gstin)
                      .map((v, i) => (
                        <div key={i}>
                          <strong>
                            {str(v.name) || "Supplier"}: {str(v.score)}/100
                          </strong>
                          <p>
                            {label(str(v.confidence))}. {str(v.basis)}
                          </p>
                        </div>
                      ))}
                    {records.data?.anomalies
                      .filter((a) => a.invoice_id === current.id)
                      .map((a, i) => (
                        <p key={i}>{str(a.meaning)}</p>
                      ))}
                    <p className="caption">
                      Saved-history indicators request review. They do not prove
                      fraud or verify GST filing.
                    </p>
                  </details>
                )}
                {role === "CA" && commercialReady && hasStatement && (
                  <details className="panel">
                    <summary>GST review and ongoing checks</summary>
                    <p>
                      {status(current.findings.ims_recommendation)}.{" "}
                      {str(current.findings.ims_reason)}
                    </p>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const f = new FormData(e.currentTarget);
                        command("ims-review", {
                          expected_version: current.version,
                          source_signature: current.source_signature,
                          action: f.get("action"),
                          reason: f.get("reason"),
                          confirm_rejection: !!f.get("confirm_rejection"),
                        });
                      }}
                    >
                      <label>
                        Reviewed GST action
                        <select
                          name="action"
                          defaultValue={
                            str(current.findings.ims_recommendation) ||
                            "HUMAN_REVIEW"
                          }
                        >
                          <option value="ACCEPT">Accept</option>
                          <option value="PENDING">Keep pending</option>
                          <option value="HUMAN_REVIEW">Needs a reviewer</option>
                          <option value="REJECT">Reject</option>
                        </select>
                      </label>
                      <Field
                        name="reason"
                        required
                        pattern=".{10,1000}"
                        value={str(current.findings.ims_reason)}
                      >
                        Reason for this review
                      </Field>
                      <label className="check">
                        <input name="confirm_rejection" type="checkbox" />I
                        reviewed the reason if rejecting.
                      </label>
                      <button disabled={action.busy}>Save GST review</button>
                    </form>
                    <p className="caption">
                      Internal guidance only. Nothing is submitted to the GST
                      portal.
                    </p>
                    <button
                      className="secondary"
                      disabled={action.busy}
                      onClick={() =>
                        command("watch", {
                          expected_version: current.version,
                          enabled: !watching,
                        })
                      }
                    >
                      {watching
                        ? "Pause ongoing checks"
                        : "Check when saved evidence changes"}
                    </button>
                    <p>
                      Ongoing checks use saved files and recorded updates. They
                      do not fetch live government data.
                    </p>
                  </details>
                )}
                {role === "CA" && <InvoiceReview c={c} invoice={current} />}
                <InvoiceProgress key={current.id} c={c} invoice={current} />
                <details className="panel">
                  <summary>Invoice facts and action history</summary>
                  <PrintedFacts values={current.fields} />
                  <ItemFacts value={current.fields.items} />
                  {current.history
                    .slice()
                    .reverse()
                    .slice(0, 30)
                    .map((h, i) => (
                      <p key={i}>
                        <strong>{label(str(h.action))}</strong> · {date(h.at)}
                      </p>
                    ))}
                  <button
                    className="secondary"
                    onClick={() =>
                      void action.run(() =>
                        c.api.download(
                          path(c, `passports/${current.id}/dossier`),
                          `gstshield-dossier-${current.id}.pdf`,
                        ),
                      )
                    }
                  >
                    Download invoice history
                  </button>
                </details>
                {role === "CA" && (
                  <details className="panel">
                    <summary>Sample GST records</summary>
                    <p>
                      Sample GST evidence only. This does not fetch from the
                      government.
                    </p>
                    <button
                      disabled={action.busy}
                      onClick={() =>
                        command("simulate-fetch", {
                          expected_version: current.version,
                          status: "MISSING",
                        })
                      }
                    >
                      Use sample: invoice missing
                    </button>
                    <button
                      disabled={action.busy}
                      onClick={() =>
                        command("simulate-fetch", {
                          expected_version: current.version,
                          status: "MATCHED",
                        })
                      }
                    >
                      Use sample: invoice corrected
                    </button>
                  </details>
                )}
              </>
            )}
          </article>
        ) : (
          <p className="notice">
            Select an invoice. Its next step appears here.
          </p>
        )}
      </div>
    </section>
  );
}
function ItemFacts({ value }: { value: unknown }) {
  const items = Array.isArray(value) ? value : [];
  return items.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Quantity</th>
            <th>Goods value</th>
          </tr>
        </thead>
        <tbody>
          {items.map((x, i) => (
            <tr key={i}>
              <td>
                {x.description} {x.sku && `(${x.sku})`}
              </td>
              <td>
                {x.quantity} {x.unit}
              </td>
              <td>{money(str(x.taxable_value))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <p className="muted">
      No printed item details were read. Item-level checks need the item record.
    </p>
  );
}
function InvoiceConfirmation({
  invoice,
  enabled,
  busy,
  confirm,
  retry,
}: {
  invoice: Passport;
  enabled: boolean;
  busy: boolean;
  confirm: (f: Values) => void;
  retry: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [values] = useState<Values>({ ...invoice.fields });
  const missing = required.filter((k) => !values[k]);
  const itemsNeedReview =
    Array.isArray(values.items) &&
    values.items.some(
      (item) =>
        !str(item.description).trim() ||
        !/^[0-9]{1,9}(\.[0-9]{1,4})?$/.test(str(item.quantity)) ||
        Number(item.quantity) <= 0 ||
        !/^[0-9]{1,14}(\.[0-9]{1,2})?$/.test(str(item.taxable_value)),
    );
  const failed = ["FAILED", "PENDING"].includes(str(invoice.extraction.status));
  if (!enabled)
    return (
      <section className="panel">
        <h3>Accounting confirmation pending</h3>
        <PrintedFacts values={values} />
        <ItemFacts value={values.items} />
        <p>
          Your accounting teammate confirms these details before the payment
          review. No retyping is needed in your role.
        </p>
      </section>
    );
  return (
    <section className="panel">
      <h3>Confirm what was read</h3>
      {failed && (
        <Notice error>
          {str(invoice.extraction.message) || "Invoice reading is pending."}
          <button disabled={!enabled || busy} onClick={retry}>
            Try reading again
          </button>
        </Notice>
      )}
      <p>
        Check the populated details against your invoice. Edit only a mistake or
        a missing required fact.
      </p>
      <PrintedFacts values={values} />
      <ItemFacts value={values.items} />
      {Array.isArray(invoice.extraction.uncertainties) &&
        invoice.extraction.uncertainties.length > 0 && (
          <p className="notice">
            Reader notes: {invoice.extraction.uncertainties.join("; ")}
          </p>
        )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const f = Object.fromEntries(new FormData(e.currentTarget).entries());
          const next = {
            ...values,
            ...Object.fromEntries(
              Object.entries(f).filter(([k]) => Object.hasOwn(fields, k)),
            ),
          };
          if (editing || itemsNeedReview) next.items = itemsFrom(f);
          confirm(confirmedFields(next));
        }}
      >
        <div className="form-grid">
          {(editing ? Object.keys(fields) : missing).map((k) => (
            <Field
              key={k}
              name={k}
              type={k === "invoice_date" ? "date" : "text"}
              value={str(values[k])}
              required={required.includes(k)}
            >
              {fields[k]}
            </Field>
          ))}
        </div>
        {itemsNeedReview && (
          <Notice>
            Some printed item details need a correction. Complete only those
            missing facts below.
          </Notice>
        )}
        {(editing || itemsNeedReview) && <InvoiceItems value={values.items} />}
        <div className="controls">
          <button disabled={!enabled || busy || failed}>Confirm details</button>
          <button
            type="button"
            className="secondary"
            onClick={() => setEditing(!editing)}
          >
            {editing ? "Keep extracted values" : "Correct a detail"}
          </button>
        </div>
      </form>
    </section>
  );
}

type Command = (suffix: string, payload: unknown, done?: () => void) => void;
function NextEvidence({
  c,
  invoice,
  canProof,
  busy,
  command,
}: {
  c: Context;
  invoice: Passport;
  canProof: boolean;
  busy: boolean;
  command: Command;
}) {
  const po = invoice.findings.po,
    receipt = invoice.findings.receipt;
  const kind =
    po === "MISSING" ? "PO" : receipt === "MISSING" ? "RECEIPT" : null;
  const [fix, setFix] = useState<string | null>(null);
  if (kind || fix)
    return (
      <section className="panel next-action">
        <span className="eyebrow">Next evidence</span>
        <h3>
          {(kind || fix) === "PO"
            ? "Add the purchase order"
            : "Add the delivery record"}
        </h3>
        <p>
          {(kind || fix) === "PO"
            ? "Your purchasing team's order proves what you agreed to buy."
            : "The receiving team's record proves what actually arrived."}
        </p>
        {canProof ? (
          <ProofReader
            key={invoice.id + ":" + (kind || fix)}
            c={c}
            invoice={invoice}
            kind={(kind || fix) as "PO" | "RECEIPT"}
            command={(s, p) => {
              command(s, p, () => setFix(null));
            }}
          />
        ) : (
          <p>
            Your accounting or receiving team adds this evidence. You can follow
            progress without filling another team's form.
          </p>
        )}
      </section>
    );
  return (
    <section className="panel">
      <h3>
        {po === "MATCHED" && receipt === "MATCHED"
          ? "Order and delivery checks complete"
          : "Order or delivery needs review"}
      </h3>
      <p>
        {po === "MATCHED" && receipt === "MATCHED"
          ? "Saved item details are compared automatically. No repeated entry is needed."
          : "The supplied records differ or have incomplete item details. Correct the source record rather than copying the invoice."}
      </p>
      {canProof && (
        <details>
          <summary>Correct saved order or delivery evidence</summary>
          <div className="controls">
            <button
              className="secondary"
              disabled={busy}
              onClick={() => setFix("PO")}
            >
              Replace order evidence
            </button>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => setFix("RECEIPT")}
            >
              Replace delivery evidence
            </button>
          </div>
        </details>
      )}
    </section>
  );
}
type Proof = {
  proposal_id: string;
  sha256: string;
  fields: Values;
  state: string;
};
function ProofReader({
  c,
  invoice,
  kind,
  command,
}: {
  c: Context;
  invoice: Passport;
  kind: "PO" | "RECEIPT";
  command: Command;
}) {
  const [proposal, setProposal] = useState<Proof | null>(null);
  const [manual, setManual] = useState(false);
  const [editing, setEditing] = useState(false);
  const action = useCommand();
  const raw = proposal?.fields || {};
  const needed = [
    "reference",
    "observed_on",
    ...(kind === "PO" ? ["taxable_value"] : []),
  ];
  const title: Record<string, string> = {
    reference: "Record reference",
    observed_on: "Record date",
    taxable_value: "Goods value",
    quantity: "Total quantity",
  };
  return (
    <>
      {!proposal && !manual && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            data.set("kind", kind);
            data.set("consent", data.get("consent") ? "true" : "false");
            const file = data.get("file") as File;
            void action.run(
              () =>
                c.api.upload<Proof>(
                  path(c, `passports/${invoice.id}/evidence-documents`),
                  data,
                  `${kind}:${file.name}:${file.size}:${file.lastModified}`,
                ),
              setProposal,
            );
          }}
        >
          <label>
            {kind === "PO" ? "Order PDF or photo" : "Delivery PDF or photo"}
            <input
              type="file"
              name="file"
              accept=".pdf,.png,.jpg,.jpeg"
              required
            />
          </label>
          <label className="check">
            <input type="checkbox" name="consent" required />
            Allow Google AI to read this supporting document.
          </label>
          <button disabled={action.busy}>Read supporting document</button>
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setManual(true);
              setEditing(true);
            }}
          >
            I only have a paper record
          </button>
        </form>
      )}
      {(proposal || manual) && (
        <form
          key={proposal?.proposal_id || "manual"}
          onSubmit={(e) => {
            e.preventDefault();
            const f = Object.fromEntries(
              new FormData(e.currentTarget).entries(),
            );
            const data = {
              ...raw,
              ...Object.fromEntries(
                Object.entries(f).filter(([k]) => k in title),
              ),
            };
            command("evidence", {
              expected_version: invoice.version,
              kind,
              reference: data.reference,
              taxable_value: data.taxable_value || null,
              quantity: data.quantity || null,
              observed_on: data.observed_on,
              items: editing
                ? itemsFrom(f).map((x) => ({
                    ...x,
                    taxable_value: x.taxable_value || null,
                  }))
                : Array.isArray(raw.items)
                  ? raw.items.map((item) => ({
                      description: str(item.description),
                      sku: str(item.sku),
                      unit: str(item.unit),
                      quantity: str(item.quantity),
                      taxable_value:
                        item.taxable_value == null
                          ? null
                          : str(item.taxable_value),
                    }))
                  : [],
              document_proposal_id: proposal?.proposal_id || null,
              note: proposal
                ? "Reviewed supporting-document extraction"
                : "Reviewed original paper record",
            });
          }}
        >
          {proposal && (
            <>
              <p>
                Read from your document. Confirm once; comparison runs
                automatically.
              </p>
              <dl className="facts">
                {Object.entries(title)
                  .filter(([k]) => raw[k] != null)
                  .map(([k, t]) => (
                    <div key={k}>
                      <dt>{t}</dt>
                      <dd>
                        {k === "taxable_value"
                          ? money(str(raw[k]))
                          : str(raw[k])}
                      </dd>
                    </div>
                  ))}
              </dl>
              <ItemFacts value={raw.items} />
              {Array.isArray(raw.uncertainties) &&
                !!raw.uncertainties.length && (
                  <p className="notice">{raw.uncertainties.join("; ")}</p>
                )}
            </>
          )}
          <div className="form-grid">
            {(editing ? Object.keys(title) : needed.filter((k) => !raw[k])).map(
              (k) => (
                <Field
                  key={k}
                  name={k}
                  type={k === "observed_on" ? "date" : "text"}
                  value={str(raw[k])}
                  required={needed.includes(k)}
                >
                  {title[k]}
                </Field>
              ),
            )}
          </div>
          {editing && <InvoiceItems value={raw.items} priced={kind === "PO"} />}
          <button disabled={action.busy}>
            Confirm {kind === "PO" ? "order" : "delivery"}
          </button>
          {proposal && (
            <button
              className="secondary"
              type="button"
              onClick={() => setEditing(!editing)}
            >
              Correct extracted details
            </button>
          )}
          <p className="caption">
            Only missing required facts need entry. Original supporting files
            are read for this proposal; the saved history keeps their
            fingerprint and reviewed facts.
          </p>
        </form>
      )}
      {action.feedback}
    </>
  );
}
function StatementChoice({
  c,
  invoice,
  reload,
}: {
  c: Context;
  invoice: Passport;
  reload: () => void;
}) {
  const [open, setOpen] = useState(false);
  const action = useCommand();
  const current = invoice.findings.gst_source as
    { id?: string; state?: string; provenance?: string } | undefined;
  const sources = useResource<Schemas["ImportListData"]>(
    c.api,
    open ? path(c, `imports?${selection(c)}&limit=100`) : null,
  );
  return (
    <section className="panel">
      <h3>
        {current?.state === "READY"
          ? "GST comparison runs automatically"
          : "Add the month's GST statement"}
      </h3>
      <p>
        {current?.state === "READY"
          ? `This invoice uses the saved statement. Result: ${status(invoice.findings.gst)}.`
          : "Your accountant downloads GSTR-2B. Upload it here once; your invoices reuse it."}
      </p>
      <div className="controls">
        <button
          type="button"
          className="secondary"
          onClick={() => setOpen(!open)}
        >
          {current
            ? "Change the month's statement"
            : "Choose an uploaded statement"}
        </button>
      </div>
      {(!current || open) && (
        <MonthlyStatementUpload
          c={c}
          reload={() => {
            sources.reload();
            reload();
          }}
        />
      )}
      {open && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            void action.run(
              () =>
                c.api.command(productPath(c, "gst-statement"), {
                  registration_id: c.registration.id,
                  period: c.period,
                  import_id: f.get("statement"),
                }),
              reload,
              "Statement saved for all invoices in this company and month.",
            );
          }}
        >
          <LoadState {...sources} empty={false} />
          <label>
            Confirmed GST statement
            <select name="statement" required defaultValue={current?.id || ""}>
              <option value="">Choose a confirmed statement</option>
              {sources.data?.imports
                .filter((s) => s.kind === "PORTAL_2B" && s.state === "READY")
                .map((s) => (
                  <option value={s.id} key={s.id}>
                    {s.provenance === "SYNTHETIC_DEMO"
                      ? "Sample statement"
                      : "Uploaded statement"}{" "}
                    · {s.id.slice(0, 8)} · {s.accepted_rows} rows
                  </option>
                ))}
            </select>
          </label>
          <button disabled={action.busy}>Use for this month's invoices</button>
          {action.feedback}
        </form>
      )}
      {current?.provenance === "SYNTHETIC_DEMO" && (
        <p className="caption">Sample records, not government data.</p>
      )}
    </section>
  );
}
function PaymentStep({
  invoice,
  busy,
  command,
}: {
  invoice: Passport;
  busy: boolean;
  command: Command;
}) {
  const [paid, setPaid] = useState("unpaid");
  const [timing, setTiming] = useState(false);
  const [decision, setDecision] = useState(
    str(invoice.gate.recommendation) === "REVIEW"
      ? "HOLD"
      : str(invoice.gate.recommendation),
  );
  const ready =
    invoice.findings.po === "MATCHED" &&
    invoice.findings.receipt === "MATCHED" &&
    !!invoice.findings.gst_source;
  const remaining = str(invoice.gate.remaining_amount),
    suggested = str(invoice.gate.suggested_part_payment);
  const amount =
    decision === "PAY"
      ? remaining
      : decision === "PARTIAL_CONTROLLED_PAYMENT"
        ? suggested
        : "0.00";
  if (!ready)
    return (
      <p className="notice">
        Payment review opens after the supporting records are checked. Missing
        evidence does not mean a zero-value invoice.
      </p>
    );
  if (!invoice.gate.payment_facts_confirmed)
    return (
      <section className="panel next-action">
        <h3>Has this invoice already been paid?</h3>
        <p>
          The invoice cannot tell us whether your bank paid it. Confirm this
          once; we calculate the balance.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            command("clocks", {
              expected_version: invoice.version,
              amount_paid: paid === "unpaid" ? "0.00" : f.get("amount_paid"),
              payment_observed_on: `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}-${String(new Date().getDate()).padStart(2, "0")}`,
              msme_covered:
                f.get("msme") === "yes"
                  ? true
                  : f.get("msme") === "no"
                    ? false
                    : null,
              accepted_on: f.get("accepted") || null,
              agreed_days: f.get("days") ? Number(f.get("days")) : null,
              claimed_on: null,
              supplier_3b_due_on: null,
              note:
                paid === "unpaid"
                  ? "Reviewer explicitly confirmed no prior payment"
                  : "Reviewer confirmed recorded payment amount",
            });
          }}
        >
          <label>
            Payment history
            <select value={paid} onChange={(e) => setPaid(e.target.value)}>
              <option value="unpaid">Not paid yet</option>
              <option value="paid">Some or all already paid</option>
            </select>
          </label>
          {paid === "paid" && (
            <Field name="amount_paid" required>
              Amount already paid (₹)
            </Field>
          )}
          <button
            type="button"
            className="text-button"
            onClick={() => setTiming(!timing)}
          >
            Add known supplier payment terms
          </button>
          {timing && (
            <div className="form-grid">
              <label>
                Micro or small supplier coverage
                <select name="msme">
                  <option value="">Not verified</option>
                  <option value="yes">Verified covered</option>
                  <option value="no">Verified not covered</option>
                </select>
              </label>
              <Field name="accepted" type="date">
                Goods accepted on
              </Field>
              <Field name="days" type="number">
                Agreed payment days, 1–45
              </Field>
            </div>
          )}
          <button disabled={busy}>Confirm payment history</button>
        </form>
      </section>
    );
  return (
    <section className="panel">
      <h3>{status(invoice.gate.recommendation)}</h3>
      <p>{str(invoice.gate.reason)}</p>
      <p>
        Unpaid invoice balance: <strong>{money(remaining)}</strong>
      </p>
      {invoice.approval?.state === "STALE" && (
        <Notice>
          Evidence changed. The old decision must be reviewed again.
        </Notice>
      )}
      <form
        key={invoice.source_signature}
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          command("approve", {
            expected_version: invoice.version,
            source_signature: invoice.source_signature,
            decision,
            amount: f.get("amount"),
            reason: f.get("reason"),
          });
        }}
      >
        <label>
          Payment decision
          <select
            value={decision}
            onChange={(e) => setDecision(e.target.value)}
          >
            <option value="PAY">Full payment when all four checks match</option>
            <option value="PARTIAL_CONTROLLED_PAYMENT">
              Controlled part payment
            </option>
            <option value="HOLD">Hold payment</option>
            <option value="ESCALATE">Ask an approver</option>
          </select>
        </label>
        <Field key={decision + amount} name="amount" value={amount} required>
          Proposed amount (₹)
        </Field>
        <Field
          name="reason"
          value={`Reviewed saved evidence: ${str(invoice.gate.reason)}`}
          required
          maxLength={1000}
        >
          Reason for the decision
        </Field>
        <button disabled={busy}>Save reviewed decision</button>
      </form>
      {invoice.approval && (
        <p>
          Saved: {status(invoice.approval.decision)} ·{" "}
          {money(invoice.approval.amount)} · {status(invoice.approval.state)}
        </p>
      )}
      <details>
        <summary>Try the simulated payment gate</summary>
        <p>
          No real bank transfer. Permitted amount:{" "}
          {money(invoice.demo_bank?.allowed_amount)}
        </p>
        <button
          disabled={busy || Number(invoice.demo_bank?.allowed_amount) <= 0}
          onClick={() =>
            command("demo-bank-payment", {
              expected_version: invoice.version,
              source_signature: invoice.source_signature,
              amount: invoice.demo_bank?.allowed_amount,
            })
          }
        >
          Release permitted simulated amount
        </button>
        <button
          disabled={busy || !remaining}
          onClick={() =>
            command("demo-bank-payment", {
              expected_version: invoice.version,
              source_signature: invoice.source_signature,
              amount: remaining,
            })
          }
        >
          Test paying the full balance
        </button>
        <p>
          Simulated amount released: {money(invoice.demo_bank?.released_amount)}
        </p>
      </details>
    </section>
  );
}
function SupplierStep({
  c,
  configured,
  invoice,
  busy,
  command,
}: {
  c: Context;
  configured: boolean;
  invoice: Passport;
  busy: boolean;
  command: Command;
}) {
  const action = useCommand();
  const [invitation, setInvitation] = useState<Record<string, unknown> | null>(
    null,
  );
  if (
    invoice.findings.gst === "MATCHED" &&
    invoice.findings.po === "MATCHED" &&
    invoice.findings.receipt === "MATCHED"
  )
    return (
      <p className="notice">
        The saved records align. No missing-record request is needed.
      </p>
    );
  return (
    <details className="panel">
      <summary>Ask the supplier to correct missing records</summary>
      <p>
        The request uses this invoice's saved findings; you do not retype
        invoice numbers or amounts.
      </p>
      <button
        disabled={busy}
        onClick={() =>
          command("resolution", {
            expected_version: invoice.version,
            action: "DRAFT",
            note: "Supplier request prepared from the saved invoice findings",
          })
        }
      >
        Prepare correction request
      </button>
      {!!invoice.resolution.draft && (
        <blockquote>{str(invoice.resolution.draft)}</blockquote>
      )}
      <p>Response: {status(invoice.resolution.state)}</p>
      {!!invoice.resolution.draft && (
        <button
          className="secondary"
          onClick={() =>
            void navigator.clipboard.writeText(str(invoice.resolution.draft))
          }
        >
          Copy correction request
        </button>
      )}
      {configured ? (
        <details>
          <summary>Send through the connected supplier channel</summary>
          <p>Supplier consent: {status(invoice.supplier_channel?.state)}</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void action.run(
                () =>
                  c.api.command<Record<string, unknown>>(
                    path(c, `passports/${invoice.id}/supplier-invite`),
                    {
                      expected_version: invoice.version,
                      phone: f.get("phone"),
                    },
                  ),
                setInvitation,
              );
            }}
          >
            <Field name="phone" required>
              Supplier phone with country code
            </Field>
            <button disabled={busy || action.busy}>
              Create opt-in invitation
            </button>
          </form>
          {invitation && <p>{str(invitation.instruction)}</p>}
          <button
            disabled={
              busy ||
              invoice.supplier_channel?.state !== "VERIFIED" ||
              !invoice.resolution.draft
            }
            onClick={() =>
              command("supplier-send", { expected_version: invoice.version })
            }
          >
            Send reviewed correction request
          </button>
          {action.feedback}
        </details>
      ) : (
        <p className="caption">
          WhatsApp is not connected. Copy the request to your existing channel.
        </p>
      )}
      <details>
        <summary>Record a response received outside the app</summary>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            command("resolution", {
              expected_version: invoice.version,
              action: f.get("response"),
              note: f.get("note"),
              promised_on: f.get("promised_on") || null,
            });
          }}
        >
          <label>
            Supplier response
            <select name="response">
              <option value="ACKNOWLEDGED">Received the request</option>
              <option value="PROMISED">Promised a correction</option>
              <option value="RESOLVED">Says the record is corrected</option>
              <option value="ESCALATED">Needs escalation</option>
            </select>
          </label>
          <Field name="note" required>
            What the supplier said
          </Field>
          <Field name="promised_on" type="date">
            Promised date, if supplied
          </Field>
          <button disabled={busy}>Save response</button>
        </form>
      </details>
      <p className="caption">
        Prepared requests are not sent automatically without a configured
        channel and supplier consent. A reply is rechecked against corrected
        evidence.
      </p>
    </details>
  );
}

type Progress = {
  id: string;
  passport_id: string | null;
  fingerprint: string;
  state: string;
  nodes: {
    id: string;
    kind: string;
    title: string;
    state: string;
    version: number;
    why: string;
    active: boolean;
    exit_ready: boolean;
    can_update: boolean;
  }[];
};
function InvoiceProgress({ c, invoice }: { c: Context; invoice: Passport }) {
  const work = useResource<{ workflows: Progress[] }>(
    c.api,
    productPath(c, `workflows?${selection(c)}`),
    10000,
  );
  const action = useCommand();
  const progress = work.data?.workflows.find(
    (w) => w.passport_id === invoice.id,
  );
  const next = progress?.nodes.find((n) => n.state !== "DONE");
  const started = useRef(false);
  useEffect(() => {
    if (
      work.data &&
      !progress &&
      !started.current &&
      ["CA", "CFO"].includes(c.staffRole || "")
    ) {
      started.current = true;
      void action.run(
        () =>
          c.api.command(productPath(c, "workflows"), {
            passport_id: invoice.id,
          }),
        work.reload,
        "Invoice review prepared from saved evidence.",
      );
    }
  }, [work.data, progress, c.staffRole, invoice.id]);
  if (
    progress &&
    progress.state !== "PROCESS_COMPLETED" &&
    !["RISK", "TAX", "COMPLETE"].includes(next?.kind || "")
  )
    return null;
  return (
    <section className="panel next-action">
      <h3>
        {progress?.state === "PROCESS_COMPLETED"
          ? "Invoice review completed"
          : "Your next step"}
      </h3>
      <LoadState {...work} empty={false} />
      {next ? (
        <>
          <strong>{next.title}</strong>
          <p>{next.why}</p>
          {next.can_update &&
            next.exit_ready &&
            ["RISK", "COMPLETE"].includes(next.kind) && (
              <button
                disabled={action.busy}
                onClick={() =>
                  void action.run(
                    () =>
                      c.api.command(
                        productPath(c, `nodes/${next.id}/transition`),
                        {
                          expected_version: next.version,
                          fingerprint: progress?.fingerprint,
                          state: "DONE",
                          note:
                            next.kind === "RISK"
                              ? "Reviewed saved findings and missing facts before the payment decision."
                              : "Completed the internal invoice review using the current evidence.",
                        },
                      ),
                    work.reload,
                  )
                }
              >
                {next.kind === "RISK"
                  ? "I reviewed the findings and dates"
                  : "Complete the reviewed process"}
              </button>
            )}
          <p className="caption">
            {progress?.nodes.filter((n) => n.state === "DONE").length} of{" "}
            {progress?.nodes.length} steps complete. Saved evidence updates
            completed checks automatically.
          </p>
          <a
            href={
              ["CA", "CFO"].includes(c.staffRole || "")
                ? "#Shared%20process"
                : "#Team%20desk"
            }
          >
            See team progress
          </a>
        </>
      ) : progress ? (
        <p>All required internal review steps are complete.</p>
      ) : (
        <p>The shared review starts automatically after confirmation.</p>
      )}
      {action.feedback}
    </section>
  );
}

function MonthlyStatementUpload({
  c,
  reload,
}: {
  c: Context;
  reload: () => void;
}) {
  const [sourceId, setSourceId] = useState("");
  const action = useCommand();
  const detail = useResource<Schemas["ImportData"]>(
    c.api,
    sourceId ? path(c, `imports/${sourceId}`) : null,
    true,
  );
  const preview = useResource<Schemas["PreviewData"]>(
    c.api,
    detail.data?.state === "AWAITING_CONFIRMATION"
      ? path(c, `imports/${sourceId}/rows?limit=5`)
      : null,
  );
  const source = detail.data;
  return (
    <div className="statement-upload">
      {!sourceId ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const file = f.get("file") as File;
            const extension = file.name.toLowerCase().split(".").pop();
            const adapter =
              extension === "json"
                ? "gst-2b-json-v1"
                : extension === "xlsx"
                  ? "xlsx-v1"
                  : "csv-v1";
            const data = new FormData();
            data.set("file", file);
            data.set("registration_id", c.registration.id);
            data.set("period", c.period);
            data.set("kind", "PORTAL_2B");
            data.set("adapter_version", adapter);
            void action.run(
              () =>
                c.api.upload<Schemas["ImportData"]>(
                  path(c, "imports"),
                  data,
                  `gst:${file.name}:${file.size}:${file.lastModified}`,
                ),
              (s) => setSourceId(s.id),
            );
          }}
        >
          <label>
            GST statement file
            <input type="file" name="file" accept=".json,.csv,.xlsx" required />
          </label>
          <p className="caption">
            GSTR-2B JSON downloaded by your accountant, or a supported CSV/XLSX
            export. Company, month and file format are filled automatically.
          </p>
          <button disabled={action.busy}>Read this month's statement</button>
        </form>
      ) : (
        <>
          <LoadState {...detail} empty={false} />
          {source && (
            <>
              <p>
                {source.accepted_rows} readable records · {source.rejected_rows}{" "}
                need attention.
              </p>
              {["RECEIVED", "PARSING"].includes(source.state) && (
                <p>Reading the statement. You do not need to enter its rows.</p>
              )}
              {source.errors.length > 0 && (
                <p className="notice">
                  {source.errors
                    .map((e) => `${e.field}: ${e.reason}`)
                    .join("; ")}
                </p>
              )}
              {source.state === "AWAITING_CONFIRMATION" && (
                <>
                  <LoadState {...preview} empty={false} />
                  <ul>
                    {preview.data?.rows.map((row) => (
                      <li key={row.row_number}>
                        {str(row.canonical?.invoice_number) ||
                          `Row ${row.row_number}`}{" "}
                        · {money(row.canonical?.total_tax)}
                      </li>
                    ))}
                  </ul>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      const f = new FormData(e.currentTarget);
                      void action.run(
                        async () => {
                          await c.api.command(
                            path(c, `imports/${sourceId}/confirm`),
                            {
                              expected_version: source.version,
                              allow_rejected_rows: f.get("partial") === "on",
                              confirmed_supersession:
                                f.get("supersede") === "on",
                            },
                          );
                          await c.api.command(productPath(c, "gst-statement"), {
                            registration_id: c.registration.id,
                            period: c.period,
                            import_id: sourceId,
                          });
                        },
                        () => {
                          setSourceId("");
                          reload();
                        },
                        "Statement confirmed. Invoice comparisons update automatically.",
                      );
                    }}
                  >
                    {source.rejected_rows > 0 && (
                      <label className="check">
                        <input type="checkbox" name="partial" required />I
                        checked the rejected records and accept excluding them.
                      </label>
                    )}
                    {source.supersedes_import_id && (
                      <label className="check">
                        <input type="checkbox" name="supersede" required />
                        Use this corrected statement and retain the earlier
                        history.
                      </label>
                    )}
                    <button
                      disabled={action.busy || source.accepted_rows === 0}
                    >
                      Confirm and compare invoices
                    </button>
                  </form>
                </>
              )}
              {source.state === "READY" && (
                <button
                  disabled={action.busy}
                  onClick={() =>
                    void action.run(
                      () =>
                        c.api.command(productPath(c, "gst-statement"), {
                          registration_id: c.registration.id,
                          period: c.period,
                          import_id: sourceId,
                        }),
                      () => {
                        setSourceId("");
                        reload();
                      },
                    )
                  }
                >
                  Use confirmed statement
                </button>
              )}
              {source.accepted_rows === 0 &&
                !["RECEIVED", "PARSING"].includes(source.state) && (
                  <a href="#Sources">Review this export's column mapping</a>
                )}
              <button
                className="text-button"
                disabled={action.busy}
                onClick={() => setSourceId("")}
              >
                Choose another file
              </button>
            </>
          )}
        </>
      )}
      {action.feedback}
    </div>
  );
}
