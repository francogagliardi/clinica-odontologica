/**
 * C-17 home hero contract: centered vertical composition with eyebrow, title,
 * description, the two entries and the backend status panel.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "./HomePage";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/health")) {
        return response({ status: "ok", service: "api" });
      }
      if (url.endsWith("/ready")) {
        return response({
          status: "ready",
          checks: { db: "up", redis: "up" },
        });
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

describe("HomePage", () => {
  it("compone el hero con eyebrow, h1, descripción y las dos entradas", async () => {
    render(<HomePage />);

    expect(document.querySelector("main.ds-home")).not.toBeNull();
    expect(document.querySelector(".ds-home__inner")).not.toBeNull();
    expect(screen.getByText("Turnos online")).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /clínica odontológica/i,
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("navigation", { name: "Accesos de la portada" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Reservar turno" }).getAttribute("href"),
    ).toBe("/reservar");
    expect(
      screen
        .getByRole("link", { name: "Ingresar al backoffice" })
        .getAttribute("href"),
    ).toBe("/agenda");

    expect(await screen.findByText("Estado del sistema")).toBeTruthy();
    expect(screen.getAllByText("Operativo")).toHaveLength(3);
  });
});
