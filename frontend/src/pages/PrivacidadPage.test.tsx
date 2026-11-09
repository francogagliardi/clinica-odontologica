import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PrivacidadPage } from "./PrivacidadPage";

const POLITICA = {
  version: "v1-2026-11",
  vigente_desde: "2026-11-01",
  texto: "Texto público de privacidad con alcance informativo.",
  hash: "b".repeat(64),
  alcance_legal_validado: false,
};

let status = 200;

function response(body: unknown, code = 200): Response {
  return {
    ok: code >= 200 && code < 300,
    status: code,
    text: async () => JSON.stringify(body),
  } as Response;
}

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  status = 200;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/privacidad")) {
        return status === 200
          ? response(POLITICA)
          : response({ detail: "Política no disponible" }, status);
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("PrivacidadPage", () => {
  it("muestra versión, fecha, texto, hash y vuelta a la reserva", async () => {
    render(<PrivacidadPage />);
    expect(await screen.findByText(/v1-2026-11/)).toBeTruthy();
    expect(screen.getByText(/2026-11-01/)).toBeTruthy();
    expect(screen.getByText(/Texto público de privacidad/)).toBeTruthy();
    expect(screen.getByText(new RegExp("b".repeat(64)))).toBeTruthy();
    const enlace = screen.getByRole("link", { name: /reservar/i });
    expect(enlace.getAttribute("href")).toBe("/reservar");
    // Read-only public page: no administration controls.
    expect(screen.queryByRole("button", { name: /crear/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /guardar/i })).toBeNull();
  });

  it("muestra el error de la API verbatim", async () => {
    status = 404;
    render(<PrivacidadPage />);
    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("404");
    expect(alerta.textContent).toContain("Política no disponible");
    expect(screen.queryByText(/Texto público de privacidad/)).toBeNull();
  });
});
