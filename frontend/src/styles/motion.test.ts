/**
 * C-17 motion contract (design.md D10): transitions only for state changes,
 * reduced-motion respected, no looping keyframes.
 */

import { describe, expect, it } from "vitest";

import appCss from "./app.css?raw";

function reducedMotionBlock(): string {
  const match =
    /@media \(prefers-reduced-motion: reduce\)\s*\{([\s\S]*?)\n\}/.exec(appCss);
  return match?.[1] ?? "";
}

describe("movimiento", () => {
  it("no declara animaciones en bucle ni @keyframes decorativos", () => {
    expect(appCss).not.toContain("@keyframes");
    expect(appCss).not.toContain("infinite");
  });

  it("respeta prefers-reduced-motion con duración casi nula y sin scroll suave", () => {
    const block = reducedMotionBlock();
    expect(block).not.toBe("");
    expect(block).toContain("transition-duration: var(--motion-reduced)");
    expect(block).toContain("animation-duration: var(--motion-reduced)");
    expect(block).toContain("animation-iteration-count: 1");
    expect(block).toContain("scroll-behavior: auto");
  });

  it("limita las transiciones a estados de interfaz de 120 a 180 ms", () => {
    expect(appCss).toContain("var(--motion-duration-fast)");
    expect(appCss).toContain("var(--motion-duration-slow)");
  });
});
