import { useCallback, useEffect, useRef, useState } from "react";

import type { ReactNode } from "react";

import { ApiClient, ApiError } from "./client";

import type { Schemas } from "./contracts";

export type Context = {
  api: ApiClient;
  user: Schemas["SessionData"];
  workspace: Schemas["WorkspaceData"];
  registration: Schemas["RegistrationData"];
  period: string;
};

export const path = (c: Context, suffix: string) =>
  `/api/v1/workspaces/${c.workspace.id}/${suffix}`;

export const writable = (c: Context) => c.workspace.role !== "VIEWER";

export const text = (value: unknown): string =>
  value === null || value === undefined
    ? "Unknown"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);

export const label = (value: string) =>
  value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (c) => c.toUpperCase());

const amountFormatter = new Intl.NumberFormat("en-IN");

export function money(value: unknown) {
  if (typeof value !== "string" || !/^-?\d+\.\d{2}$/.test(value))
    return "Unknown";

  const [whole, fraction] = value.split(".");
  const integer = whole === "-0" ? "-0" : amountFormatter.format(BigInt(whole));
  return `₹${integer}.${fraction}`;
}

export const utcDay = () => new Date().toISOString().slice(0, 10);

export function date(value: unknown) {
  if (value === null || value === undefined) return "Not recorded";
  const d = new Date(typeof value === "number" ? value * 1000 : String(value));
  return Number.isNaN(d.valueOf()) ? "Not recorded" : d.toLocaleString();
}

export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      role={error ? "alert" : "status"}
      className={error ? "notice error" : "notice"}
    >
      {children}
    </div>
  );
}

export function Badge({ value }: { value: string }) {
  return <span className="badge">{label(value)}</span>;
}

export function Facts({ values }: { values: Record<string, unknown> }) {
  return (
    <dl className="facts">
      {Object.entries(values).map(([k, v]) => (
        <div key={k}>
          <dt>{label(k)}</dt>
          <dd>{text(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function History({ rows }: { rows: Record<string, unknown>[] }) {
  const [open, setOpen] = useState(false);
  const [limit, setLimit] = useState(20);
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>Evidence and action history ({rows.length})</summary>
      {open && (
        <>
          <p className="muted">
            Showing {Math.min(limit, rows.length)} of {rows.length} retained
            events.
          </p>
          {rows.slice(0, limit).map((row, i) => (
            <article key={text(row.id) + i}>
              <strong>{label(text(row.kind || row.action))}</strong>{" "}
              <small>{date(row.created_at)}</small>
              <Facts values={row} />
            </article>
          ))}
          {limit < rows.length && (
            <button
              type="button"
              className="secondary"
              onClick={() => setLimit((value) => value + 20)}
            >
              Show more history
            </button>
          )}
        </>
      )}
    </details>
  );
}

export function useResource<T>(
  api: ApiClient,
  url: string | null,
  watch: boolean | number = false,
) {
  const epoch = api.epoch;
  const [state, setState] = useState<{
    api: ApiClient | null;
    epoch: number;
    url: string | null;
    data: T | null;
    error: string;
    loading: boolean;
    refreshing: boolean;
    denied: boolean;
  }>({
    api: null,
    epoch: -1,
    url: null,
    data: null,
    error: "",
    loading: false,
    refreshing: false,
    denied: false,
  });
  const [revision, bump] = useState(0);
  const reload = useCallback(() => bump((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let inFlight = false;
    let polling = !!url;
    let failures = 0;
    let pendingReads = 0;
    let nextAt = 0;
    const interval = typeof watch === "number" ? watch : 2000;
    setState((previous) => {
      const data =
        previous.api === api &&
        previous.epoch === epoch &&
        previous.url === url &&
        !previous.denied
          ? previous.data
          : null;
      return {
        api,
        epoch,
        url,
        data,
        error: "",
        loading: !!url,
        refreshing: !!url && data !== null,
        denied: false,
      };
    });
    if (!url) return;

    const schedule = (delay: number) => {
      clearTimeout(timer);
      nextAt = Date.now() + delay;
      if (document.visibilityState === "visible")
        timer = setTimeout(() => void load(), delay);
    };
    const load = async () => {
      if (
        controller.signal.aborted ||
        inFlight ||
        document.visibilityState !== "visible"
      )
        return;
      inFlight = true;
      try {
        const data = await api.get<T>(url, controller.signal);
        if (controller.signal.aborted) return;
        failures = 0;
        setState({
          api,
          epoch,
          url,
          data,
          error: "",
          loading: false,
          refreshing: false,
          denied: false,
        });
        const status = (data as { state?: string } | null)?.state;
        polling =
          typeof watch === "number" ||
          (watch === true &&
            !!status &&
            ["PENDING", "QUEUED", "RUNNING", "PARSING", "RECEIVED"].includes(
              status,
            ));
        if (polling) {
          pendingReads++;
          schedule(
            watch === true
              ? Math.min(2000 + Math.max(0, pendingReads - 2) * 1000, 5000)
              : interval,
          );
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        const denied =
          error instanceof ApiError && [401, 403, 404].includes(error.status);
        setState((previous) => ({
          ...previous,
          data: denied ? null : previous.data,
          error: error instanceof Error ? error.message : "Unable to load",
          loading: false,
          refreshing: false,
          denied,
        }));
        failures++;
        polling = !!watch && !denied;
        if (polling)
          schedule(
            Math.max(
              Math.min(interval * 2 ** Math.min(failures, 4), 60000),
              error instanceof ApiError ? error.retryAfterMs : 0,
            ),
          );
      } finally {
        inFlight = false;
      }
    };
    const visible = () => {
      clearTimeout(timer);
      if (!polling || inFlight || document.visibilityState !== "visible")
        return;
      schedule(Math.max(0, nextAt - Date.now()));
    };
    document.addEventListener("visibilitychange", visible);
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [api, epoch, url, revision, watch]);

  return {
    ...(state.api === api && state.epoch === epoch && state.url === url
      ? state
      : {
          data: null,
          error: "",
          loading: !!url,
          refreshing: false,
          denied: false,
        }),
    reload,
  };
}

export function useCommand() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const alive = useRef(true);
  const gate = useRef(false);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  async function run<T>(
    work: () => Promise<T>,
    done?: (result: T) => void,
    success = "Saved. The backend record has been updated.",
  ) {
    if (gate.current) return;
    gate.current = true;
    setBusy(true);
    setError("");
    setMessage("");

    try {
      const result = await work();
      if (alive.current) {
        done?.(result);
        setMessage(success);
      }
    } catch (error) {
      if (alive.current)
        setError(error instanceof Error ? error.message : "Action unavailable");
    } finally {
      gate.current = false;
      if (alive.current) setBusy(false);
    }
  }

  return {
    busy,
    run,
    message,
    error,
    feedback: (
      <>
        {error && <Notice error>{error}</Notice>}
        {message && <Notice>{message}</Notice>}
      </>
    ),
  };
}

export function LoadState({
  loading,
  error,
  empty,
  reload,
  refreshing = false,
}: {
  loading: boolean;
  refreshing?: boolean;
  error: string;
  empty: boolean;
  reload: () => void;
}) {
  return (
    <>
      {loading && (
        <Notice>
          {refreshing ? "Refreshing saved records…" : "Loading saved records…"}
        </Notice>
      )}
      {error && (
        <Notice error>
          {error}{" "}
          <button disabled={loading} onClick={reload}>
            Retry loading
          </button>
        </Notice>
      )}
      {!loading && !error && empty && (
        <Notice>No saved records in this selection yet.</Notice>
      )}
    </>
  );
}

export function Field({
  name,
  children,
  type = "text",
  value,
  required = false,
  maxLength = 1000,
  pattern,
}: {
  name: string;
  children: ReactNode;
  type?: string;
  value?: string;
  required?: boolean;
  maxLength?: number;
  pattern?: string;
}) {
  return (
    <label>
      {children}
      <input
        name={name}
        type={type}
        defaultValue={value}
        required={required}
        maxLength={maxLength}
        pattern={pattern}
        step={type === "number" ? "1" : undefined}
      />
    </label>
  );
}

export function values(form: HTMLFormElement): Record<string, string> {
  return Object.fromEntries(
    [...new FormData(form)].map(([k, v]) => [k, String(v)]),
  );
}

export function payloadError(message: string): never {
  throw new ApiError(message, 422, "INPUT_INVALID");
}

export function Job({ c, id }: { c: Context; id: string }) {
  const job = useResource<Schemas["JobData"]>(c.api, path(c, `jobs/${id}`));
  return (
    <>
      <LoadState {...job} empty={false} />
      {job.data && (
        <Notice>
          Processing job: {label(job.data.state)}{" "}
          {job.data.error_code ? `· ${job.data.error_code}` : ""}
        </Notice>
      )}
    </>
  );
}
