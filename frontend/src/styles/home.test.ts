/**
 * C-17 home layout contract: centered hero column with vertical breathing room,
 * stacked actions at 320 px and inline actions from 640 px.
 */

import { describe, expect, it } from "vitest";

import appCss from "./app.css?raw";

describe("portada", () => {
  it("deja aire vertical con padding por tokens y clamp", () => {
    expect(appCss).toMatch(
      /\.ds-home\s*\{[^}]*padding-block:\s*clamp\(var\(--space-8\),\s*6vw,\s*var\(--space-12\)\)/,
    );
  });

  it("centra una columna de 42 a 46 rem", () => {
    expect(appCss).toMatch(
      /\.ds-home__inner\s*\{[^}]*max-width:\s*44rem/,
    );
    expect(appCss).toMatch(
      /\.ds-home__inner\s*\{[^}]*margin-inline:\s*auto/,
    );
    expect(appCss).toMatch(
      /\.ds-home__inner\s*\{[^}]*text-align:\s*center/,
    );
  });

  it("apila las acciones en móvil y las pone en fila desde 640 px", () => {
    expect(appCss).toMatch(
      /\.ds-home__actions\s*\{[^}]*flex-direction:\s*column/,
    );
    expect(appCss).toMatch(
      /@media \(min-width: 640px\)[\s\S]*?\.ds-home__actions\s*\{[^}]*flex-direction:\s*row/,
    );
  });
});
