import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// `npm run dev` proxies /api to a backend. Default: a local uvicorn on :8000. To develop the
// UI against the running compose stack instead: VITE_API_TARGET=http://localhost:8088 npm run dev
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": { target: process.env.VITE_API_TARGET ?? "http://localhost:8000", changeOrigin: true } },
  },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
