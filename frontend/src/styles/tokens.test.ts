/**
 * C-17 design-system contract (D1–D4, D8, D12).
 *
 * jsdom cannot compute styles, so the only automatic edge for colour and
 * contrast is reading the stylesheets as text, parsing the custom properties
 * and recalculating the WCAG 2.x ratios. The matrix expected values come from
 * `openspec/changes/c-17-frontend-design-system/design.md` §D3.
 */

import { describe, expect, it } from "vitest";

import appCss from "./app.css?raw";
import tokensCss from "./tokens.css?raw";

interface TokenGroup {
  name: string;
  prefixes: readonly string[];
  required: readonly string[];
}

const GROUPS: readonly TokenGroup[] = [
  {
    name: "color",
    prefixes: ["--color-"],
    required: [
      "--color-ink",
      "--color-ink-soft",
      "--color-paper",
      "--color-surface",
      "--color-surface-sunken",
      "--color-line",
      "--color-line-strong",
      "--color-primary",
      "--color-primary-hover",
      "--color-primary-tint",
      "--color-danger",
      "--color-danger-bg",
      "--color-warning",
      "--color-warning-bg",
      "--color-info",
      "--color-info-bg",
      "--color-focus",
      "--color-print-bg",
      "--color-print-ink",
    ],
  },
  {
    name: "tipografía",
    prefixes: ["--font-", "--text-", "--leading-", "--measure-", "--weight-"],
    required: [
      "--font-display",
      "--font-ui",
      "--font-mono",
      "--text-xs",
      "--text-sm",
      "--text-base",
      "--text-lg",
      "--text-xl",
      "--text-2xl",
      "--text-3xl",
      "--text-display",
      "--leading-xs",
      "--leading-sm",
      "--leading-base",
      "--leading-lg",
      "--leading-xl",
      "--leading-2xl",
      "--leading-3xl",
      "--leading-display",
      "--measure-public",
      "--measure-backoffice",
      "--weight-body",
      "--weight-ui",
    ],
  },
  {
    name: "espaciado",
    prefixes: ["--space-"],
    required: [
      "--space-1",
      "--space-2",
      "--space-3",
      "--space-4",
      "--space-6",
      "--space-8",
      "--space-12",
      "--space-16",
    ],
  },
  {
    name: "radios",
    prefixes: ["--radius-"],
    required: ["--radius-xs", "--radius-sm", "--radius-md", "--radius-pill"],
  },
  {
    name: "bordes",
    prefixes: ["--border-"],
    required: ["--border-width", "--border-hairline", "--border-control"],
  },
  {
    name: "foco",
    prefixes: ["--focus-"],
    required: ["--focus-width", "--focus-offset", "--focus-ring"],
  },
  {
    name: "movimiento",
    prefixes: ["--motion-"],
    required: [
      "--motion-duration-fast",
      "--motion-duration-slow",
      "--motion-ease",
      "--motion-reduced",
    ],
  },
  {
    name: "sombra",
    prefixes: ["--shadow-"],
    required: ["--shadow-surface"],
  },
  {
    name: "layout",
    prefixes: ["--rail-", "--shell-", "--gutter", "--touch-", "--tap-"],
    required: [
      "--rail-width",
      "--shell-max",
      "--gutter",
      "--touch-target",
      "--tap-target",
    ],
  },
];

type PairRole = "texto" | "interfaz";

interface ContrastPair {
  label: string;
  fg: string;
  bg: string;
  role: PairRole;
  expected: number;
}

/**
 * Matrix from design.md §D3. `expected` is the rounded ratio documented in the
 * change; the test recalculates it from the hex values in tokens.css.
 */
const MATRIX: readonly ContrastPair[] = [
  { label: "ink sobre paper", fg: "--color-ink", bg: "--color-paper", role: "texto", expected: 14.39 },
  { label: "ink sobre surface", fg: "--color-ink", bg: "--color-surface", role: "texto", expected: 15.42 },
  { label: "ink-soft sobre paper", fg: "--color-ink-soft", bg: "--color-paper", role: "texto", expected: 6.08 },
  { label: "ink-soft sobre surface", fg: "--color-ink-soft", bg: "--color-surface", role: "texto", expected: 6.51 },
  { label: "ink sobre surface-sunken", fg: "--color-ink", bg: "--color-surface-sunken", role: "texto", expected: 13.18 },
  { label: "line-strong sobre surface", fg: "--color-line-strong", bg: "--color-surface", role: "interfaz", expected: 4.03 },
  { label: "line-strong sobre paper", fg: "--color-line-strong", bg: "--color-paper", role: "interfaz", expected: 3.76 },
  { label: "primary sobre surface", fg: "--color-primary", bg: "--color-surface", role: "texto", expected: 7.91 },
  { label: "surface sobre primary", fg: "--color-surface", bg: "--color-primary", role: "texto", expected: 7.91 },
  { label: "surface sobre primary-hover", fg: "--color-surface", bg: "--color-primary-hover", role: "texto", expected: 9.91 },
  { label: "primary sobre primary-tint", fg: "--color-primary", bg: "--color-primary-tint", role: "texto", expected: 6.76 },
  { label: "danger sobre surface", fg: "--color-danger", bg: "--color-surface", role: "texto", expected: 7.48 },
  { label: "danger sobre danger-bg", fg: "--color-danger", bg: "--color-danger-bg", role: "texto", expected: 6.42 },
  { label: "warning sobre warning-bg", fg: "--color-warning", bg: "--color-warning-bg", role: "texto", expected: 6.40 },
  { label: "warning sobre surface", fg: "--color-warning", bg: "--color-surface", role: "texto", expected: 7.18 },
  { label: "info sobre info-bg", fg: "--color-info", bg: "--color-info-bg", role: "texto", expected: 6.54 },
  { label: "focus sobre surface", fg: "--color-focus", bg: "--color-surface", role: "interfaz", expected: 7.91 },
];

/** Minimum allowed by WCAG 2.2 AA for the role declared in the matrix. */
const MINIMUM: Record<PairRole, number> = { texto: 4.5, interfaz: 3 };

const LITERAL_COLOR =
  /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b|\brgba?\(|\bhsla?\(/g;

function parseTokens(css: string): Map<string, string> {
  const root = /:root\s*\{([\s\S]*?)\}/.exec(css);
  if (root === null) {
    throw new Error("tokens.css debe declarar un bloque :root");
  }
  const body = root[1] ?? "";
  const tokens = new Map<string, string>();
  for (const match of body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/gi)) {
    const name = match[1];
    const value = match[2];
    if (name !== undefined && value !== undefined) {
      tokens.set(name, value.trim());
    }
  }
  return tokens;
}

function valueOf(tokens: Map<string, string>, name: string): string {
  const value = tokens.get(name);
  if (value === undefined) {
    throw new Error(`Falta el token ${name} en tokens.css`);
  }
  return value;
}

function hexToRgb(hex: string): readonly [number, number, number] {
  const clean = hex.replace("#", "");
  const full =
    clean.length === 3 || clean.length === 4
      ? clean
          .slice(0, 3)
          .split("")
          .map((character) => character + character)
          .join("")
      : clean.slice(0, 6);
  const red = Number.parseInt(full.slice(0, 2), 16);
  const green = Number.parseInt(full.slice(2, 4), 16);
  const blue = Number.parseInt(full.slice(4, 6), 16);
  if ([red, green, blue].some((channel) => Number.isNaN(channel))) {
    throw new Error(`Valor de color no hexadecimal: ${hex}`);
  }
  return [red, green, blue];
}

function relativeLuminance(hex: string): number {
  const [red, green, blue] = hexToRgb(hex).map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.03928
      ? normalized / 12.92
      : Math.pow((normalized + 0.055) / 1.055, 2.4);
  }) as [number, number, number];
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrastRatio(fgHex: string, bgHex: string): number {
  const first = relativeLuminance(fgHex);
  const second = relativeLuminance(bgHex);
  const lighter = Math.max(first, second);
  const darker = Math.min(first, second);
  return (lighter + 0.05) / (darker + 0.05);
}

function findLiteralColors(css: string): readonly string[] {
  return css.match(LITERAL_COLOR) ?? [];
}

const tokens = parseTokens(tokensCss);

describe("tokens de diseño", () => {
  it("declara los grupos requeridos con valor no vacío", () => {
    for (const group of GROUPS) {
      const members = [...tokens.keys()].filter((name) =>
        group.prefixes.some((prefix) => name.startsWith(prefix)),
      );
      expect(members.length, `grupo ${group.name} sin tokens`).toBeGreaterThan(
        0,
      );
      for (const name of group.required) {
        expect(tokens.get(name), `${group.name}: falta ${name}`).toBeTruthy();
      }
    }
  });

  it("recalcula la matriz de contraste de design.md §D3", () => {
    for (const pair of MATRIX) {
      const ratio = contrastRatio(
        valueOf(tokens, pair.fg),
        valueOf(tokens, pair.bg),
      );
      expect(ratio, `${pair.label} (${pair.fg} sobre ${pair.bg})`).toBeCloseTo(
        pair.expected,
        1,
      );
    }
  });

  it("mantiene los umbrales AA: 4.5:1 en texto y 3:1 en interfaz", () => {
    for (const pair of MATRIX) {
      const ratio = contrastRatio(
        valueOf(tokens, pair.fg),
        valueOf(tokens, pair.bg),
      );
      expect(
        ratio,
        `${pair.label}: ${pair.fg} sobre ${pair.bg} da ${ratio.toFixed(2)}:1, ` +
          `mínimo ${MINIMUM[pair.role]}:1`,
      ).toBeGreaterThanOrEqual(MINIMUM[pair.role]);
    }
  });

  it("no deja colores literales fuera de tokens.css", () => {
    const literals = findLiteralColors(appCss);
    expect(
      literals,
      `app.css debe consumir var(--…) y no colores literales: ${literals.join(", ")}`,
    ).toEqual([]);
  });

  it("el guard detecta colores literales si se introducen", () => {
    const cssConLiterales =
      ".x { color: #ffffff; background: rgb(10 20 30); border-color: hsl(1, 2%, 3%); }";
    expect(findLiteralColors(cssConLiterales)).toEqual([
      "#ffffff",
      "rgb(",
      "hsl(",
    ]);
  });

  it("solo referencia tokens declarados en tokens.css", () => {
    const references = [...appCss.matchAll(/var\(\s*(--[a-z0-9-]+)/gi)]
      .map((match) => match[1])
      .filter((name): name is string => name !== undefined);
    const unknown = [...new Set(references)].filter(
      (name) => !tokens.has(name),
    );
    expect(unknown, `tokens no declarados: ${unknown.join(", ")}`).toEqual([]);
  });
});
