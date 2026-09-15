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
  test: {
    environment: "jsdom",
    include: ["src/**/*.unit.test.{ts,tsx}"],
  },
});
