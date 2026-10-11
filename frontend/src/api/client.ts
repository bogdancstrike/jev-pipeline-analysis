/**
 * The HTTP client every request goes through. It guarantees:
 * 1. Failures become `ApiError` with the server's `{error, message, details}` and the
 *    `x-request-id`, so an error on screen can be found in the backend logs.
 * 2. Every call accepts an AbortSignal (react-query passes one), so stale requests die.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, details: Record<string, unknown>, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  /** Worth retrying: the server is busy or still loading, or the network dropped. */
  get transient(): boolean {
    return this.status === 0 || this.status === 429 || this.status >= 500;
  }
}

type Params = Record<string, string | number | boolean | string[] | undefined>;

export function buildQuery(params: Params = {}): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === "" || v === false) continue;
    if (Array.isArray(v)) v.forEach((x) => q.append(k, x));
    else q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

export async function toApiError(res: Response): Promise<ApiError> {
  let body: { error?: string; message?: string; details?: Record<string, unknown> } = {};
  try { body = await res.json(); } catch { /* not JSON (proxy error page) */ }
  return new ApiError(res.status, body.error ?? "http_error", body.message ?? `${res.status} ${res.statusText}`,
                      body.details ?? {}, res.headers.get("x-request-id"));
}

export async function request<T>(path: string, init: RequestInit & { params?: Params } = {}): Promise<T> {
  const { params, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`/api${path}${buildQuery(params)}`, rest);
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "network", "Cannot reach the server. Check your connection.", {}, null);
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
