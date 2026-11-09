import { defineConfig } from "vitest/config";

export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "jsdom",
    css: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
