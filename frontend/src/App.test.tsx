import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";

function renderAt(path: string): void {
  window.history.pushState({}, "", path);
  render(<App />);
}

afterEach(() => {
  cleanup();
});

describe("SPA routes", () => {
  it("renders the backoffice placeholder at /", () => {
    renderAt("/");
    expect(
      screen.getByRole("heading", { name: /backoffice/i }),
    ).toBeTruthy();
  });

  it("renders the public booking placeholder at /reservar", () => {
    renderAt("/reservar");
    expect(
      screen.getByRole("heading", { name: /reservar/i }),
    ).toBeTruthy();
  });

  it("renders a 404 for unknown routes without breaking the SPA", () => {
    renderAt("/ruta-que-no-existe");
    expect(
      screen.getByRole("heading", { name: /no encontrada/i }),
    ).toBeTruthy();
    expect(screen.getByText(/404/)).toBeTruthy();
  });
});
