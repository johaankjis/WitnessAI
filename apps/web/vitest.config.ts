import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./test/setup.ts"],
    include: ["lib/**/*.test.{ts,tsx}", "components/**/*.test.{tsx,ts}", "app/**/*.test.{tsx,ts}"],
    css: false,
  },
});
