export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

/** Error with a human-readable message and the HTTP status (0 = network failure). */
export class ApiError extends Error {
  status: number;
  /** Parsed FastAPI `detail` (string, validation list or structured object such as duplicate warnings). */
  detail: unknown;
  constructor(message: string, status: number, detail: unknown = null) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

const STATUS_MESSAGES: Record<number, string> = {
  404: "Not found.",
  422: "The request could not be processed.",
  500: "The analysis engine hit an internal error. Please try again.",
  501: "This feature is not available yet.",
};

/** Turn FastAPI's {"detail": ...} (string or validation list) into one readable line. */
function readableDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : null))
      .filter(Boolean)
      .map((m) => (m as string).replace(/^Value error, /, ""));
    return msgs.length ? msgs.join(" ") : null;
  }
  return null;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    const headers=new Headers(init?.headers);
    const token=sessionStorage.getItem('rca_token');
    if(token) headers.set('Authorization',`Bearer ${token}`);
    res = await fetch(`${API_BASE_URL}${path}`, {...init, headers});
  } catch {
    throw new ApiError("Backend unavailable. Check that the API server is running.", 0);
  }
  if (!res.ok) {
    if(res.status===401 && path!='/api/auth/login') {
      sessionStorage.removeItem('rca_token');window.dispatchEvent(new Event('rca-auth-expired'));
    }
    let message: string | null = null;
    let detail: unknown = null;
    try {
      detail = (await res.json())?.detail;
      message = readableDetail(detail);
    } catch {
      /* non-JSON body: fall back to the status message */
    }
    if (res.status >= 500 && res.status !== 501) message = STATUS_MESSAGES[500];
    throw new ApiError(message || STATUS_MESSAGES[res.status] || `Request failed (${res.status}).`, res.status, detail);
  }
  return (await res.json()) as T;
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}
