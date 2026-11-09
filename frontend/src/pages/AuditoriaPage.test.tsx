import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { login, logout } from "../features/auth/session";
import { AuditoriaPage } from "./AuditoriaPage";

const FILA = {
  id: "a1",
  usuario_id: "u1",
  usuario_email: "auditor@test",
  accion: "usuario.crear",
  entidad: "usuario",
  entidad_id: "u2",
  ip: "127.0.0.1",
  dispositivo: "vitest",
  timestamp: "2026-11-05T12:00:00-03:00",
};

const FILA_PAGINA_2 = {
  ...FILA,
  id: "a2",
  accion: "usuario.roles",
  entidad_id: "u3",
};

let calls: Array<{ url: string; init?: RequestInit }>;
let status: number;
let loginRoles: string[];

function response(body: unknown, code = 200): Response {
  return {
    ok: code >= 200 && code < 300,
    status: code,
    text: async () => JSON.stringify(body),
  } as Response;
}

function installFetch(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, init });
      if (url.endsWith("/usuarios/login")) {
        return response({
          access_token: "jwt-1",
          token_type: "bearer",
          expires_in: 1800,
          usuario: {
            id: "sesion",
            nombre: "Sesión",
            email: "sesion@test",
            roles: loginRoles,
          },
        });
      }
      if (url.includes("/auditoria")) {
        if (status !== 200) {
          return response({ detail: "Permisos insuficientes" }, status);
        }
        const params = new URL(url).searchParams;
        const offset = Number(params.get("offset") ?? "0");
        const limite = Number(params.get("limite") ?? "100");
        return response({
          total: 120,
          limite,
          offset,
          filas: offset === 0 ? [FILA] : [FILA_PAGINA_2],
        });
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
}

async function entrar(roles: string[] = ["auditor"]): Promise<void> {
  loginRoles = roles;
  await login("sesion@test", "clave");
}

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  calls = [];
  status = 200;
  loginRoles = ["auditor"];
  logout();
  installFetch();
});

afterEach(() => {
  cleanup();
  logout();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

function llamadasAuditoria(): string[] {
  return calls
    .map((llamada) => String(llamada.url))
    .filter((url) => url.includes("/auditoria"));
}

describe("AuditoriaPage", () => {
  it("sin sesión pide login y no consulta el historial", () => {
    render(<AuditoriaPage />);
    expect(screen.getByRole("heading", { name: /backoffice/i })).toBeTruthy();
    expect(llamadasAuditoria()).toHaveLength(0);
  });

  it("muestra la tabla y aplica filtros de acción y fecha", async () => {
    await entrar();
    render(<AuditoriaPage />);

    expect(await screen.findByText("usuario.crear")).toBeTruthy();
    expect(screen.getByText("auditor@test")).toBeTruthy();
    expect(screen.getByText("Total: 120")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Acción"), {
      target: { value: "usuario.roles" },
    });
    fireEvent.change(screen.getByLabelText("Desde"), {
      target: { value: "2026-11-05" },
    });
    fireEvent.change(screen.getByLabelText("Hasta"), {
      target: { value: "2026-11-06" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));

    await waitFor(() => {
      expect(
        llamadasAuditoria().some(
          (url) =>
            url.includes("accion=usuario.roles") &&
            url.includes("desde=2026-11-05") &&
            url.includes("hasta=2026-11-06"),
        ),
      ).toBe(true);
    });
  });

  it("pagina por offset sin controles de escritura", async () => {
    await entrar();
    render(<AuditoriaPage />);
    await screen.findByText("usuario.crear");

    for (const nombre of ["Crear", "Guardar", "Eliminar", "Editar"]) {
      expect(screen.queryByRole("button", { name: nombre })).toBeNull();
    }

    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => {
      expect(
        llamadasAuditoria().some((url) => url.includes("offset=100")),
      ).toBe(true);
    });
    expect(await screen.findByText("usuario.roles")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Anterior" }));
    await waitFor(() => {
      expect(
        llamadasAuditoria().some((url) => url.includes("offset=0")),
      ).toBe(true);
    });
  });

  it("muestra el 403 de un odontólogo sin habilitar filtros", async () => {
    status = 403;
    await entrar(["odontologo"]);
    render(<AuditoriaPage />);

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("403");
    expect(alerta.textContent).toContain("Permisos insuficientes");
    expect(screen.queryByRole("button", { name: "Buscar" })).toBeNull();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
