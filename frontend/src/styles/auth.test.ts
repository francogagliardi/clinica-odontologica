/**
 * C-17 auth layout contract (design.md D5/D9): a centered panel with a bounded
 * width that works from 320 px and does not create page-level overflow.
 */

import { describe, expect, it } from "vitest";

import appCss from "./app.css?raw";

describe("layout de autenticación", () => {
  it("crea un main de autenticación centrado en ambos ejes", () => {
    expect(appCss).toMatch(/\.ds-auth\s*\{[^}]*display:\s*flex/);
    expect(appCss).toMatch(/\.ds-auth\s*\{[^}]*align-items:\s*center/);
    expect(appCss).toMatch(/\.ds-auth\s*\{[^}]*justify-content:\s*center/);
    expect(appCss).toMatch(/\.ds-auth\s*\{[^}]*width:\s*100%/);
  });

  it("limita la tarjeta a 440 px y la centra horizontalmente", () => {
    expect(appCss).toMatch(
      /\.ds-auth__panel\s*\{[^}]*max-width:\s*27\.5rem/,
    );
    expect(appCss).toMatch(
      /\.ds-auth__panel\s*\{[^}]*margin-inline:\s*auto/,
    );
  });

  it("el shell sin sesión ocupa el alto disponible sin rail", () => {
    expect(appCss).toMatch(
      /\.ds-shell--signed-out\s*\{[^}]*display:\s*flex/,
    );
    expect(appCss).toMatch(
      /\.ds-shell--signed-out\s*\{[^}]*min-height:\s*100vh/,
    );
    expect(appCss).toMatch(
      /\.ds-shell--signed-out \.ds-content\s*\{[^}]*align-items:\s*center/,
    );
  });

  it("no agrega overflow horizontal al body", () => {
    const body = /(?:^|\})\s*body\s*\{([^}]*)\}/.exec(appCss)?.[1] ?? "";
    expect(body).not.toContain("overflow-x");
  });
});
