import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GestionTurnoPage } from "./GestionTurnoPage";
import { ReservaPage } from "./ReservaPage";

const CATALOGO = {
  slug: "demo",
  nombre: "Consultorio Demo",
  profesionales: [{ id: "prof-1", matricula: "MP-1", especialidades: ["general"] }],
  prestaciones: [
    {
      id: "prest-1",
      codigo: "CONS",
      nombre: "Consulta odontológica",
      duracion_min: 30,
      precio_base: "12000.00",
      especialidad: "general",
      requiere_sena: false,
      monto_sena: null,
    },
  ],
  plazo_cancelacion_horas: 24,
  politica_cancelacion: "Podés cancelar hasta 24 horas antes.",
  politica_sena: "La seña se descuenta del total.",
  moneda: "ARS",
};

const SLOTS = [
  { inicio: "2026-11-09T09:00:00-03:00", fin: "2026-11-09T09:30:00-03:00" },
];

const RESERVA = {
  turno_id: "turno-1",
  inicio: SLOTS[0].inicio,
  fin: SLOTS[0].fin,
  estado: "reservado",
  profesional: CATALOGO.profesionales[0],
  prestacion: CATALOGO.prestaciones[0],
  sena: { requiere: false, monto: null, estado: "no_requiere" },
  gestion_url: "http://127.0.0.1:8080/reservar/gestion/token-1",
  whatsapp_confirmacion: "encolada",
  plazo_cancelacion_horas: 24,
  politica_sena: "La seña se descuenta del total.",
};

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

function mockFetch(
  handlers: Array<(url: string, init?: RequestInit) => Response | undefined>,
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    for (const handler of handlers) {
      const response = handler(url, init);
      if (response !== undefined) return response;
    }
    throw new Error(`Sin mock para ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("ReservaPage", () => {
  it("muestra el catálogo y los slots reales", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/demo") ? jsonResponse(CATALOGO) : undefined,
      (url) =>
        url.includes("/reservar/demo/disponibilidad")
          ? jsonResponse(SLOTS)
          : undefined,
    ]);
    render(<ReservaPage />);

    expect(await screen.findByText(/Consultorio Demo/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Profesional/), {
      target: { value: "prof-1" },
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "09:00" })).toBeTruthy();
    });
  });

  it("muestra el enlace de gestión tras reservar", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/demo") ? jsonResponse(CATALOGO) : undefined,
      (url) =>
        url.includes("/reservar/demo/disponibilidad")
          ? jsonResponse(SLOTS)
          : undefined,
      (url, init) =>
        url.endsWith("/reservar/demo/turnos") && init?.method === "POST"
          ? jsonResponse(RESERVA, 201)
          : undefined,
    ]);
    render(<ReservaPage />);

    fireEvent.change(await screen.findByLabelText(/Profesional/), {
      target: { value: "prof-1" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "09:00" }));
    fireEvent.change(screen.getByLabelText(/Nombre/), { target: { value: "Ana" } });
    fireEvent.change(screen.getByLabelText(/Apellido/), { target: { value: "Demo" } });
    fireEvent.change(screen.getByLabelText(/DNI/), { target: { value: "30111222" } });
    fireEvent.change(screen.getByLabelText(/Teléfono/), {
      target: { value: "11 5555-1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reservar" }));

    expect(await screen.findByText(/Turno reservado/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Gestionar mi turno/ })).toBeTruthy();
  });

  it("enlaza la política de privacidad sin checkbox ni bloqueo", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/demo") ? jsonResponse(CATALOGO) : undefined,
      (url) =>
        url.includes("/reservar/demo/disponibilidad")
          ? jsonResponse(SLOTS)
          : undefined,
    ]);
    render(<ReservaPage />);
    await screen.findByText(/Consultorio Demo/);

    const enlace = screen.getByRole("link", { name: /privacidad/i });
    expect(enlace.getAttribute("href")).toBe("/privacidad");
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByText(/acepto/i)).toBeNull();
    // The reservation form is still available without any acceptance step.
    expect(screen.getByRole("button", { name: "Reservar" })).toBeTruthy();
  });

  it("muestra el error de la API tal cual", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/demo") ? jsonResponse(CATALOGO) : undefined,
      (url) =>
        url.includes("/reservar/demo/disponibilidad")
          ? jsonResponse(SLOTS)
          : undefined,
      (url, init) =>
        url.endsWith("/reservar/demo/turnos") && init?.method === "POST"
          ? jsonResponse({ detail: "El horario se solapa" }, 409)
          : undefined,
    ]);
    render(<ReservaPage />);

    fireEvent.change(await screen.findByLabelText(/Profesional/), {
      target: { value: "prof-1" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "09:00" }));
    fireEvent.change(screen.getByLabelText(/Nombre/), { target: { value: "Ana" } });
    fireEvent.change(screen.getByLabelText(/Apellido/), { target: { value: "Demo" } });
    fireEvent.change(screen.getByLabelText(/DNI/), { target: { value: "30111222" } });
    fireEvent.change(screen.getByLabelText(/Teléfono/), {
      target: { value: "11 5555-1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reservar" }));

    expect((await screen.findByRole("alert")).textContent).toMatch(/409/);
  });

  it("presenta jerarquía, campos etiquetados y una grilla de huecos seleccionable", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/demo") ? jsonResponse(CATALOGO) : undefined,
      (url) =>
        url.includes("/reservar/demo/disponibilidad")
          ? jsonResponse(SLOTS)
          : undefined,
    ]);
    render(<ReservaPage />);

    await screen.findByText(/Consultorio Demo/);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(
      screen.getByRole("heading", { level: 2, name: "Horarios" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("region", { name: "Horarios disponibles" }),
    ).toBeTruthy();
    for (const etiqueta of [
      "Profesional",
      "Prestación",
      "Fecha",
      "Nombre",
      "Apellido",
      "DNI",
      "Teléfono WhatsApp",
    ]) {
      expect(screen.getByLabelText(etiqueta)).toBeTruthy();
    }

    fireEvent.change(screen.getByLabelText("Profesional"), {
      target: { value: "prof-1" },
    });
    const grilla = await screen.findByRole("list", {
      name: "Horarios disponibles",
    });
    const hueco = within(grilla).getByRole("button", { name: "09:00" });
    expect(hueco.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(hueco);
    expect(hueco.getAttribute("aria-pressed")).toBe("true");
  });

  it("muestra un estado vacío cuando no hay horarios para la fecha", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/demo") ? jsonResponse(CATALOGO) : undefined,
      (url) =>
        url.includes("/reservar/demo/disponibilidad")
          ? jsonResponse([])
          : undefined,
    ]);
    render(<ReservaPage />);

    fireEvent.change(await screen.findByLabelText("Profesional"), {
      target: { value: "prof-1" },
    });

    expect(
      await screen.findByRole("heading", {
        level: 2,
        name: /no hay horarios disponibles/i,
      }),
    ).toBeTruthy();
    expect(screen.getByText(/probá con otra fecha/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "09:00" })).toBeNull();
  });

  it("conserva el 409 verbatim y el formulario tras el conflicto", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/demo") ? jsonResponse(CATALOGO) : undefined,
      (url) =>
        url.includes("/reservar/demo/disponibilidad")
          ? jsonResponse(SLOTS)
          : undefined,
      (url, init) =>
        url.endsWith("/reservar/demo/turnos") && init?.method === "POST"
          ? jsonResponse({ detail: "El horario se solapa" }, 409)
          : undefined,
    ]);
    render(<ReservaPage />);

    fireEvent.change(await screen.findByLabelText("Profesional"), {
      target: { value: "prof-1" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "09:00" }));
    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Ana" },
    });
    fireEvent.change(screen.getByLabelText("Apellido"), {
      target: { value: "Demo" },
    });
    fireEvent.change(screen.getByLabelText("DNI"), {
      target: { value: "30111222" },
    });
    fireEvent.change(screen.getByLabelText("Teléfono WhatsApp"), {
      target: { value: "11 5555-1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reservar" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("409");
    expect(alerta.textContent).toContain("El horario se solapa");
    expect(screen.getByRole("button", { name: "Reservar" })).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "09:00" }).getAttribute("aria-pressed"),
    ).toBe("true");
  });
});

describe("GestionTurnoPage", () => {
  it("muestra el turno y permite cancelar", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/gestion/token-1")
          ? jsonResponse({
              turno_id: "turno-1",
              inicio: SLOTS[0].inicio,
              fin: SLOTS[0].fin,
              estado: "reservado",
              profesional: CATALOGO.profesionales[0],
              prestacion: CATALOGO.prestaciones[0],
              sena: { requiere: false, monto: null, estado: "no_requiere" },
              puede_confirmar: true,
              puede_cancelar: true,
              plazo_cancelacion_horas: 24,
              politica_sena: "La seña se descuenta del total.",
            })
          : undefined,
      (url, init) =>
        url.endsWith("/cancelar") && init?.method === "POST"
          ? jsonResponse({ estado: "cancelado", sena_perdida: false })
          : undefined,
    ]);
    render(<GestionTurnoPage token="token-1" />);

    expect(await screen.findByText(/Estado: reservado/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Cancelar turno/ }));
    expect(await screen.findByRole("status")).toHaveProperty(
      "textContent",
      "Turno cancelado.",
    );
  });

  it("resume el turno en una Card con el estado como badge", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/gestion/token-1")
          ? jsonResponse({
              turno_id: "turno-1",
              inicio: SLOTS[0].inicio,
              fin: SLOTS[0].fin,
              estado: "reservado",
              profesional: CATALOGO.profesionales[0],
              prestacion: CATALOGO.prestaciones[0],
              sena: { requiere: false, monto: null, estado: "no_requiere" },
              puede_confirmar: true,
              puede_cancelar: true,
              plazo_cancelacion_horas: 24,
              politica_sena: "La seña se descuenta del total.",
            })
          : undefined,
    ]);
    render(<GestionTurnoPage token="token-1" />);

    const resumen = await screen.findByRole("region", {
      name: /resumen del turno/i,
    });
    expect(within(resumen).getByText(/Estado: reservado/)).toBeTruthy();
    const badge = within(resumen).getByText("reservado", {
      selector: ".ds-badge",
    });
    expect(badge.className).toContain("ds-badge--info");
    expect(
      within(resumen).getByRole("button", { name: /Cancelar turno/ }),
    ).toBeTruthy();
  });

  it("explica un 410 verbatim y pide un enlace nuevo sin acciones", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/gestion/token-usado")
          ? jsonResponse(
              { detail: "El enlace ya fue utilizado o venció" },
              410,
            )
          : undefined,
    ]);
    render(<GestionTurnoPage token="token-usado" />);

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("410");
    expect(alerta.textContent).toContain("El enlace ya fue utilizado o venció");
    expect(screen.getByText(/pedí un enlace nuevo/i)).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: /Confirmar turno/ }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /Cancelar turno/ }),
    ).toBeNull();
  });

  it("muestra un 409 verbatim al confirmar y conserva el turno", async () => {
    mockFetch([
      (url) =>
        url.endsWith("/reservar/gestion/token-1")
          ? jsonResponse({
              turno_id: "turno-1",
              inicio: SLOTS[0].inicio,
              fin: SLOTS[0].fin,
              estado: "reservado",
              profesional: CATALOGO.profesionales[0],
              prestacion: CATALOGO.prestaciones[0],
              sena: { requiere: false, monto: null, estado: "no_requiere" },
              puede_confirmar: true,
              puede_cancelar: true,
              plazo_cancelacion_horas: 24,
              politica_sena: "La seña se descuenta del total.",
            })
          : undefined,
      (url, init) =>
        url.endsWith("/confirmar") && init?.method === "POST"
          ? jsonResponse(
              { detail: "El turno ya no puede confirmarse" },
              409,
            )
          : undefined,
    ]);
    render(<GestionTurnoPage token="token-1" />);

    fireEvent.click(
      await screen.findByRole("button", { name: /Confirmar turno/ }),
    );

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("409");
    expect(alerta.textContent).toContain("El turno ya no puede confirmarse");
    expect(
      screen.getByRole("button", { name: /Cancelar turno/ }),
    ).toBeTruthy();
  });
});
