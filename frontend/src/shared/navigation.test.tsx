/**
 * C-17 navigation helper contract: internal links update the SPA without a
 * document reload, keep the in-memory session, preserve href for accessibility
 * and do not hijack modified clicks or new-tab links.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Link, goBack, navigate, usePathname } from "./navigation";

function Harness(): React.JSX.Element {
  const pathname = usePathname();
  return (
    <>
      <p data-testid="pathname">{pathname}</p>
      <Link to="/reportes">Reportes</Link>
      <Link to="/usuarios" target="_blank">
        Usuarios
      </Link>
    </>
  );
}

beforeEach(() => {
  window.history.replaceState({}, "", "/agenda");
});

afterEach(() => {
  cleanup();
});

describe("Link", () => {
  it("conserva href y navega client-side con un click normal", () => {
    render(<Harness />);

    const link = screen.getByRole("link", { name: "Reportes" });
    expect(link.getAttribute("href")).toBe("/reportes");
    expect(screen.getByTestId("pathname").textContent).toBe("/agenda");

    fireEvent.click(link);

    expect(window.location.pathname).toBe("/reportes");
    expect(screen.getByTestId("pathname").textContent).toBe("/reportes");
  });

  it.each([
    ["ctrl", { ctrlKey: true }],
    ["meta", { metaKey: true }],
    ["shift", { shiftKey: true }],
    ["alt", { altKey: true }],
  ])("no intercepta un click con %s", (_name, modifier) => {
    const pushState = vi.spyOn(window.history, "pushState");
    const preventNavigation = (event: Event) => event.preventDefault();
    window.addEventListener("click", preventNavigation);
    render(<Harness />);

    fireEvent.click(screen.getByRole("link", { name: "Reportes" }), modifier);

    expect(pushState).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/agenda");
    window.removeEventListener("click", preventNavigation);
    pushState.mockRestore();
  });

  it("no intercepta enlaces con target distinto de _self", () => {
    const pushState = vi.spyOn(window.history, "pushState");
    const preventNavigation = (event: Event) => event.preventDefault();
    window.addEventListener("click", preventNavigation);
    render(<Harness />);

    fireEvent.click(screen.getByRole("link", { name: "Usuarios" }));

    expect(pushState).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/agenda");
    window.removeEventListener("click", preventNavigation);
    pushState.mockRestore();
  });

  it("responde a popstate (atrás/adelante)", async () => {
    render(<Harness />);

    navigate("/reportes");
    await waitFor(() => {
      expect(screen.getByTestId("pathname").textContent).toBe("/reportes");
    });

    window.history.back();

    await waitFor(() => {
      expect(window.location.pathname).toBe("/agenda");
      expect(screen.getByTestId("pathname").textContent).toBe("/agenda");
    });
  });
});

describe("goBack", () => {
  it("incrementa appIndex al navegar", () => {
    window.history.replaceState({ appIndex: 4 }, "", "/agenda");

    navigate("/reportes");

    expect(window.history.state).toMatchObject({ appIndex: 5 });
    expect(window.location.pathname).toBe("/reportes");
  });

  it("usa history.back cuando hay historial interno", () => {
    window.history.replaceState({ appIndex: 2 }, "", "/privacidad");
    const back = vi
      .spyOn(window.history, "back")
      .mockImplementation(() => undefined);

    goBack("/");

    expect(back).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/privacidad");
    back.mockRestore();
  });

  it("navega al fallback cuando se entró directo por URL", () => {
    window.history.replaceState(null, "", "/privacidad");

    goBack("/");

    expect(window.location.pathname).toBe("/");
  });
});
