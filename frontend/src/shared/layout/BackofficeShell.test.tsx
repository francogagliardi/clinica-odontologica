/**
 * C-17 backoffice shell contract (design.md D5, D8).
 * The session is real (in memory) so logout and identity are exercised end to end.
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getSession, login, logout } from "../../features/auth/session";
import { BackofficeShell } from "./BackofficeShell";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      response({
        access_token: "jwt-shell",
        token_type: "bearer",
        expires_in: 1800,
        usuario: {
          id: "u-1",
          nombre: "Ana Pérez",
          email: "ana@clinica.test",
          roles: ["administrador"],
        },
      }),
    ),
  );
});

afterEach(() => {
  logout();
  cleanup();
  vi.unstubAllGlobals();
});

async function iniciarSesion(): Promise<void> {
  await login("ana@clinica.test", "secreto");
}

describe("BackofficeShell con sesión", () => {
  it("muestra el rail con los cuatro módulos y marca la ruta activa", async () => {
    await iniciarSesion();
    render(
      <BackofficeShell pathname="/agenda">
        <p>Contenido</p>
      </BackofficeShell>,
    );

    const nav = screen.getByRole("navigation", {
      name: "Navegación principal",
    });
    expect(
      within(nav).getByRole("link", { name: "Agenda" }).getAttribute(
        "aria-current",
      ),
    ).toBe("page");
    for (const modulo of ["Reportes", "Usuarios", "Auditoría"]) {
      expect(
        within(nav).getByRole("link", { name: modulo }).getAttribute(
          "aria-current",
        ),
      ).toBeNull();
    }
  });

  it("marca Reportes cuando la ruta es /reportes", async () => {
    await iniciarSesion();
    render(
      <BackofficeShell pathname="/reportes">
        <p>Contenido</p>
      </BackofficeShell>,
    );

    const nav = screen.getByRole("navigation", {
      name: "Navegación principal",
    });
    expect(
      within(nav).getByRole("link", { name: "Reportes" }).getAttribute(
        "aria-current",
      ),
    ).toBe("page");
  });

  it("muestra la identidad de la sesión", async () => {
    await iniciarSesion();
    render(
      <BackofficeShell pathname="/usuarios">
        <p>Contenido</p>
      </BackofficeShell>,
    );

    expect(screen.getByText("Ana Pérez")).toBeTruthy();
    expect(screen.getByText("ana@clinica.test")).toBeTruthy();
  });

  it("Salir descarta la sesión en memoria", async () => {
    await iniciarSesion();
    render(
      <BackofficeShell pathname="/auditoria">
        <p>Contenido</p>
      </BackofficeShell>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Salir" }));
    expect(getSession()).toBeNull();
    expect(screen.queryByRole("button", { name: "Salir" })).toBeNull();
  });

  it("el skip link es el primer enlace y apunta al contenido", async () => {
    await iniciarSesion();
    render(
      <BackofficeShell pathname="/agenda">
        <p>Contenido</p>
      </BackofficeShell>,
    );

    const skip = screen.getByRole("link", { name: "Saltar al contenido" });
    expect(skip.getAttribute("href")).toBe("#contenido");
    expect(screen.getAllByRole("link")[0]).toBe(skip);
    expect(
      document.getElementById("contenido")?.getAttribute("tabindex"),
    ).toBe("-1");
  });

  it("el menú móvil expone aria-expanded y aria-controls y se cierra al navegar", async () => {
    await iniciarSesion();
    render(
      <BackofficeShell pathname="/agenda">
        <p>Contenido</p>
      </BackofficeShell>,
    );

    const nav = screen.getByRole("navigation", {
      name: "Navegación principal",
    });
    const menu = screen.getByRole("button", { name: "Menú" });
    expect(menu.getAttribute("aria-expanded")).toBe("false");
    expect(menu.getAttribute("aria-controls")).toBe(nav.id);

    fireEvent.click(menu);
    expect(menu.getAttribute("aria-expanded")).toBe("true");

    const reportes = within(nav).getByRole("link", { name: "Reportes" });
    reportes.addEventListener("click", (event) => event.preventDefault(), {
      once: true,
    });
    fireEvent.click(reportes);
    expect(menu.getAttribute("aria-expanded")).toBe("false");
  });
});

describe("BackofficeShell sin sesión", () => {
  it("no expone enlaces protegidos ni Salir", () => {
    render(
      <BackofficeShell pathname="/reportes">
        <p>Acceso</p>
      </BackofficeShell>,
    );

    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.queryByRole("link", { name: "Agenda" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Reportes" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Salir" })).toBeNull();
    expect(screen.getByRole("link", { name: "Clínica Odontológica" })).toBeTruthy();
  });
});
