import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgendaPage } from "./AgendaPage";
import { login, logout } from "../features/auth/session";

const PROFESIONALES = [
  {
    id: "prof-1",
    usuario_id: "u-odonto",
    matricula: "MP-1",
    especialidades: ["general"],
  },
  {
    id: "prof-2",
    usuario_id: "u-otro",
    matricula: "MP-2",
    especialidades: ["general"],
  },
];

const TURNOS = [
  {
    id: "t1",
    paciente_id: "p1",
    profesional_id: "prof-1",
    sillon_id: "s1",
    prestacion_id: "pr1",
    inicio: "2026-11-09T09:00:00-03:00",
    fin: "2026-11-09T09:30:00-03:00",
    estado: "reservado",
    origen: "recepcion",
    es_sobreturno: false,
    color_sobreturno: null,
  },
  {
    id: "t2",
    paciente_id: "p2",
    profesional_id: "prof-1",
    sillon_id: "s1",
    prestacion_id: "pr1",
    inicio: "2026-11-09T09:30:00-03:00",
    fin: "2026-11-09T10:00:00-03:00",
    estado: "confirmado",
    origen: "online",
    es_sobreturno: true,
    color_sobreturno: "#F97316",
  },
  {
    id: "t3",
    paciente_id: "p3",
    profesional_id: "prof-2",
    sillon_id: "s2",
    prestacion_id: null,
    inicio: "2026-11-09T10:00:00-03:00",
    fin: "2026-11-09T11:00:00-03:00",
    estado: "cancelado",
    origen: "recepcion",
    es_sobreturno: false,
    color_sobreturno: null,
  },
];

const BLOQUEOS = [
  {
    id: "b1",
    profesional_id: "prof-1",
    sillon_id: null,
    desde: "2026-11-09T11:00:00-03:00",
    hasta: "2026-11-09T12:00:00-03:00",
    motivo: "Licencia",
  },
];

const calls: Array<{ url: string; init?: RequestInit }> = [];
let patchStatus = 200;

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
            id: currentUser.id,
            nombre: "Usuario",
            email: "u@test",
            roles: currentRoles,
          },
        });
      }
      if (url.endsWith("/profesionales")) return response(PROFESIONALES);
      if (url.endsWith("/sillones")) {
        return response([
          { id: "s1", nombre: "Sillón 1" },
          { id: "s2", nombre: "Sillón 2" },
        ]);
      }
      if (url.includes("/turnos?") && !url.includes("reprogramar")) {
        return response(TURNOS);
      }
      if (url.includes("/bloqueos?")) return response(BLOQUEOS);
      if (url.includes("/reprogramar")) {
        return patchStatus === 200
          ? response(TURNOS[0])
          : response({ detail: "El horario se solapa" }, patchStatus);
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
}

let currentUser = { id: "u-recep" };
let currentRoles = ["recepcionista"];

async function entrar(): Promise<void> {
  await login("u@test", "clave");
}

function dataTransfer(): DataTransfer {
  const store = new Map<string, string>();
  return {
    setData: (key: string, value: string) => store.set(key, value),
    getData: (key: string) => store.get(key) ?? "",
  } as unknown as DataTransfer;
}

async function abrirDia(): Promise<void> {
  render(<AgendaPage />);
  await waitFor(() => expect(screen.getByLabelText(/Fecha/)).toBeTruthy());
  fireEvent.change(screen.getByLabelText(/Fecha/), {
    target: { value: "2026-11-09" },
  });
  await waitFor(() =>
    expect(screen.getByLabelText(/Turno 09:00 reservado/)).toBeTruthy(),
  );
}

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  calls.length = 0;
  patchStatus = 200;
  currentUser = { id: "u-recep" };
  currentRoles = ["recepcionista"];
  logout();
  installFetch();
});

afterEach(() => {
  cleanup();
  logout();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("AgendaPage", () => {
  it("muestra el login sin sesión", () => {
    render(<AgendaPage />);
    expect(screen.getByRole("heading", { name: /backoffice/i })).toBeTruthy();
  });

  it("renderiza día con colores, bloqueo y sobreturno", async () => {
    await entrar();
    await abrirDia();

    expect(screen.getByLabelText(/Turno 09:30 confirmado/)).toBeTruthy();
    expect(screen.getByText("Sobreturno")).toBeTruthy();
    expect(screen.getByLabelText(/Bloqueo Licencia/)).toBeTruthy();
    expect(document.querySelector(".estado-cancelado")).toBeTruthy();
  });

  it("reprograma al soltar en otra hora", async () => {
    await entrar();
    await abrirDia();
    const dt = dataTransfer();
    fireEvent.dragStart(screen.getByLabelText(/Turno 09:00 reservado/), {
      dataTransfer: dt,
    });
    const fila = document.querySelector('[data-hora="10"]');
    expect(fila).toBeTruthy();
    fireEvent.drop(fila as Element, { dataTransfer: dt });

    await waitFor(() => expect(calls.some((c) => c.url.includes("/reprogramar"))).toBe(true));
    const patch = calls.find((c) => c.url.includes("/reprogramar"));
    expect(patch?.init?.method).toBe("PATCH");
    expect(patch?.init?.body).toBe(
      JSON.stringify({ inicio: "2026-11-09T10:00:00-03:00" }),
    );
  });

  it("muestra el 409 de la API y no mueve el turno", async () => {
    patchStatus = 409;
    await entrar();
    await abrirDia();
    const dt = dataTransfer();
    fireEvent.dragStart(screen.getByLabelText(/Turno 09:00 reservado/), {
      dataTransfer: dt,
    });
    fireEvent.drop(document.querySelector('[data-hora="10"]') as Element, {
      dataTransfer: dt,
    });

    expect((await screen.findByRole("alert")).textContent).toMatch(/409/);
    expect(document.querySelector(".estado-reservado")).toBeTruthy();
  });

  it("el odontólogo solo arrastra sus turnos", async () => {
    currentUser = { id: "u-odonto" };
    currentRoles = ["odontologo"];
    await entrar();
    await abrirDia();

    const propio = screen.getByLabelText(/Turno 09:00 reservado/);
    const ajeno = screen.getByLabelText(/Turno 10:00 cancelado/);
    expect(propio.getAttribute("draggable")).toBe("true");
    expect(ajeno.getAttribute("draggable")).toBe("false");
  });

  it("asistente y auditor quedan en lectura", async () => {
    currentRoles = ["asistente"];
    await entrar();
    await abrirDia();

    expect(
      screen.getByLabelText(/Turno 09:00 reservado/).getAttribute("draggable"),
    ).toBe("false");
  });

  it("cambia a semana y mes", async () => {
    await entrar();
    await abrirDia();
    fireEvent.change(screen.getByLabelText(/Vista/), {
      target: { value: "semana" },
    });
    expect(document.querySelector(".agenda-semana")).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Vista/), {
      target: { value: "mes" },
    });
    expect(document.querySelector(".agenda-mes")).toBeTruthy();
  });
});
