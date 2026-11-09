/**
 * C-17 shared components contract (design.md D6–D8).
 *
 * These tests freeze the observable contract the pages rely on: roles, exact
 * accessible names, aria relations, native disabled behaviour and the verbatim
 * loading/error copy. No styling engine is involved: jsdom only checks markup.
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";
import { EmptyState } from "./EmptyState";
import { ErrorBanner } from "./ErrorBanner";
import { EstadoBadge } from "./EstadoBadge";
import { Input } from "./Input";
import { Loading } from "./Loading";
import { PageHeader } from "./PageHeader";
import { Select } from "./Select";
import { Table } from "./Table";

afterEach(() => {
  cleanup();
});

describe("Button", () => {
  it("renderiza un enlace cuando recibe href", () => {
    render(
      <Button href="/reservar" variant="primary">
        Reservar turno
      </Button>,
    );

    const link = screen.getByRole("link", { name: "Reservar turno" });
    expect(link.getAttribute("href")).toBe("/reservar");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("renderiza un botón nativo con type button por defecto", () => {
    render(<Button>Guardar</Button>);

    const button = screen.getByRole("button", { name: "Guardar" });
    expect(button.tagName).toBe("BUTTON");
    expect(button.getAttribute("type")).toBe("button");
  });

  it("respeta disabled y no dispara la acción", () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Reservar
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Reservar" });
    expect(button.getAttribute("disabled")).not.toBeNull();
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("acepta un type submit explícito", () => {
    render(<Button type="submit">Ingresar</Button>);
    expect(
      screen.getByRole("button", { name: "Ingresar" }).getAttribute("type"),
    ).toBe("submit");
  });
});

describe("Input", () => {
  it("usa la etiqueta visible como nombre accesible exacto", () => {
    render(<Input label="Email" type="email" />);

    const input = screen.getByRole("textbox", { name: "Email" });
    expect(input.getAttribute("aria-describedby")).toBeNull();
  });

  it("asocia la ayuda por aria-describedby sin sumarla al nombre", () => {
    render(<Input label="Email" hint="Usá tu correo institucional" />);

    const input = screen.getByRole("textbox", { name: "Email" });
    const describedBy = input.getAttribute("aria-describedby");
    expect(describedBy).not.toBeNull();
    expect(document.getElementById(describedBy ?? "")?.textContent).toBe(
      "Usá tu correo institucional",
    );
  });

  it("marca aria-invalid y asocia el error sin cambiar el nombre", () => {
    render(<Input label="DNI" error="DNI inválido" />);

    const input = screen.getByRole("textbox", { name: "DNI" });
    expect(input.getAttribute("aria-invalid")).toBe("true");
    const describedBy = input.getAttribute("aria-describedby");
    expect(document.getElementById(describedBy ?? "")?.textContent).toBe(
      "DNI inválido",
    );
  });

  it("asocia ayuda y error a la vez", () => {
    render(
      <Input label="Teléfono" hint="Con código de área" error="Formato inválido" />,
    );

    const input = screen.getByRole("textbox", { name: "Teléfono" });
    const ids = (input.getAttribute("aria-describedby") ?? "").split(" ");
    const texts = ids.map((id) => document.getElementById(id)?.textContent);
    expect(texts).toEqual(["Con código de área", "Formato inválido"]);
  });
});

describe("Select", () => {
  it("usa la etiqueta visible como nombre accesible exacto", () => {
    render(
      <Select label="Vista" defaultValue="dia">
        <option value="dia">Día</option>
        <option value="semana">Semana</option>
      </Select>,
    );

    const select = screen.getByRole("combobox", { name: "Vista" });
    expect(within(select).getAllByRole("option")).toHaveLength(2);
    expect(select.getAttribute("aria-describedby")).toBeNull();
  });

  it("asocia ayuda y error igual que Input", () => {
    render(
      <Select label="Vista" hint="Elegí el rango" error="Vista inválida">
        <option value="dia">Día</option>
      </Select>,
    );

    const select = screen.getByRole("combobox", { name: "Vista" });
    expect(select.getAttribute("aria-invalid")).toBe("true");
    const ids = (select.getAttribute("aria-describedby") ?? "").split(" ");
    expect(ids.map((id) => document.getElementById(id)?.textContent)).toEqual([
      "Elegí el rango",
      "Vista inválida",
    ]);
  });
});

describe("Loading", () => {
  it("anuncia la carga en una región status con el texto exacto", () => {
    render(<Loading />);

    const status = screen.getByRole("status");
    expect(status.textContent).toBe("Cargando…");
    expect(status.getAttribute("aria-live")).toBe("polite");
  });

  it("acepta una etiqueta explícita", () => {
    render(<Loading label="Consultando agenda…" />);
    expect(screen.getByRole("status").textContent).toBe("Consultando agenda…");
  });
});

describe("ErrorBanner", () => {
  it("anuncia el mensaje verbatim en una región alert", () => {
    render(<ErrorBanner message="409 — el horario ya está ocupado" />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("409 — el horario ya está ocupado");
  });

  it("muestra título y acción opcionales", () => {
    render(
      <ErrorBanner
        title="No se pudo guardar"
        message="422 — datos inválidos"
        action={<Button size="sm">Reintentar</Button>}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(within(alert).getByText("No se pudo guardar")).toBeTruthy();
    expect(alert.textContent).toContain("422 — datos inválidos");
    expect(
      within(alert).getByRole("button", { name: "Reintentar" }),
    ).toBeTruthy();
  });
});

describe("Card", () => {
  it("usa h2 por defecto y expone la sección con nombre accesible", () => {
    render(
      <Card title="Resumen del turno" description="Datos de la reserva">
        <p>Contenido</p>
      </Card>,
    );

    expect(
      screen.getByRole("heading", { level: 2, name: "Resumen del turno" }),
    ).toBeTruthy();
    const region = screen.getByRole("region", { name: "Resumen del turno" });
    expect(within(region).getByText("Datos de la reserva")).toBeTruthy();
    expect(within(region).getByText("Contenido")).toBeTruthy();
  });

  it("permite elegir el nivel de encabezado", () => {
    render(
      <Card title="Detalle" headingLevel={3}>
        <p>Filas</p>
      </Card>,
    );

    expect(
      screen.getByRole("heading", { level: 3, name: "Detalle" }),
    ).toBeTruthy();
  });

  it("renderiza acciones junto al título", () => {
    render(
      <Card title="Turnos" actions={<Button size="sm">Actualizar</Button>}>
        <p>Contenido</p>
      </Card>,
    );

    expect(screen.getByRole("button", { name: "Actualizar" })).toBeTruthy();
  });
});

describe("Table", () => {
  it("envuelve la tabla en una región desplazable con nombre y foco", () => {
    render(
      <Table label="Usuarios">
        <thead>
          <tr>
            <th scope="col">Nombre</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Ana</td>
          </tr>
        </tbody>
      </Table>,
    );

    const region = screen.getByRole("region", { name: "Usuarios" });
    expect(region.getAttribute("tabindex")).toBe("0");
    const table = within(region).getByRole("table");
    expect(table).toBeTruthy();
    expect(
      within(table)
        .getByRole("columnheader", { name: "Nombre" })
        .getAttribute("scope"),
    ).toBe("col");
  });
});

describe("Badge y EstadoBadge", () => {
  it("aplica el tono como clase sin cambiar el texto", () => {
    render(<Badge tone="warning">Pendiente</Badge>);
    const badge = screen.getByText("Pendiente");
    expect(badge.className).toContain("ds-badge");
    expect(badge.className).toContain("ds-badge--warning");
  });

  it("mapea estados conocidos a un tono y deja el texto crudo", () => {
    render(<EstadoBadge estado="cancelado" />);
    expect(screen.getByText("cancelado").className).toContain(
      "ds-badge--danger",
    );
  });

  it("usa tonos distintos por estado sin traducir", () => {
    render(
      <>
        <EstadoBadge estado="reservado" />
        <EstadoBadge estado="atendido" />
      </>,
    );
    expect(screen.getByText("reservado").className).toContain(
      "ds-badge--info",
    );
    expect(screen.getByText("atendido").className).toContain(
      "ds-badge--success",
    );
  });

  it("cae en neutral para un estado desconocido", () => {
    render(<EstadoBadge estado="en_revision" />);
    const badge = screen.getByText("en_revision");
    expect(badge.textContent).toBe("en_revision");
    expect(badge.className).toContain("ds-badge--neutral");
  });
});

describe("EmptyState", () => {
  it("muestra título, explicación y acción opcional", () => {
    render(
      <EmptyState
        title="Sin turnos para este rango"
        description="Probá con otra fecha o profesional."
        action={<Button size="sm">Cambiar de fecha</Button>}
      />,
    );

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Sin turnos para este rango",
      }),
    ).toBeTruthy();
    expect(screen.getByText("Probá con otra fecha o profesional.")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Cambiar de fecha" }),
    ).toBeTruthy();
  });

  it("funciona sin acción", () => {
    render(
      <EmptyState title="Sin resultados" description="No hay filas." />,
    );
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("PageHeader", () => {
  it("renderiza un único h1 con las acciones", () => {
    render(
      <PageHeader
        title="Agenda"
        description="Turnos del día"
        eyebrow="Backoffice"
        actions={<Button>Nuevo turno</Button>}
      />,
    );

    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]?.textContent).toBe("Agenda");
    expect(screen.getByText("Turnos del día")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Nuevo turno" })).toBeTruthy();
  });
});
