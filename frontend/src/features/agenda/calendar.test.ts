import { describe, expect, it } from "vitest";

import {
  diasEntre,
  horaDe,
  inicioEnDia,
  inicioEnHora,
  mover,
  rango,
} from "./calendar";

describe("calendar ranges", () => {
  it("día devuelve la misma fecha", () => {
    expect(rango("dia", "2026-11-09")).toEqual({
      desde: "2026-11-09",
      hasta: "2026-11-09",
    });
  });

  it("semana arranca el lunes y termina el domingo", () => {
    expect(rango("semana", "2026-11-11")).toEqual({
      desde: "2026-11-09",
      hasta: "2026-11-15",
    });
  });

  it("mes cubre el mes completo sin pasarse de 62 días", () => {
    expect(rango("mes", "2026-02-14")).toEqual({
      desde: "2026-02-01",
      hasta: "2026-02-28",
    });
    const { desde, hasta } = rango("mes", "2026-11-10");
    expect(diasEntre(desde, hasta).length).toBe(30);
  });

  it("navega día, semana y mes", () => {
    expect(mover("dia", "2026-11-09", 1)).toBe("2026-11-10");
    expect(mover("semana", "2026-11-09", 1)).toBe("2026-11-16");
    expect(mover("mes", "2026-11-09", 1)).toBe("2026-12-01");
    expect(mover("mes", "2026-11-09", -1)).toBe("2026-10-01");
  });

  it("calcula inicios ISO con offset argentino", () => {
    expect(inicioEnHora("2026-11-09", 9)).toBe("2026-11-09T09:00:00-03:00");
    expect(
      inicioEnDia("2026-11-10", "2026-11-09T14:30:00-03:00"),
    ).toBe("2026-11-10T14:30:00-03:00");
    expect(horaDe("2026-11-09T14:30:00-03:00")).toBe("14:30");
  });
});
