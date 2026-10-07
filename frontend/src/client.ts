export class ApiError extends Error {
  status: number;
  code: string;
  uncertain: boolean;
  retryAfterMs: number;

  constructor(
    message: string,
    status = 0,
    code = "UNAVAILABLE",
    uncertain = false,
    retryAfterMs = 0,
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.uncertain = uncertain;
    this.retryAfterMs = retryAfterMs;
  }
}

export function apiOrigin(
  configured: string | undefined,
  location: Pick<Location, "hostname" | "protocol">,
): string {
  const host = location.hostname.includes(":")
    ? `[${location.hostname.replace(/^\[|\]$/g, "")}]`
    : location.hostname;

  const url = new URL(configured || `${location.protocol}//${host}:8000`);

  if (
    url.protocol !== "http:" ||
    location.protocol !== "http:" ||
    url.hostname !== location.hostname ||
    !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) ||
    !["", "/"].includes(url.pathname) ||
    url.search ||
    url.hash ||
    url.username ||
    url.password
  )
    throw new Error(
      "Use the same local HTTP hostname for the website and backend. Check frontend .env.example.",
    );

  return url.origin;
}

function retryDelay(value: string | null) {
  if (!value || !/^\d+$/.test(value)) return 0;
  return Math.min(Number(value), 300) * 1000;
}

export class ApiClient {
  base: string;
  csrf = "";
  epoch = 0;
  onExpired: () => void;

  private controllers = new Set<AbortController>();

  private receipts = new Map<string, string>();

  private flights = new Map<string, Promise<unknown>>();

  constructor(base: string, onExpired: () => void = () => {}) {
    this.base = base;
    this.onExpired = onExpired;
  }

  reset() {
    this.epoch++;
    this.csrf = "";
    for (const controller of this.controllers) controller.abort();
    this.controllers.clear();
    this.receipts.clear();
    this.flights.clear();
  }

  private async request<T>(
    path: string,
    method: string,
    body?: BodyInit,
    key?: string,
    signal?: AbortSignal,
    download = false,
  ): Promise<T> {
    if (
      !path.startsWith("/api/v1/") ||
      path.includes("..") ||
      path.includes("#") ||
      /[\\\x00-\x20\x7f]/.test(path) ||
      !/^\/api\/v1\/[a-zA-Z0-9_/-]+$/.test(path.split("?", 1)[0])
    )
      throw new Error("Unsupported request path");

    const controller = new AbortController();
    const epoch = this.epoch;

    this.controllers.add(controller);

    const timer = setTimeout(() => controller.abort(), 30000);

    const headers: Record<string, string> = {};

    if (body && !(body instanceof FormData))
      headers["Content-Type"] = "application/json";

    if (method !== "GET" && this.csrf) headers["X-CSRF-Token"] = this.csrf;

    if (key) headers["Idempotency-Key"] = key;

    try {
      const response = await fetch(this.base + path, {
        method,
        body,
        headers,
        credentials: "include",
        cache: "no-store",
        redirect: "error",
        signal: signal
          ? AbortSignal.any([signal, controller.signal])
          : controller.signal,
      });

      if (epoch !== this.epoch || signal?.aborted)
        throw new ApiError(
          "Selection changed; refresh the current workspace.",
          0,
          "OBSOLETE",
        );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        if (epoch !== this.epoch || signal?.aborted)
          throw new ApiError("Session changed.", 0, "OBSOLETE");

        if (response.status === 401 && path !== "/api/v1/auth/login")
          this.onExpired();

        const message = data?.error?.message;

        throw new ApiError(
          typeof message === "string"
            ? message
            : "The request could not be completed.",
          response.status,
          data?.error?.code || "HTTP_ERROR",
          response.status >= 500 && method !== "GET",
          retryDelay(response.headers?.get("Retry-After") ?? null),
        );
      }

      if (download) {
        const mime = (response.headers.get("content-type") || "").split(
          ";",
          1,
        )[0];

        if (!["application/pdf", "text/csv"].includes(mime))
          throw new ApiError("Unsupported report type.");

        const reader = response.body?.getReader();
        if (!reader) throw new ApiError("Report content unavailable.");

        const chunks: Uint8Array<ArrayBuffer>[] = [];
        let size = 0;

        try {
          while (true) {
            const chunk = await reader.read();
            if (chunk.done) break;
            size += chunk.value.byteLength;
            if (size > 5242880)
              throw new ApiError(
                "The report exceeds the 5 MiB download limit.",
              );
            chunks.push(new Uint8Array(chunk.value));
          }
        } finally {
          await reader.cancel();
        }

        if (epoch !== this.epoch || signal?.aborted)
          throw new ApiError("Session changed.", 0, "OBSOLETE");

        return new Blob(chunks, { type: mime }) as T;
      }

      const data = await response.json();

      if (epoch !== this.epoch || signal?.aborted)
        throw new ApiError(
          "Selection changed; refresh the current workspace.",
          0,
          "OBSOLETE",
        );

      if (!data || !("data" in data))
        throw new ApiError(
          "The backend reply could not be read. Refresh and try again.",
          0,
          "INVALID_REPLY",
          method !== "GET",
        );

      return data.data as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;

      throw new ApiError(
        method === "GET"
          ? "Cannot reach the local backend. Start GSTShield on this PC, then retry."
          : "The reply was interrupted. This action may have saved. Check its status before retrying the unchanged request.",
        0,
        "UNAVAILABLE",
        method !== "GET",
      );
    } finally {
      clearTimeout(timer);
      this.controllers.delete(controller);
    }
  }

  get<T>(path: string, signal?: AbortSignal) {
    return this.request<T>(path, "GET", undefined, undefined, signal);
  }

  auth<T>(path: string, payload?: unknown) {
    return this.request<T>(
      path,
      "POST",
      payload === undefined ? undefined : JSON.stringify(payload),
    );
  }

  command<T>(path: string, payload: unknown, method = "POST") {
    return this.write<T>(
      path,
      JSON.stringify(payload),
      JSON.stringify(payload),
      method,
    );
  }

  upload<T>(path: string, form: FormData, signature: string) {
    return this.write<T>(path, form, signature, "POST");
  }

  private write<T>(
    path: string,
    body: BodyInit,
    signature: string,
    method: string,
  ): Promise<T> {
    const identity = `${this.epoch}:${method}:${path}:${signature}`;

    const inFlight = this.flights.get(identity);
    if (inFlight) return inFlight as Promise<T>;

    if (!this.receipts.has(identity) && this.receipts.size >= 100)
      return Promise.reject(
        new ApiError(
          "Too many unresolved requests. Check saved records before refreshing your session.",
          0,
          "RETRY_LIMIT",
        ),
      );

    const key = this.receipts.get(identity) || crypto.randomUUID();
    this.receipts.set(identity, key);

    const task = this.request<T>(path, method, body, key)
      .then((result) => {
        this.receipts.delete(identity);
        return result;
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status > 0 && !error.uncertain)
          this.receipts.delete(identity);

        throw error;
      })
      .finally(() => this.flights.delete(identity));

    this.flights.set(identity, task);
    return task;
  }

  async download(path: string, filename: string, signal?: AbortSignal) {
    const epoch = this.epoch;
    const blob = await this.request<Blob>(
      path,
      "GET",
      undefined,
      undefined,
      signal,
      true,
    );
    if (epoch !== this.epoch || signal?.aborted)
      throw new ApiError("Report selection changed.", 0, "OBSOLETE");

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = /^gstshield-[a-z_]+-[0-9a-f-]{36}\.(pdf|csv)$/.test(
      filename,
    )
      ? filename
      : "gstshield-report";

    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
