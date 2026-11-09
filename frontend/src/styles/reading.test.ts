/**
 * C-17 reading layout contract: the privacy column uses the public measure and
 * centers itself instead of sticking to the left of `.ds-content`.
 */

import { describe, expect, it } from "vitest";

import appCss from "./app.css?raw";

describe("columna de lectura", () => {
  it("usa la medida pública y se centra", () => {
    expect(appCss).toMatch(
      /\.ds-reading\s*\{[^}]*max-width:\s*var\(--measure-public\)/,
    );
    expect(appCss).toMatch(
      /\.ds-reading\s*\{[^}]*margin-inline:\s*auto/,
    );
  });

  it("agrega aire vertical y no desborda con el hash largo", () => {
    expect(appCss).toMatch(/\.ds-reading\s*\{[^}]*padding-block:\s*var\(--space-8\)/);
    expect(appCss).toContain("overflow-wrap: anywhere");
  });
});
