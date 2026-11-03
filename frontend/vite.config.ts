import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    proxy: {
      "/api": process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
      "/health": process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
  },
});
