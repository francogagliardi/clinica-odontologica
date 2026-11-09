/**
 * C-17 auth screen contract: the backoffice login is a centered Card built from
 * the shared components, with the exact labels and accessible error relation.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "./LoginForm";

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
    vi.fn(async () => response({ detail: "Credenciales inválidas" }, 401)),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("LoginForm", () => {
  it("se renderiza dentro del layout de autenticación con una Card", () => {
    render(<LoginForm />);

    const main = document.querySelector("main.ds-auth");
    expect(main).not.toBeNull();
    const panel = main?.querySelector(".ds-auth__panel");
    expect(panel).not.toBeNull();
    expect(panel?.querySelector(".ds-card")).not.toBeNull();
    expect(
      screen.getByRole("heading", { level: 1, name: "Backoffice" }),
    ).toBeTruthy();
    expect(screen.getByLabelText("Email")).toBeTruthy();
    expect(screen.getByLabelText("Contraseña")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ingresar" })).toBeTruthy();
    expect(document.querySelector(".ds-field__control")).not.toBeNull();
  });

  it("muestra el error verbatim en un ErrorBanner y lo asocia a los campos", async () => {
    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "admin@clinica.test" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "incorrecta" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta.className).toContain("ds-error-banner");
    expect(alerta.textContent).toContain("401");
    expect(alerta.textContent).toContain("Credenciales inválidas");

    await waitFor(() => {
      const email = screen.getByLabelText("Email");
      expect(email.getAttribute("aria-invalid")).toBe("true");
      const describedBy = email.getAttribute("aria-describedby");
      expect(document.getElementById(describedBy ?? "")).toBe(alerta);
    });
  });
});
