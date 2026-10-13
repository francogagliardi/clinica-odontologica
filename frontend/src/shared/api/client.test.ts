import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchJson, getApiBaseUrl } from "./client";

function mockFetchOnce(status: number, body: unknown): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("API client base URL", () => {
  it("uses VITE_API_BASE_URL for calls", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api-a:8000");
    expect(getApiBaseUrl()).toBe("http://api-a:8000");
    mockFetchOnce(200, { status: "ok", service: "api" });
    await fetchJson("/health");
    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
      "http://api-a:8000/health",
    );
  });

  it("uses the new base after the env changes without code edits", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api-b:9000");
    mockFetchOnce(200, { status: "ok", service: "api" });
    await fetchJson("/health");
    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe(
      "http://api-b:9000/health",
    );
  });
});

describe("API error presentation", () => {
  it("surfaces a 409 exactly as the API returned it", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api:8000");
    const apiBody = { detail: "slot already taken" };
    mockFetchOnce(409, apiBody);
    const failure = await fetchJson("/turnos").then(
      () => null,
      (error: unknown) => error,
    );
    expect(failure).toBeInstanceOf(ApiError);
    const apiError = failure as ApiError;
    expect(apiError.status).toBe(409);
    expect(apiError.body).toEqual(apiBody);
    expect(apiError.message).toContain("slot already taken");
  });

  it("surfaces a 422 exactly as the API returned it", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://api:8000");
    const apiBody = { detail: [{ loc: ["dni"], msg: "invalid" }] };
    mockFetchOnce(422, apiBody);
    const failure = await fetchJson("/pacientes").then(
      () => null,
      (error: unknown) => error,
    );
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(422);
    expect((failure as ApiError).body).toEqual(apiBody);
  });
});
