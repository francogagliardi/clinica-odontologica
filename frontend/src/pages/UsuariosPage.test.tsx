import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { login, logout } from "../features/auth/session";
import { UsuariosPage } from "./UsuariosPage";

const ROLES = [
  { id: "r1", nombre: "administrador" },
  { id: "r2", nombre: "odontologo" },
  { id: "r3", nombre: "asistente" },
];

let usuarios: Array<Record<string, unknown>>;
let calls: Array<{ url: string; init?: RequestInit }>;
let listStatus: number;
let patchStatus: number;
let createStatus: number;
let loginRoles: string[];

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
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
      if (url.endsWith("/roles")) {
        return listStatus === 200
          ? response(ROLES)
          : response({ detail: "Permisos insuficientes" }, listStatus);
      }
      if (url.includes("/usuarios?")) {
        return listStatus === 200
          ? response(usuarios)
          : response({ detail: "Permisos insuficientes" }, listStatus);
      }
      if (url.endsWith("/usuarios") && (init?.method ?? "GET") === "GET") {
        return listStatus === 200
          ? response(usuarios)
          : response({ detail: "Permisos insuficientes" }, listStatus);
      }
      if (url.endsWith("/usuarios") && init?.method === "POST") {
        if (createStatus !== 201) {
          return response({ detail: "Error de validación del backend" }, createStatus);
        }
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        const creado = {
          id: `u-${usuarios.length + 1}`,
          nombre: String(body.nombre),
          email: String(body.email),
          is_active: true,
          roles: body.roles,
        };
        usuarios = [...usuarios, creado];
        return response(creado, 201);
      }
      if (url.includes("/roles") && init?.method === "PUT") {
        const uuid = url.split("/")[4];
        const body = JSON.parse(String(init.body)) as { roles: string[] };
        usuarios = usuarios.map((usuario) =>
          usuario.id === uuid ? { ...usuario, roles: body.roles } : usuario,
        );
        return response(usuarios.find((usuario) => usuario.id === uuid));
      }
      if (url.includes("/password") && init?.method === "POST") {
        return response(usuarios[0]);
      }
      if (init?.method === "PATCH") {
        if (patchStatus !== 200) {
          return response(
            { detail: "El sistema quedaría sin administrador activo" },
            patchStatus,
          );
        }
        const uuid = url.split("/")[4];
        const body = JSON.parse(String(init.body)) as { activo: boolean };
        usuarios = usuarios.map((usuario) =>
          usuario.id === uuid ? { ...usuario, is_active: body.activo } : usuario,
        );
        return response(usuarios.find((usuario) => usuario.id === uuid));
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
}

async function entrar(roles: string[] = ["administrador"]): Promise<void> {
  loginRoles = roles;
  await login("sesion@test", "clave");
}

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  usuarios = [
    {
      id: "u1",
      nombre: "Ana Demo",
      email: "ana@test",
      is_active: true,
      roles: ["odontologo"],
    },
  ];
  calls = [];
  listStatus = 200;
  patchStatus = 200;
  createStatus = 201;
  loginRoles = ["administrador"];
  logout();
  installFetch();
});

afterEach(() => {
  cleanup();
  logout();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("UsuariosPage", () => {
  it("pide login sin sesión", () => {
    render(<UsuariosPage />);
    expect(screen.getByRole("heading", { name: /backoffice/i })).toBeTruthy();
  });

  it("lista nombre, email, estado y roles", async () => {
    await entrar();
    render(<UsuariosPage />);
    expect(await screen.findByText("Ana Demo")).toBeTruthy();
    expect(screen.getByText("ana@test")).toBeTruthy();
    expect(screen.getByText("activo")).toBeTruthy();
    expect(screen.getAllByText("odontologo").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Usuarios" })).toBeTruthy();
  });

  it("crea un usuario con los roles elegidos", async () => {
    await entrar();
    render(<UsuariosPage />);
    await screen.findByText("Ana Demo");

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Nuevo Demo" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "nuevo@test" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "clave-larga-123" },
    });
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Rol odontologo" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Crear usuario" }));

    await waitFor(() => {
      const alta = calls.find(
        (llamada) =>
          llamada.url.endsWith("/usuarios") &&
          llamada.init?.method === "POST",
      );
      expect(alta).toBeTruthy();
      expect(alta?.init?.body).toBe(
        JSON.stringify({
          nombre: "Nuevo Demo",
          email: "nuevo@test",
          password: "clave-larga-123",
          roles: ["odontologo"],
        }),
      );
    });
    expect(await screen.findByText("nuevo@test")).toBeTruthy();
  });

  it("asigna roles a una fila con PUT", async () => {
    await entrar();
    render(<UsuariosPage />);
    await screen.findByText("Ana Demo");

    fireEvent.click(
      screen.getByRole("checkbox", { name: "ana@test asistente" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Guardar roles" }));

    await waitFor(() => {
      const put = calls.find(
        (llamada) => llamada.init?.method === "PUT",
      );
      expect(put?.url).toContain("/usuarios/u1/roles");
      const body = JSON.parse(String(put?.init?.body)) as {
        roles: string[];
      };
      expect(body.roles).toContain("odontologo");
      expect(body.roles).toContain("asistente");
    });
    const fila = (await screen.findByText("ana@test")).closest("tr");
    expect(fila).not.toBeNull();
    expect(
      within(fila as HTMLElement).getAllByText(/asistente/).length,
    ).toBeGreaterThan(0);
  });

  it("desactiva una cuenta con PATCH y refresca el estado", async () => {
    await entrar();
    render(<UsuariosPage />);
    await screen.findByText("Ana Demo");

    fireEvent.click(screen.getByRole("button", { name: "Desactivar" }));

    await waitFor(() => {
      const patch = calls.find(
        (llamada) => llamada.init?.method === "PATCH",
      );
      expect(patch?.url).toContain("/usuarios/u1");
      expect(patch?.init?.body).toBe(JSON.stringify({ activo: false }));
    });
    expect(await screen.findByText("inactivo")).toBeTruthy();
  });

  it("muestra el 409 del último administrador verbatim y no cambia la fila", async () => {
    patchStatus = 409;
    await entrar();
    render(<UsuariosPage />);
    await screen.findByText("Ana Demo");

    fireEvent.click(screen.getByRole("button", { name: "Desactivar" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("409");
    expect(alerta.textContent).toContain(
      "El sistema quedaría sin administrador activo",
    );
    expect(screen.getByText("activo")).toBeTruthy();
  });

  it("muestra el 403 de un rol sin permisos y no habilita escritura", async () => {
    listStatus = 403;
    await entrar(["recepcionista"]);
    render(<UsuariosPage />);

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("403");
    expect(alerta.textContent).toContain("Permisos insuficientes");
    expect(
      screen.queryByRole("button", { name: "Crear usuario" }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: "Desactivar" })).toBeNull();
  });

  it("no valida localmente: envía el alta vacía y muestra el 422 de la API", async () => {
    createStatus = 422;
    await entrar();
    render(<UsuariosPage />);
    await screen.findByText("Ana Demo");

    fireEvent.click(screen.getByRole("button", { name: "Crear usuario" }));

    await waitFor(() => {
      expect(
        calls.some(
          (llamada) =>
            llamada.url.endsWith("/usuarios") &&
            llamada.init?.method === "POST",
        ),
      ).toBe(true);
    });
    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("422");
    expect(alerta.textContent).toContain("Error de validación del backend");
  });

  it("agrupa el alta en una Card y la tabla en una región desplazable", async () => {
    await entrar();
    render(<UsuariosPage />);
    await screen.findByText("Ana Demo");

    expect(
      screen.getByRole("region", { name: "Nuevo usuario" }),
    ).toBeTruthy();
    const tabla = screen.getByRole("region", { name: "Usuarios" });
    expect(within(tabla).getByRole("table")).toBeTruthy();

    const activo = within(tabla).getByText("activo", {
      selector: ".ds-badge",
    });
    expect(activo.className).toContain("ds-badge--success");

    const fila = screen.getByText("ana@test").closest("tr");
    expect(fila).not.toBeNull();
    expect(
      within(fila as HTMLElement).getByRole("group", {
        name: /acciones/i,
      }),
    ).toBeTruthy();
  });

  it("muestra un vacío explicativo cuando no hay usuarios", async () => {
    usuarios = [];
    await entrar();
    render(<UsuariosPage />);

    expect(
      await screen.findByRole("heading", {
        level: 2,
        name: /sin usuarios/i,
      }),
    ).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("oculta la escritura si la API responde 403 aunque el rol sea admin", async () => {
    listStatus = 403;
    await entrar(["administrador"]);
    render(<UsuariosPage />);

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("403");
    expect(
      screen.queryByRole("button", { name: "Crear usuario" }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: "Guardar roles" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Desactivar" })).toBeNull();
  });
});
