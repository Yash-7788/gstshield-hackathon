import type { Context } from "./shared";
import { useResource, LoadState, money } from "./shared";
import { productPath, selection, roleNames } from "./product";
import type { Business } from "./product";
import { deskFor } from "./workspace";
import Today from "./Today";
import LedgerFlower from "./LedgerFlower";

export default function RoleHome({
  c,
  role = "OBSERVER",
  navigate,
}: {
  c: Context;
  role?: string;
  navigate: (section: string, id: string) => void;
}) {
  const desk = deskFor(role);
  const hasFigures = ["CFO", "CMA", "CMO", "CEO", "OWNER"].includes(role);
  const business = useResource<Business>(
    c.api,
    hasFigures ? productPath(c, `business?${selection(c)}`) : null,
  );
  const p = business.data?.profile;
  const figures =
    role === "CMO"
      ? [
          ["Marketing spend", p?.marketing_spend],
          ["Attributed sales", p?.attributed_sales],
        ]
      : role === "CMA"
        ? [
            ["Operating cost", p?.monthly_operating_cost],
            ["Profit", p?.monthly_profit],
            ["Recorded payroll", p?.recorded_payroll_total],
          ]
        : [
            ["Revenue", p?.monthly_revenue],
            ["Profit", p?.monthly_profit],
          ];
  const handoff = () =>
    document.getElementById("team-updates")?.scrollIntoView({ block: "start" });
  return (
    <section className="role-home" data-desk={role} aria-label="Your role desk">
      <div className="role-brief">
        <div className="role-intro">
          <span className="eyebrow">
            {roleNames[role] || "Shared team view"}
          </span>
          <h2>{desk.title}</h2>
          <p>{desk.purpose}</p>
          <div className="role-actions">
            <button onClick={() => navigate(desk.action, "")}>
              Open {desk.action.toLowerCase()} <span aria-hidden="true">↗</span>
            </button>
            <button className="text-button" onClick={handoff}>
              Share a handoff
            </button>
          </div>
        </div>
        <aside className="role-book" aria-label="Your working ledger">
          <span className="book-imprint">GST SHIELD</span>
          <LedgerFlower className="book-flower" />
          <h3>{roleNames[role] || "Team"}</h3>
          <p>
            {role === "CA"
              ? "Four records. One invoice."
              : role === "CFO"
                ? "Evidence before payment."
                : role === "CMO"
                  ? "Spend. Sales. Shared context."
                  : role === "CMA"
                    ? "Costs from saved facts."
                    : role === "CTO"
                      ? "Connections and their limits."
                      : role === "COO"
                        ? "Every handoff, recorded."
                        : "Your team's saved work."}
          </p>
          <span className="book-foot">{c.period} · Working ledger</span>
        </aside>
      </div>
      {["CA", "ACCOUNTS", "WAREHOUSE"].includes(role) && (
        <div className="record-ribbon" aria-label="The four supporting records">
          {["Bill", "Order", "Delivery", "GST statement"].map((record, i) => (
            <div key={record}>
              <span>{String(i + 1).padStart(2, "0")}</span>
              <strong>{record}</strong>
            </div>
          ))}
        </div>
      )}
      {hasFigures && (
        <div
          className={
            role === "CMO"
              ? "marketing-records"
              : role === "CMA"
                ? "cost-records"
                : "business-records"
          }
        >
          <LoadState {...business} empty={false} />
          {business.data && (
            <>
              <span className="eyebrow">Reported this month</span>
              <dl className="role-figures">
                {figures.map(([name, amount]) => (
                  <div key={name}>
                    <dt>{name}</dt>
                    <dd>{money(amount)}</dd>
                  </div>
                ))}
              </dl>
              <p className="caption">
                Entered by your owner. Unknown means the figure has not been
                supplied.
              </p>
            </>
          )}
        </div>
      )}
      {["CA", "CFO"].includes(role) && (
        <Today
          c={c}
          navigate={navigate}
          compact
          limit={3}
          title={
            role === "CFO"
              ? "Payment decisions to review"
              : role === "CA"
                ? "Invoices that need attention"
                : role === "CEO"
                  ? "Decisions waiting for a review"
                  : undefined
          }
        />
      )}
      {role === "CMO" && (
        <p className="role-context-note">
          Marketing accounts are not connected. Share campaign context below;
          your owner can record spend and attributed sales.
        </p>
      )}
      {role === "CMA" && (
        <p className="role-context-note">
          Ask the cost assistant to explain these figures alongside confirmed
          invoices. It will list missing facts before suggesting an action.
        </p>
      )}
      {role === "CTO" && (
        <dl className="systems-records">
          <div>
            <dt>01 · Storage</dt>
            <dd>Saved on the local PC</dd>
          </div>
          <div>
            <dt>02 · Government portal</dt>
            <dd>Uploaded statements. No direct filing.</dd>
          </div>
          <div>
            <dt>03 · Bank</dt>
            <dd>Simulated gateway</dd>
          </div>
          <div>
            <dt>04 · Firm infrastructure</dt>
            <dd>Not connected</dd>
          </div>
        </dl>
      )}
      {role === "COO" && (
        <div className="operations-path">
          <span className="eyebrow">The handoff path</span>
          <ol>
            <li>Confirm the invoice</li>
            <li>Collect order and delivery</li>
            <li>Review the decision</li>
            <li>Finish the shared process</li>
          </ol>
          <p className="caption">
            Read team handoffs below. Ask the assigned accounting or receiving
            teammate for missing evidence.
          </p>
        </div>
      )}
    </section>
  );
}
