import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/**
 * Unit tests for pure lib utilities and presentational components.
 *
 * Deliberately separate from vite.config.ts (the TanStack Start / Nitro app
 * config) so this suite stays fast and needs no server plugins, no PGLite,
 * and no network.
 *
 * Test files use the `.unit.test.ts(x)` suffix so they don't collide with
 * the existing `node --test` suites run by `npm run test`.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    // Match the app's `@/` alias (vite.config.ts) so components that import
    // `@/lib/...` or `@/components/...` resolve in the unit-test sandbox too.
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.unit.test.{ts,tsx}"],
  },
});
