/** Shared API client: env-based base URL, parallel-ready fetches.
 *
 * Rules (R-07 + vercel-react-best-practices client subset):
 * - Base URL comes ONLY from VITE_API_BASE_URL (never hardcoded).
 * - Independent fetches run via Promise.all (see fetchSystemStatus).
 * - API errors (409/422/...) are presented verbatim — the UI shows
 *   ApiError.status/body as-is; all validation lives in the backend.
 */

export interface HealthPayload {
  status: string;
  service: string;
}

export interface ReadinessPayload {
  status: string;
  checks: {
    db: string;
    redis: string;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown) {
    super(`API ${status}: ${typeof body === "string" ? body : JSON.stringify(body)}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function getApiBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (base === undefined || base === "") {
    throw new Error("VITE_API_BASE_URL is not configured");
  }
  return base.replace(/\/+$/, "");
}

export async function fetchJson(path: string): Promise<unknown> {
  const response = await fetch(`${getApiBaseUrl()}${path}`);
  const text = await response.text();
  let body: unknown = text;
  if (text !== "") {
    try {
      body = JSON.parse(text) as unknown;
    } catch {
      body = text;
    }
  }
  if (!response.ok) {
    throw new ApiError(response.status, body);
  }
  return body;
}

export function fetchHealth(): Promise<HealthPayload> {
  return fetchJson("/health") as Promise<HealthPayload>;
}

export function fetchReady(): Promise<ReadinessPayload> {
  return fetchJson("/ready") as Promise<ReadinessPayload>;
}

export interface SystemStatus {
  health: HealthPayload | ApiError;
  ready: ReadinessPayload | ApiError;
}

function asSettled<T>(promise: Promise<T>): Promise<T | ApiError> {
  return promise.catch((error: unknown) =>
    error instanceof ApiError
      ? error
      : new ApiError(0, error instanceof Error ? error.message : String(error)),
  );
}

/** Fetch liveness + readiness independently and in parallel. */
export async function fetchSystemStatus(): Promise<SystemStatus> {
  const [health, ready] = await Promise.all([
    asSettled(fetchHealth()),
    asSettled(fetchReady()),
  ]);
  return { health, ready };
}

/** Render an API failure verbatim (no local reinterpretation). */
export function describeFailure(failure: ApiError): string {
  return failure.message;
}
