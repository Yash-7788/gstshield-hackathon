import { useEffect, useMemo, useRef, useState } from "react";

import { ApiClient, apiOrigin } from "./client";

import type { Schemas } from "./contracts";

import { Notice, useCommand, useResource, path } from "./shared";

import type { Context } from "./shared";

import Sources from "./Sources";

import Reconciliation from "./Reconciliation";

import Cases from "./Cases";

import Actions from "./Actions";

import Proposals from "./Proposals";

import Reports from "./Reports";
import WhatsApp from "./WhatsApp";
import InvoiceJourney from "./InvoiceJourney";
import GuidedHelp from "./GuidedHelp";
import Today from "./Today";
import TeamWorkspace from "./TeamWorkspace";
import Assistants from "./Assistants";
import ProcessWorkspace from "./ProcessWorkspace";
import { Schemes } from "./ProductDirectories";
import { roleNames } from "./product";
import RoleHome from "./RoleHome";
import { workspaceSections, deskFor, sectionsFor, homeFor } from "./workspace";
import OwnerOverview from "./OwnerOverview";
import FocusedInvoiceDesk from "./FocusedInvoiceDesk";
import { BusinessForm } from "./OwnerWorkspace";
import type { Business } from "./product";
import type { Portal } from "./product";

function sectionFromHash() {
  try {
    const value = decodeURIComponent(location.hash.slice(1));
    return sections.includes(value) ? value : "";
  } catch {
    return "";
  }
}

const sections = workspaceSections;

const sectionDescriptions: Record<string, string> = {
  Assistants: "Understand the saved facts through your approved role.",
  "Shared process": "Move each invoice through a checked, shared review.",
  "Business setup": "Set company facts once. Your team reuses them.",
  "Owner desk": "Understand your business and its current priorities.",
  "Team desk": "Work together and see what changed.",
  Today: "See what needs your attention and why.",
  "Invoice desk":
    "Start with a bill. Follow its records, review and next step.",
  Sources: "Bring the records together before comparing them.",
  Reconciliation: "See what agrees, what differs and what needs another look.",
  "Cases & evidence": "Keep the facts and correction history in one place.",
  "Work queue": "See what needs attention and move the next step forward.",
  "Payment drafts": "Review the evidence before approving a payment proposal.",
  Reports: "Turn saved records into a clear, reviewable account.",
  WhatsApp: "Keep supplier follow-ups connected to the invoice history.",
};

function Login({
  api,
  onSession,
}: {
  api: ApiClient;
  onSession: (s: Schemas["SessionData"]) => void;
}) {
  const action = useCommand();
  const [entry, setEntry] = useState(
    new URLSearchParams(location.search).get("portal") === "team"
      ? "team"
      : "owner",
  );

  return (
    <main className="login">
      <a className="login-brand" href="/landing.html">
        GST<span>SHIELD</span>
      </a>
      <span className="eyebrow">GSTShield · Your invoice workspace</span>
      <h1>
        {entry === "owner"
          ? "Your business, in focus."
          : "Your team workspace."}
      </h1>
      <div className="portal-choice">
        <button
          type="button"
          className={entry === "owner" ? "" : "secondary"}
          onClick={() => setEntry("owner")}
        >
          Business owner
        </button>
        <button
          type="button"
          className={entry === "team" ? "" : "secondary"}
          onClick={() => setEntry("team")}
        >
          Team member
        </button>
      </div>
      <p>
        Pick up where you left off. Keep the bill, its supporting records and
        the next decision together.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          void action.run(
            () =>
              api.auth<Schemas["SessionData"]>("/api/v1/auth/login", {
                username: data.get("username"),
                password: data.get("password"),
                portal: entry,
              }),
            (session) => {
              sessionStorage.removeItem("gstshield_selection");
              history.replaceState(null, "", location.pathname);
              onSession(session);
            },
          );
        }}
      >
        <label>
          Username
          <input
            name="username"
            autoComplete="username"
            required
            minLength={1}
            maxLength={64}
          />
        </label>
        <label>
          Password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            minLength={1}
            maxLength={128}
          />
        </label>
        <button disabled={action.busy}>
          {action.busy ? "Signing in…" : "Sign in"}
        </button>
        {action.feedback}
      </form>
      <p className="muted">
        Owners manage the team. Team members sign in only after the owner
        creates their account and assigns a role.
      </p>
    </main>
  );
}

function rememberedSelection(userId: string) {
  try {
    const value = JSON.parse(
      sessionStorage.getItem("gstshield_selection") || "null",
    );
    if (
      value?.user_id === userId &&
      typeof value.workspace_id === "string" &&
      typeof value.registration_id === "string" &&
      typeof value.period === "string" &&
      /^\d{4}-(0[1-9]|1[0-2])$/.test(value.period)
    )
      return value as {
        workspace_id: string;
        registration_id: string;
        period: string;
      };
  } catch {}
  return {
    workspace_id: "",
    registration_id: "",
    period: new Date().toISOString().slice(0, 7),
  };
}
function Workspace({
  api,
  user,
  logout,
}: {
  api: ApiClient;
  user: Schemas["SessionData"];
  logout: () => void;
}) {
  const workspaces = useResource<Schemas["WorkspaceData"][]>(
    api,
    "/api/v1/workspaces",
    15000,
  );

  const [remembered] = useState(() => rememberedSelection(user.user_id));
  const [workspaceId, setWorkspace] = useState(remembered.workspace_id);
  const selected =
    workspaces.data?.find((w) => w.id === workspaceId) ||
    workspaces.data?.find((w) => w.role === "OWNER") ||
    workspaces.data?.find((w) => w.role === "REVIEWER") ||
    workspaces.data?.[0];

  const registrations = useResource<Schemas["RegistrationData"][]>(
    api,
    selected ? `/api/v1/workspaces/${selected.id}/registrations` : null,
  );

  const [registrationId, setRegistration] = useState(
    remembered.registration_id,
  );
  const registration =
    registrations.data?.find((r) => r.id === registrationId) ||
    registrations.data?.[0];

  const [period, setPeriod] = useState(remembered.period);
  const approvedPortal = useResource<Portal>(
    api,
    selected ? `/api/v1/workspaces/${selected.id}/product/portal` : null,
    15000,
  );
  const workingRole = approvedPortal.data?.roles[0];
  const allowedSections = sectionsFor(workingRole);
  const [requestedSection, setSection] = useState(sectionFromHash);
  const section = allowedSections.includes(requestedSection)
    ? requestedSection
    : homeFor(workingRole);
  useEffect(() => {
    if (approvedPortal.data && !allowedSections.includes(requestedSection)) {
      setSection(homeFor(workingRole));
      history.replaceState(
        null,
        "",
        `${location.pathname}#${encodeURIComponent(homeFor(workingRole))}`,
      );
    }
  }, [workingRole, requestedSection, approvedPortal.data]);
  const [invoiceFocus, setInvoiceFocus] = useState<{
    scope: string;
    id: string;
  } | null>(null);
  const scope = `${user.user_id}:${selected?.id}:${selected?.role}:${registration?.id}:${period}`;
  const focusedInvoice =
    invoiceFocus?.scope === scope ? invoiceFocus.id : undefined;
  const navigateInvoice = (destination: string, id: string) => {
    setInvoiceFocus(id ? { scope, id } : null);
    setSection(destination);
    location.hash = encodeURIComponent(destination);
  };
  const heading = useRef<HTMLHeadingElement>(null);
  const primary = deskFor(workingRole)
    .primary.filter((name) => allowedSections.includes(name))
    .slice(0, 3);
  const secondary = allowedSections.filter((name) => !primary.includes(name));
  const [moreOpen, setMoreOpen] = useState(false);
  useEffect(() => {
    setMoreOpen(false);
  }, [section, workingRole]);

  useEffect(() => {
    const change = () => {
      setSection(sectionFromHash());
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);

  const context: Context | null =
    selected &&
    registration &&
    !period.startsWith("0000") &&
    /^\d{4}-(0[1-9]|1[0-2])$/.test(period)
      ? {
          api,
          user,
          workspace: selected,
          registration,
          period,
          staffRole: workingRole,
        }
      : null;

  useEffect(() => {
    if (context)
      sessionStorage.setItem(
        "gstshield_selection",
        JSON.stringify({
          user_id: user.user_id,
          workspace_id: context.workspace.id,
          registration_id: context.registration.id,
          period,
        }),
      );
  }, [user.user_id, selected?.id, registration?.id, period]);
  useEffect(() => {
    if (selected && registration)
      heading.current?.focus({ preventScroll: true });
  }, [section, selected?.id, selected?.role, registration?.id, period]);
  const key = `${user.user_id}:${selected?.id}:${selected?.role}:${registration?.id}:${period}:${section}`;

  return (
    <div className="app" data-role={workingRole || "OBSERVER"}>
      <a
        className="skip-link"
        href="#workspace-content"
        onClick={(event) => {
          event.preventDefault();
          heading.current?.focus();
        }}
      >
        Skip to workspace content
      </a>
      <header className="workspace-header">
        <div>
          <a className="brand" href="/landing.html">
            <span className="brand-mark" aria-hidden="true">
              S
            </span>{" "}
            GST<span>SHIELD</span>
          </a>
          <span className="muted">Pay the vendor. Keep the credit.</span>
        </div>
        <div>
          <span>{user.username}</span>{" "}
          <button className="secondary" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <div className="context">
        <label>
          Workspace
          <select
            value={selected?.id || ""}
            onChange={(e) => {
              setInvoiceFocus(null);
              setWorkspace(e.target.value);
              setRegistration("");
            }}
          >
            {workspaces.data?.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} · {w.role.toLowerCase()}
              </option>
            ))}
          </select>
        </label>
        <label>
          Registration
          <select
            value={registration?.id || ""}
            onChange={(e) => {
              setInvoiceFocus(null);
              setRegistration(e.target.value);
            }}
          >
            {registrations.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.display_name} · {r.gstin}
              </option>
            ))}
          </select>
        </label>
        <label>
          Accounting month
          <input
            type="month"
            value={period}
            onChange={(e) => {
              setInvoiceFocus(null);
              setPeriod(e.target.value);
            }}
          />
        </label>
        {approvedPortal.data && (
          <div className="role-selector">
            <span className="eyebrow">Assigned role</span>
            <strong>
              {roleNames[workingRole || "OBSERVER"] ||
                "Owner must set one role"}
            </strong>
          </div>
        )}
      </div>
      <div className="layout">
        <nav className="workspace-nav" aria-label="Workspace sections">
          <div className="nav-primary">
            {primary.map((name, index) => (
              <a
                key={name}
                href={`#${encodeURIComponent(name)}`}
                aria-current={section === name ? "page" : undefined}
                onClick={() => setMoreOpen(false)}
              >
                <span className="nav-index" aria-hidden="true">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {name}
              </a>
            ))}
          </div>
          {!!secondary.length && (
            <div
              className="nav-more"
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  setMoreOpen(false);
                  e.currentTarget.querySelector("button")?.focus();
                }
              }}
            >
              <button
                type="button"
                aria-expanded={moreOpen}
                aria-controls="workspace-tools-index"
                onClick={() => setMoreOpen((open) => !open)}
              >
                More tools{" "}
                <span aria-hidden="true">{moreOpen ? "−" : "+"}</span>
              </button>
              {moreOpen && (
                <div className="tools-index" id="workspace-tools-index">
                  <p>Supporting tools for your assigned role.</p>
                  {secondary.map((name) => (
                    <a
                      key={name}
                      href={`#${encodeURIComponent(name)}`}
                      aria-current={section === name ? "page" : undefined}
                    >
                      {name}
                      <span aria-hidden="true">↗</span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}
        </nav>
        <main data-section={section}>
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {registration?.display_name || "Your company"} · {period}
              </span>
              <h1 id="workspace-content" ref={heading} tabIndex={-1}>
                {section}
              </h1>
              <p className="section-intro">{sectionDescriptions[section]}</p>
            </div>
            <span className="page-stamp">
              {workingRole
                ? roleNames[workingRole] || "Team view"
                : "Loading your role…"}
            </span>
          </div>
          {workspaces.error && (
            <Notice error>
              {workspaces.error}{" "}
              <button onClick={workspaces.reload}>Retry</button>
            </Notice>
          )}
          {registrations.error && (
            <Notice error>
              {registrations.error}{" "}
              <button onClick={registrations.reload}>Retry</button>
            </Notice>
          )}
          {!context || !approvedPortal.data ? (
            <Notice>
              {workspaces.loading ||
              registrations.loading ||
              approvedPortal.loading
                ? "Loading your permitted workspace…"
                : "Select a workspace, registration and valid accounting month. Ask the operator if none is listed."}
            </Notice>
          ) : (
            <section
              key={key + ":" + workingRole + ":" + (focusedInvoice || "all")}
            >
              {selected?.role === "VIEWER" && (
                <Notice>
                  Financial records are read-only. Your approved shared-work
                  actions remain available.
                </Notice>
              )}
              {workingRole !== "OWNER" && <GuidedHelp c={context} />}
              <InvoiceJourney
                c={context}
                invoiceId={
                  section === "Invoice desk" ? undefined : focusedInvoice
                }
                navigate={navigateInvoice}
                clear={() => setInvoiceFocus(null)}
              >
                {(workflow) => (
                  <>
                    {section === "Owner desk" && (
                      <>
                        <OwnerOverview c={context} />
                        <Schemes c={context} />
                      </>
                    )}
                    {section === "Business setup" && (
                      <BusinessSetup c={context} />
                    )}
                    {section === "Team desk" && (
                      <>
                        {workingRole !== "OWNER" && (
                          <RoleHome
                            c={context}
                            role={workingRole}
                            navigate={navigateInvoice}
                          />
                        )}
                        <TeamWorkspace
                          c={context}
                          workingRole={workingRole}
                          approvedPortal={approvedPortal.data || undefined}
                        />
                      </>
                    )}
                    {section === "Assistants" && (
                      <Assistants
                        key={workingRole}
                        c={context}
                        initialRole={workingRole}
                        approvedPortal={approvedPortal.data || undefined}
                      />
                    )}
                    {section === "Shared process" && (
                      <ProcessWorkspace
                        c={context}
                        navigate={navigateInvoice}
                      />
                    )}
                    {section === "Today" && (
                      <Today c={context} navigate={navigateInvoice} />
                    )}
                    {section === "Invoice desk" && (
                      <FocusedInvoiceDesk
                        c={context}
                        initialInvoiceId={focusedInvoice}
                        navigate={navigateInvoice}
                      />
                    )}
                    {section === "Sources" && <Sources c={context} />}
                    {section === "Reconciliation" && (
                      <Reconciliation c={context} workflow={workflow} />
                    )}
                    {section === "Cases & evidence" && (
                      <Cases c={context} workflow={workflow} />
                    )}
                    {section === "Work queue" && <Actions c={context} />}
                    {section === "Payment drafts" && (
                      <Proposals c={context} workflow={workflow} />
                    )}
                    {section === "Reports" && <Reports c={context} />}
                    {section === "WhatsApp" && <WhatsApp c={context} />}
                  </>
                )}
              </InvoiceJourney>
            </section>
          )}
          <footer>
            Reviews and recorded observations do not verify legal entitlement or
            perform tax filing or payments. WhatsApp delivery is confirmed only
            by provider delivery status.
          </footer>
        </main>
      </div>
    </div>
  );
}

function BusinessSetup({ c }: { c: Context }) {
  const business = useResource<Business>(
    c.api,
    path(
      c,
      `product/business?registration_id=${c.registration.id}&period=${c.period}`,
    ),
  );
  return (
    <>
      <Notice>
        Company facts are entered once. Revenue and salaries cannot be
        calculated from a supplier bill.
      </Notice>
      {business.data && (
        <BusinessForm
          key={business.data.version}
          c={c}
          business={business.data}
          reload={business.reload}
        />
      )}
    </>
  );
}

export default function App() {
  const [session, setSession] = useState<Schemas["SessionData"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  const setup = useMemo(() => {
    try {
      return {
        api: new ApiClient(
          apiOrigin(import.meta.env.VITE_API_BASE_URL, location),
        ),
        error: "",
      };
    } catch (error) {
      return {
        api: null,
        error:
          error instanceof Error ? error.message : "Configuration unavailable",
      };
    }
  }, []);

  const api = setup.api;
  const [signingOut, setSigningOut] = useState(false);

  if (api)
    api.onExpired = () => {
      api.reset();
      sessionStorage.removeItem("gstshield_selection");
      setSession(null);
      setMessage(
        session
          ? "Your access has expired or been revoked. Sign in again."
          : "",
      );
    };

  const accept = (data: Schemas["SessionData"]) => {
    if (api) {
      sessionStorage.removeItem("gstshield_signed_out");
      api.csrf = data.csrf_token;
      setSession(data);
      setMessage("");
    }
  };

  useEffect(() => {
    if (!api || sessionStorage.getItem("gstshield_signed_out")) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    api
      .get<Schemas["SessionData"]>("/api/v1/auth/session", controller.signal)
      .then(accept)
      .catch((error) => {
        if (!controller.signal.aborted && error.status !== 401)
          setMessage(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api]);

  useEffect(() => {
    if (!api || !session) return;
    const timer = setTimeout(
      () => {
        api.reset();
        sessionStorage.removeItem("gstshield_selection");
        setSession(null);
        setMessage("Your session expired. Sign in again.");
      },
      Math.max(0, Date.parse(session.expires_at) - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [api, session]);

  if (!api)
    return (
      <main className="login">
        <h1>GSTShield</h1>
        <Notice error>{setup.error}</Notice>
      </main>
    );

  if (loading)
    return (
      <main className="login">
        <Notice>Checking your session…</Notice>
      </main>
    );

  const logout = () => {
    if (signingOut) return;
    setSigningOut(true);
    sessionStorage.setItem("gstshield_signed_out", "1");
    sessionStorage.removeItem("gstshield_selection");
    history.replaceState(null, "", location.pathname);
    setSession(null);
    const signout = new ApiClient(api.base);
    signout.csrf = api.csrf;
    api.reset();
    const pending = signout.auth("/api/v1/auth/logout");
    void pending
      .then(() => setMessage("Signed out."))
      .catch(() =>
        setMessage(
          "Private screens are cleared. Server sign-out could not be confirmed; the cookie remains valid until expiry or operator revocation. Explicit sign-in is required here.",
        ),
      )
      .finally(() => setSigningOut(false));
  };

  return (
    <>
      {message && <Notice>{message}</Notice>}
      {signingOut ? (
        <main className="login">
          <Notice>Signing out…</Notice>
        </main>
      ) : session ? (
        <Workspace
          key={session.user_id}
          api={api}
          user={session}
          logout={logout}
        />
      ) : (
        <Login api={api} onSession={accept} />
      )}
    </>
  );
}
