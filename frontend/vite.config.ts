import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server forwards /api calls to the FastAPI backend, so no CORS setup is needed.
const apiTarget = process.env.VITE_API_PROXY || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1200 },
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
  // `npm run demo`: production build served on the same port. No live-reload connection, so a busy PC
  // can never trigger a page reload in the middle of a live demonstration.
  preview: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
});
