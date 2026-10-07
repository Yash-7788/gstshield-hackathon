import { useEffect, useState } from "react";
import type { Schemas } from "./contracts";
import type { Context } from "./shared";
import { LoadState, Notice, path, useCommand, useResource } from "./shared";

function Controls({
  c,
  item,
  changed,
}: {
  c: Context;
  item: Schemas["ActionData"];
  changed: () => void;
}) {
  const [draftId, setDraft] = useState("");
  const [code, setCode] = useState<Schemas["ConsentCodeData"] | null>(null);
  const action = useCommand();
  const recipients = useResource<Schemas["SupplierRecipientData"][]>(
    c.api,
    path(c, "whatsapp/supplier-recipients"),
  );
  const drafts = item.timeline
    .filter((event) => event.kind === "FOLLOWUP_DRAFT")
    .map((event) => ({
      id: String(event.id),
      snapshot:
        event.snapshot && typeof event.snapshot === "object"
          ? (event.snapshot as Record<string, unknown>)
          : {},
    }));
  useEffect(() => {
    if (recipients.denied) setCode(null);
  }, [recipients.denied]);
  const draft = drafts.find((event) => event.id === draftId);
  const proof = recipients.data?.find(
    (value) => value.action_id === item.id && value.draft_id === draftId,
  );
  useEffect(() => {
    if (!code) return;
    const timer = setTimeout(
      () => setCode(null),
      Math.max(0, code.expires_at * 1000 - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [code]);
  return (
    <>
      <p>
        Choose an unchanged saved follow-up draft with the supplier's
        international phone number. The supplier must send its one-use consent
        code to the configured bot. Consent grants no buyer workspace access.
        Sending also requires the operator's verified account and budget.
      </p>
      <label>
        Saved supplier draft
        <select
          value={draftId}
          onChange={(event) => {
            setDraft(event.target.value);
            setCode(null);
          }}
        >
          <option value="">Choose draft</option>
          {drafts.map((event) => (
            <option key={event.id} value={event.id}>
              {String(event.snapshot.contact)} ·{" "}
              {String(event.snapshot.request)}
            </option>
          ))}
        </select>
      </label>
      <button
        disabled={
          !draft || action.busy || recipients.loading || recipients.denied
        }
        onClick={() =>
          void action.run(
            () =>
              c.api.command<Schemas["ConsentCodeData"]>(
                path(c, "whatsapp/supplier-consent-code"),
                {
                  action_id: item.id,
                  draft_id: draftId,
                  expected_version: item.version,
                },
              ),
            (value) => setCode(value),
          )
        }
      >
        Generate supplier consent code
      </button>
      {code && (
        <Notice>
          Share this code with the intended supplier through your existing
          contact method. Ask them to send <strong>CONSENT {code.code}</strong>{" "}
          to the bot within ten minutes. It authorizes only this saved draft for{" "}
          {code.masked_phone}.
        </Notice>
      )}
      <button
        className="secondary"
        disabled={recipients.loading}
        onClick={recipients.reload}
      >
        Check supplier consent
      </button>
      <LoadState {...recipients} empty={false} />
      {proof && (
        <p>
          Consent received from {proof.masked_phone}. The supplier can send STOP
          to revoke it.
        </p>
      )}
      <button
        disabled={
          !proof ||
          !draft ||
          action.busy ||
          recipients.loading ||
          recipients.denied ||
          recipients.denied
        }
        onClick={() =>
          void action.run(
            () =>
              c.api.command<Schemas["DeliveryData"]>(
                path(c, "whatsapp/supplier-followups"),
                {
                  action_id: item.id,
                  draft_id: draftId,
                  recipient_id: proof?.id,
                  expected_version: item.version,
                },
              ),
            () => {
              setCode(null);
              changed();
              recipients.reload();
            },
          )
        }
      >
        Queue this consented supplier follow-up
      </button>
      <p>
        Queued does not mean sent or delivered. The WhatsApp section shows
        delivery state. This does not correct the invoice, file a return or
        recover credit.
      </p>
      {action.feedback}
    </>
  );
}

export default function SupplierDelivery(props: {
  c: Context;
  item: Schemas["ActionData"];
  changed: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>Consented WhatsApp supplier follow-up</summary>
      {open && (
        <Controls key={`${props.item.id}:${props.item.version}`} {...props} />
      )}
    </details>
  );
}
