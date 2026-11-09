import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/api/client";
import { fetchPrivacidad } from "./api";

const calls: Array<string> = [];
let notFound = false;

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  calls.length = 0;
  notFound = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      if (url.includes("/privacidad")) {
        if (notFound) {
          return response({ detail: "Versión no encontrada" }, 404);
        }
        return response({
          version: "v1-2026-11",
          vigente_desde: "2026-11-01",
          texto: "Texto público de privacidad.",
          hash: "a".repeat(64),
          alcance_legal_validado: false,
        });
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("privacidad api", () => {
  it("lee la política vigente sin sesión", async () => {
    const politica = await fetchPrivacidad();
    expect(calls[calls.length - 1]?.endsWith("/privacidad")).toBe(true);
    expect(politica.version).toBe("v1-2026-11");
    expect(politica.alcance_legal_validado).toBe(false);
  });

  it("lee una versión explícita", async () => {
    await fetchPrivacidad("v1-2026-11");
    expect(
      calls[calls.length - 1]?.endsWith("/privacidad/v1-2026-11"),
    ).toBe(true);
  });

  it("propaga el 404 sin inventar texto", async () => {
    notFound = true;
    await expect(fetchPrivacidad("v0")).rejects.toBeInstanceOf(ApiError);
    await expect(fetchPrivacidad("v0")).rejects.toMatchObject({
      status: 404,
    });
  });
});
