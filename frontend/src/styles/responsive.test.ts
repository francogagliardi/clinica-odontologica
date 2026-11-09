/**
 * C-17 responsive contract (design.md D9): four breakpoints, rail at 1024,
 * mobile topbar and no page-level horizontal overflow.
 */

import { describe, expect, it } from "vitest";

import appCss from "./app.css?raw";

const BREAKPOINTS = [640, 900, 1024, 1280] as const;

function bodyRule(): string {
  const match = /(?:^|\})\s*body\s*\{([^}]*)\}/.exec(appCss);
  return match?.[1] ?? "";
}

describe("responsive", () => {
  it.each(BREAKPOINTS)("declara el corte de %i px", (breakpoint) => {
    expect(appCss).toContain(`@media (min-width: ${breakpoint}px)`);
  });

  it("no fuerza overflow horizontal en la página", () => {
    expect(bodyRule()).not.toContain("overflow-x");
    expect(appCss).not.toMatch(/html\s*\{[^}]*overflow-x:\s*(auto|scroll)/);
  });

  it("usa rail lateral fijo de 232 px en escritorio y barra superior en móvil", () => {
    expect(appCss).toMatch(/\.ds-topbar\s*\{/);
    expect(appCss).toMatch(/\.ds-menu-button/);
    expect(appCss).toMatch(
      /@media \(min-width: 1024px\)[\s\S]*?grid-template-columns:\s*var\(--rail-width\)/,
    );
  });

  it("oculta el botón Menú en escritorio con especificidad suficiente", () => {
    expect(appCss).toMatch(
      /@media \(min-width: 1024px\)(?:[\s\S]*?)\.ds-topbar \.ds-menu-button\s*\{[^}]*display:\s*none/,
    );
  });

  it("mantiene objetivos secundarios de al menos 24 px", () => {
    expect(appCss).toMatch(
      /\.ds-public-nav a\s*\{[^}]*min-height:\s*var\(--tap-target\)/,
    );
    expect(appCss).toMatch(
      /\.ds-button--sm\s*\{[^}]*min-height:\s*var\(--tap-target\)/,
    );
  });

  it("limita el contenido a 1280 px y centra con gutters", () => {
    expect(appCss).toMatch(/\.ds-content\s*\{[^}]*max-width:\s*var\(--shell-max\)/);
    expect(appCss).toMatch(/\.ds-content\s*\{[^}]*margin-inline:\s*auto/);
  });
});
