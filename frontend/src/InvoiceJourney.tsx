import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import type { Schemas } from "./contracts";
import { LoadState, Notice, path, useResource, writable } from "./shared";
import type { Context } from "./shared";

export type InvoiceWorkflow = Schemas["InvoiceWorkflowData"] & {
  reload: () => void;
};
export type InvoiceNavigate = (section: string, invoiceId: string) => void;

export default function InvoiceJourney({
  c,
  invoiceId,
  navigate,
  clear,
  children,
}: {
  c: Context;
  invoiceId?: string;
  navigate: InvoiceNavigate;
  clear: () => void;
  children: (workflow?: InvoiceWorkflow) => ReactNode;
}) {
  const link = useResource<Schemas["InvoiceWorkflowData"]>(
    c.api,
    invoiceId ? path(c, `passports/${invoiceId}/workflow`) : null,
    invoiceId ? 4000 : false,
  );
  const attempted = useRef("");
  const [catchupError, setCatchupError] = useState("");
  const sourceKey =
    link.data?.confirmed &&
    link.data.portal_import_id &&
    !link.data.run &&
    link.data.registration_id === c.registration.id &&
    link.data.period === c.period &&
    link.data.automation?.state !== "DELAYED" &&
    writable(c)
      ? `${invoiceId}:${link.data.purchase_import_id}:${link.data.portal_import_id}`
      : "";
  useEffect(() => {
    if (!sourceKey || !invoiceId || attempted.current === sourceKey) return;
    attempted.current = sourceKey;
    let active = true;
    setCatchupError("");
    void c.api
      .command(path(c, `passports/${invoiceId}/refresh`), {})
      .then(() => {
        if (active) link.reload();
      })
      .catch((error) => {
        if (active)
          setCatchupError(
            error.message ||
              "The comparison could not start. Open the comparison to retry.",
          );
      });
    return () => {
      active = false;
    };
  }, [sourceKey, invoiceId, c.api, c.workspace.id, link.reload]);
  if (!invoiceId) return children();
  if (!link.data) return <LoadState {...link} empty={false} />;
  if (
    link.data.registration_id !== c.registration.id ||
    link.data.period !== c.period
  )
    return (
      <Notice error>
        This invoice belongs to a different company or month. Return to Invoice
        desk.
      </Notice>
    );
  const workflow: InvoiceWorkflow = { ...link.data, reload: link.reload };
  const compared = workflow.run?.state === "COMPLETED" && workflow.result;
  return (
    <>
      <article className="card" aria-label="Selected invoice workflow">
        <strong>Invoice {workflow.invoice_number}</strong>
        <p>
          {!workflow.confirmed
            ? "Confirm the invoice details first."
            : !workflow.portal_import_id
              ? "Add or choose a GST statement to continue."
              : workflow.automation?.state === "DELAYED"
                ? String(
                    workflow.automation.message ||
                      "The comparison is delayed. Open the comparison to retry.",
                  )
                : workflow.run?.state === "FAILED"
                  ? "The comparison could not finish. Open it to review the error and retry."
                  : !compared
                    ? "Comparing your confirmed records automatically. Results will appear here shortly."
                    : "Your related cases and payment drafts are shown below. Review and approval remain your decision."}
        </p>
        <div className="controls">
          <button
            type="button"
            onClick={() => navigate("Invoice desk", invoiceId)}
          >
            Back to this invoice
          </button>
          {workflow.confirmed && !workflow.portal_import_id && (
            <button
              type="button"
              onClick={() => navigate("Sources", invoiceId)}
            >
              Add GST statement
            </button>
          )}
          {workflow.confirmed && workflow.portal_import_id && (
            <button
              type="button"
              onClick={() => navigate("Reconciliation", invoiceId)}
            >
              View comparison
            </button>
          )}
          {compared && (
            <>
              <button
                type="button"
                onClick={() => navigate("Cases & evidence", invoiceId)}
              >
                Open invoice cases
              </button>
              <button
                type="button"
                onClick={() => navigate("Payment drafts", invoiceId)}
              >
                Open invoice payment drafts
              </button>
            </>
          )}
          <button type="button" className="secondary" onClick={clear}>
            Show all records
          </button>
        </div>
      </article>
      {catchupError && <Notice error>{catchupError}</Notice>}
      {link.error && <Notice error>{link.error}</Notice>}
      {children(workflow)}
    </>
  );
}
