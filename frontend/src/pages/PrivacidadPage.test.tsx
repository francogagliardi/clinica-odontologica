import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
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
  window.history.replaceState(null, "", "/privacidad");
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

  it("presenta lectura larga, metadatos destacados y hash monoespaciado", async () => {
    render(<PrivacidadPage />);
    await screen.findByText(/v1-2026-11/);

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const articulo = screen.getByRole("article", {
      name: "Política de privacidad",
    });
    expect(
      within(articulo).getByText(/Texto público de privacidad/),
    ).toBeTruthy();
    expect(within(articulo).getByText("Versión")).toBeTruthy();
    expect(within(articulo).getByText("Vigente desde")).toBeTruthy();
    const hash = within(articulo).getByText(new RegExp("b".repeat(64)));
    expect(hash.className).toContain("ds-mono");
  });

  it("usa una columna de lectura centrada y un botón Volver real", async () => {
    window.history.replaceState({ appIndex: 1 }, "", "/privacidad");
    const back = vi
      .spyOn(window.history, "back")
      .mockImplementation(() => undefined);
    render(<PrivacidadPage />);
    await screen.findByText(/v1-2026-11/);

    expect(document.querySelector("main.ds-reading")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Volver" }));
    expect(back).toHaveBeenCalledTimes(1);
    back.mockRestore();
  });

  it("el CTA Reservar turno usa el estilo de botón del sistema", async () => {
    render(<PrivacidadPage />);
    await screen.findByText(/v1-2026-11/);

    const cta = screen.getByRole("link", { name: "Reservar turno" });
    expect(cta.getAttribute("href")).toBe("/reservar");
    expect(cta.className).toContain("ds-button");
  });
});
