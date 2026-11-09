/**
 * C-17 status panel contract: three named rows with Badge + text (never colour
 * alone), verbatim API errors in mono and a polite loading status.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiStatus } from "./ApiStatus";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

let health: () => Response;
let ready: () => Response;

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  health = () => response({ status: "ok", service: "api" });
  ready = () =>
    response({ status: "ready", checks: { db: "up", redis: "up" } });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/health")) {
        return health();
      }
      if (url.endsWith("/ready")) {
        return ready();
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

function row(name: string): HTMLElement {
  return screen.getByRole("group", { name });
}

describe("ApiStatus", () => {
  it("muestra tres badges success cuando todo responde", async () => {
    render(<ApiStatus />);

    expect(await screen.findByText("Estado del sistema")).toBeTruthy();
    for (const name of ["API", "Base de datos", "Redis"]) {
      const badge = within(row(name)).getByText("Operativo");
      expect(badge.className).toContain("ds-badge--success");
    }
    expect(screen.queryByText(/Con error/)).toBeNull();
  });

  it("marca danger solo en API cuando health falla y muestra el error verbatim", async () => {
    health = () => response({ detail: "Sin conexión con la API" }, 503);
    render(<ApiStatus />);

    expect(await screen.findByText("Estado del sistema")).toBeTruthy();
    expect(
      within(row("API")).getByText("Con error").className,
    ).toContain("ds-badge--danger");
    expect(
      within(row("Base de datos")).getByText("Operativo").className,
    ).toContain("ds-badge--success");
    expect(
      within(row("Redis")).getByText("Operativo").className,
    ).toContain("ds-badge--success");

    const error = document.querySelector(".ds-status__error");
    expect(error?.textContent).toContain("503");
    expect(error?.textContent).toContain("Sin conexión con la API");
    expect(error?.className).toContain("ds-mono");
  });

  it("marca danger solo en Base de datos cuando db no está up", async () => {
    ready = () =>
      response({ status: "degraded", checks: { db: "down", redis: "up" } });
    render(<ApiStatus />);

    expect(await screen.findByText("Estado del sistema")).toBeTruthy();
    expect(
      within(row("API")).getByText("Operativo").className,
    ).toContain("ds-badge--success");
    expect(
      within(row("Base de datos")).getByText("Con error").className,
    ).toContain("ds-badge--danger");
    expect(
      within(row("Redis")).getByText("Operativo").className,
    ).toContain("ds-badge--success");
  });

  it("anuncia la carga en una región status", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    render(<ApiStatus />);

    const status = screen.getByRole("status");
    expect(status.textContent).toContain("Consultando estado del backend…");
    expect(status.getAttribute("aria-live")).toBe("polite");
  });
});
