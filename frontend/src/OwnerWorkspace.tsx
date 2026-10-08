import { useState } from "react";
import type { Context } from "./shared";
import {
  useResource,
  useCommand,
  LoadState,
  money,
  Field,
  Notice,
} from "./shared";
import { productPath, selection } from "./product";
import type { Business, Employee } from "./product";
import Today from "./Today";
import InvoiceReview from "./InvoiceReview";
import type { Schemas } from "./contracts";
import { path } from "./shared";

export default function OwnerWorkspace({
  c,
  navigate,
}: {
  c: Context;
  navigate: (section: string, id: string) => void;
}) {
  const [taxOpen, setTaxOpen] = useState(false);
  const invoices = useResource<Schemas["PassportListData"]>(
    c.api,
    taxOpen ? path(c, `passports?${selection(c)}`) : null,
  );
  const [taxInvoice, setTaxInvoice] = useState("");
  const selectedTaxInvoice =
    invoices.data?.passports.find((p) => p.id === taxInvoice) ||
    invoices.data?.passports.find((p) => p.confirmed);
  const business = useResource<Business>(
    c.api,
    productPath(c, `business?${selection(c)}`),
  );
  return (
    <>
      <div className="owner-overview">
        <section className="owner-business">
          <h2>Your business in this month</h2>
          <p>
            Enter figures you know. Leave anything unknown blank. These are your
            reported figures, not a verified financial statement.
          </p>
          <LoadState {...business} empty={!business.data} />
          {business.data && (
            <>
              <div className="metrics">
                <p>
                  Revenue{" "}
                  <strong>
                    {money(business.data.profile.monthly_revenue)}
                  </strong>
                </p>
                <p>
                  Profit{" "}
                  <strong>{money(business.data.profile.monthly_profit)}</strong>
                </p>
                <p>
                  Recorded payroll{" "}
                  <strong>
                    {money(business.data.profile.recorded_payroll_total)}
                  </strong>
                </p>
              </div>
              {c.workspace.role === "OWNER" ? (
                <BusinessForm
                  key={business.data.version}
                  c={c}
                  business={business.data}
                  reload={business.reload}
                />
              ) : (
                <Notice>
                  Employee names and individual salaries are visible only to the
                  owner.
                </Notice>
              )}
            </>
          )}
        </section>
        <aside className="owner-priorities">
          <Today c={c} navigate={navigate} compact limit={3} />
        </aside>
      </div>
      <details
        className="panel tax-drawer"
        onToggle={(e) => setTaxOpen(e.currentTarget.open)}
      >
        <summary>
          Legal ways to save tax for your business{" "}
          <span className="summary-note">Confirm with your CA</span>
        </summary>
        {taxOpen && (
          <>
            <p>
              Start with a saved bill. Each suggestion states its rule, recorded
              amount and information still needed. Confirm with your CA.
            </p>
            <LoadState {...invoices} empty={false} />
            <label>
              Invoice to review
              <select
                value={selectedTaxInvoice?.id || ""}
                onChange={(e) => setTaxInvoice(e.target.value)}
              >
                {invoices.data?.passports
                  .filter((p) => p.confirmed)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {String(p.fields.invoice_number || p.filename)}
                    </option>
                  ))}
              </select>
            </label>
            {selectedTaxInvoice ? (
              <InvoiceReview
                key={
                  selectedTaxInvoice.id + selectedTaxInvoice.source_signature
                }
                c={c}
                invoice={selectedTaxInvoice}
              />
            ) : (
              <p>
                Add and confirm an invoice to receive evidence-based
                suggestions.
              </p>
            )}
          </>
        )}
      </details>
    </>
  );
}
export function BusinessForm({
  c,
  business,
  reload,
}: {
  c: Context;
  business: Business;
  reload: () => void;
}) {
  const p = business.profile;
  const action = useCommand();
  const [employees, setEmployees] = useState<Employee[]>(p.employees || []);
  const amountFields: [string, string][] = [
    ["monthly_revenue", "Revenue this month"],
    ["monthly_profit", "Profit this month (negative if loss)"],
    ["monthly_operating_cost", "Operating cost this month"],
    ["annual_turnover", "Annual turnover"],
    ["loan_needed", "Loan amount needed"],
    ["marketing_spend", "Marketing spend this month"],
    ["attributed_sales", "Sales attributed to marketing"],
  ];
  return (
    <details className="panel">
      <summary>Enter or update business details</summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const nullable = (name: string) =>
            String(f.get(name) || "").trim() || null;
          const profile = {
            business_name: f.get("business_name"),
            business_type: f.get("business_type"),
            workforce_count:
              nullable("workforce_count") === null
                ? null
                : Number(f.get("workforce_count")),
            employees,
            msme_status: f.get("msme_status"),
            prior_tarun_repaid:
              nullable("prior_tarun_repaid") === null
                ? null
                : f.get("prior_tarun_repaid") === "yes",
            note: f.get("note"),
            tax_paid: Object.fromEntries(
              ["GST", "INCOME_TAX", "PAYROLL", "OTHER"].map((k) => [
                k,
                nullable(`tax_${k}`),
              ]),
            ),
            ...Object.fromEntries(amountFields.map(([k]) => [k, nullable(k)])),
          };
          void action.run(
            () =>
              c.api.command(productPath(c, "business"), {
                registration_id: c.registration.id,
                period: c.period,
                expected_version: business.version,
                profile,
              }),
            reload,
          );
        }}
      >
        <div className="form-grid">
          <Field
            name="business_name"
            value={p.business_name || c.registration.display_name}
            required
            maxLength={100}
          >
            Business name
          </Field>
          <label>
            Business type
            <select
              name="business_type"
              defaultValue={p.business_type || "UNKNOWN"}
            >
              {["UNKNOWN", "MANUFACTURING", "TRADING", "SERVICES", "OTHER"].map(
                (x) => (
                  <option key={x} value={x}>
                    {(
                      {
                        UNKNOWN: "Not known",
                        MANUFACTURING: "Manufacturing",
                        TRADING: "Trading",
                        SERVICES: "Services",
                        OTHER: "Other",
                        MICRO: "Micro business",
                        SMALL: "Small business",
                        MEDIUM: "Medium business",
                        NOT_MSME: "Not an MSME",
                      } as Record<string, string>
                    )[x] || x}
                  </option>
                ),
              )}
            </select>
          </label>
          <Field
            name="workforce_count"
            value={p.workforce_count == null ? "" : String(p.workforce_count)}
            type="number"
          >
            Number of people
          </Field>
          <label>
            MSME classification
            <select
              name="msme_status"
              defaultValue={p.msme_status || "UNKNOWN"}
            >
              {["UNKNOWN", "MICRO", "SMALL", "MEDIUM", "NOT_MSME"].map((x) => (
                <option key={x} value={x}>
                  {(
                    {
                      UNKNOWN: "Not known",
                      MANUFACTURING: "Manufacturing",
                      TRADING: "Trading",
                      SERVICES: "Services",
                      OTHER: "Other",
                      MICRO: "Micro business",
                      SMALL: "Small business",
                      MEDIUM: "Medium business",
                      NOT_MSME: "Not an MSME",
                    } as Record<string, string>
                  )[x] || x}
                </option>
              ))}
            </select>
          </label>
          {amountFields.slice(0, 3).map(([k, title]) => (
            <Field
              key={k}
              name={k}
              value={String(p[k as keyof typeof p] ?? "")}
              pattern={
                k === "monthly_profit"
                  ? "-?[0-9]+([.][0-9]{1,2})?"
                  : "[0-9]+([.][0-9]{1,2})?"
              }
            >
              {title} (₹)
            </Field>
          ))}
        </div>
        <p className="caption">
          Only the business name is required. Add other figures when available;
          absent figures stay unknown. These are shared monthly facts, not
          repeated invoice questions.
        </p>
        <details>
          <summary>Marketing figures, if available</summary>
          <div className="form-grid">
            {amountFields.slice(5).map(([k, title]) => (
              <Field
                key={k}
                name={k}
                value={String(p[k as keyof typeof p] ?? "")}
                pattern={
                  k === "monthly_profit"
                    ? "-?[0-9]+([.][0-9]{1,2})?"
                    : "[0-9]+([.][0-9]{1,2})?"
                }
              >
                {title} (₹)
              </Field>
            ))}
          </div>
        </details>
        <details>
          <summary>Loan and scheme details, if needed</summary>
          <div className="form-grid">
            {amountFields.slice(3, 5).map(([k, title]) => (
              <Field
                key={k}
                name={k}
                value={String(p[k as keyof typeof p] ?? "")}
                pattern={
                  k === "monthly_profit"
                    ? "-?[0-9]+([.][0-9]{1,2})?"
                    : "[0-9]+([.][0-9]{1,2})?"
                }
              >
                {title} (₹)
              </Field>
            ))}{" "}
            <label>
              Previous Tarun loan repaid?
              <select
                name="prior_tarun_repaid"
                defaultValue={
                  p.prior_tarun_repaid == null
                    ? ""
                    : p.prior_tarun_repaid
                      ? "yes"
                      : "no"
                }
              >
                <option value="">Not known</option>
                <option value="yes">Yes, reported repaid</option>
                <option value="no">No</option>
              </select>
            </label>
          </div>
        </details>
        <details>
          <summary>Tax already paid, if recorded</summary>
          <div className="form-grid">
            {" "}
            {["GST", "INCOME_TAX", "PAYROLL", "OTHER"].map((k) => (
              <Field
                key={k}
                name={`tax_${k}`}
                value={p.tax_paid?.[k] || ""}
                pattern="[0-9]+([.][0-9]{1,2})?"
              >
                {k.replaceAll("_", " ")} paid this month (₹)
              </Field>
            ))}
          </div>
        </details>
        <details>
          <summary>Private staff and salary records, optional</summary>
          <h3>People and monthly salaries</h3>
          <p className="muted">
            This list is private to the owner. It does not create login
            accounts.
          </p>
          {employees.map((person, i) => (
            <div className="form-grid" key={i}>
              <label>
                Name
                <input
                  required
                  maxLength={100}
                  value={person.name}
                  onChange={(e) =>
                    setEmployees((v) =>
                      v.map((x, j) =>
                        j === i ? { ...x, name: e.target.value } : x,
                      ),
                    )
                  }
                />
              </label>
              <label>
                Role
                <input
                  required
                  maxLength={100}
                  value={person.role}
                  onChange={(e) =>
                    setEmployees((v) =>
                      v.map((x, j) =>
                        j === i ? { ...x, role: e.target.value } : x,
                      ),
                    )
                  }
                />
              </label>
              <label>
                Monthly salary (₹)
                <input
                  pattern="[0-9]+([.][0-9]{1,2})?"
                  value={person.monthly_salary || ""}
                  onChange={(e) =>
                    setEmployees((v) =>
                      v.map((x, j) =>
                        j === i
                          ? { ...x, monthly_salary: e.target.value || null }
                          : x,
                      ),
                    )
                  }
                />
              </label>
              <button
                type="button"
                className="secondary"
                onClick={() => setEmployees((v) => v.filter((_, j) => j !== i))}
              >
                Remove person
              </button>
            </div>
          ))}
          <button
            type="button"
            className="secondary"
            disabled={employees.length >= 500}
            onClick={() =>
              setEmployees((v) => [
                ...v,
                { name: "", role: "", monthly_salary: null },
              ])
            }
          >
            Add a person
          </button>
        </details>
        <details>
          <summary>Additional context for the team, optional</summary>
          <label>
            Context for the team
            <textarea name="note" defaultValue={p.note} maxLength={2000} />
          </label>
        </details>
        <button disabled={action.busy}>Save business details</button>
        {action.feedback}
      </form>
    </details>
  );
}
