import { useEffect, useState } from "react";
import type { Schemas } from "./contracts";
import type { Context } from "./shared";
import {
  Badge,
  LoadState,
  Notice,
  path,
  useCommand,
  useResource,
} from "./shared";

export default function WhatsApp({ c }: { c: Context }) {
  const status = useResource<Schemas["ChannelData"]>(
    c.api,
    path(c, "whatsapp"),
    15000,
  );
  const [code, setCode] = useState<Schemas["LinkCodeData"] | null>(null);
  const action = useCommand();
  const link = status.data?.link;
  useEffect(() => {
    if (!code) return;
    const timer = setTimeout(
      () => setCode(null),
      Math.max(0, code.expires_at * 1000 - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [code]);
  useEffect(() => {
    if (status.denied || link) setCode(null);
  }, [status.denied, link?.id]);
  return (
    <>
      <p>
        Use the same saved sources, comparisons and reports from your phone. The
        local PC must remain running. Confirm imports and review evidence on
        this website.
      </p>
      <LoadState {...status} empty={false} />
      {status.data && (
        <>
          {!status.data.enabled && (
            <Notice>
              WhatsApp is disabled. The operator must configure a Meta account
              and an HTTPS callback before linking a phone. The local website
              still works.
            </Notice>
          )}
          {status.data.enabled && !status.data.sending_enabled && (
            <Notice>
              Outbound sending is paused or its configured budget is exhausted.
              Saved phone tasks remain available here; no reply is claimed as
              delivered.
            </Notice>
          )}
          {link ? (
            <article>
              <h2>Linked phone {link.masked_phone}</h2>
              <p>
                Linked month: {link.period}. Selected month: {c.period}.
              </p>
              <p>
                Context changes revoke old upload intents, queued replies and
                report links.
              </p>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  void action.run(
                    () =>
                      c.api.command<Schemas["ChannelData"]>(
                        path(c, "whatsapp/context"),
                        {
                          registration_id: c.registration.id,
                          period: c.period,
                          expected_version: link.version,
                          consent_alerts: form.get("alerts") === "on",
                        },
                      ),
                    status.reload,
                  );
                }}
              >
                <label>
                  <input
                    key={String(link.consent_alerts)}
                    type="checkbox"
                    name="alerts"
                    defaultChecked={link.consent_alerts}
                  />{" "}
                  Allow recorded review reminders to this phone within a
                  permitted reply window and the operator's send budget
                </label>
                <button disabled={action.busy || status.loading}>
                  Use selected registration and month
                </button>
              </form>
              <button
                className="secondary"
                disabled={action.busy || status.loading}
                onClick={() =>
                  void action.run(
                    () =>
                      c.api.command(path(c, "whatsapp/unlink"), {
                        expected_version: link.version,
                      }),
                    () => {
                      setCode(null);
                      status.reload();
                    },
                  )
                }
              >
                Unlink phone and revoke report links
              </button>
            </article>
          ) : (
            status.data.enabled && (
              <article>
                <h2>Link your phone</h2>
                <p>
                  The code authorizes only your permitted workspace, selected
                  registration and {c.period}. It expires after ten minutes and
                  can be used once. Do not share it with another person.
                </p>
                <button
                  disabled={action.busy || status.loading}
                  onClick={() =>
                    void action.run(
                      () =>
                        c.api.command<Schemas["LinkCodeData"]>(
                          path(c, "whatsapp/link-code"),
                          {
                            registration_id: c.registration.id,
                            period: c.period,
                          },
                        ),
                      (value) => setCode(value),
                    )
                  }
                >
                  Generate one-use link code
                </button>
                {code && (
                  <Notice>
                    Send <strong>LINK {code.code}</strong> to the configured
                    WhatsApp number. Expires{" "}
                    {new Date(code.expires_at * 1000).toLocaleTimeString()}. A
                    fresh request replaces any earlier code.
                  </Notice>
                )}
                <button
                  className="secondary"
                  disabled={status.loading}
                  onClick={status.reload}
                >
                  Check linked status
                </button>
              </article>
            )
          )}
          <p>
            Commands: HELP, STATUS, UPLOAD PURCHASE, UPLOAD 2B, RUN, REPORT and
            UNLINK. CSV/XLSX uploads need explicit website confirmation. Replies
            describe uploaded evidence, not government verification or legal
            approval.
          </p>
          <h2>Recent reply delivery states</h2>
          <p>
            API acknowledgement means accepted by Meta. Delivered/read require
            provider callbacks. An uncertain send is never automatically resent.
          </p>
          {status.data.deliveries.length === 0 ? (
            <p>No recorded replies for your current link.</p>
          ) : (
            status.data.deliveries.map((item) => (
              <article key={item.id}>
                <Badge value={item.state} />
                <p>{item.id}</p>
                {item.action_id && <p>Supplier action: {item.action_id}</p>}
                {(item.history?.length ?? 0) > 0 && (
                  <p>
                    Recorded states:{" "}
                    {item.history?.map((value) => value.state).join(" → ")}
                  </p>
                )}
                {item.error_code && <p>{item.error_code}</p>}
              </article>
            ))
          )}
          <p className="muted">
            Remaining configured send attempts:{" "}
            {status.data.remaining_send_budget}. This counter is an application
            limit, not a provider billing guarantee. Physical-phone verification
            is still pending.
          </p>
        </>
      )}
      {action.feedback}
    </>
  );
}
