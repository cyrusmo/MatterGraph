import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/health": { target: env.VITE_API_URL || "http://127.0.0.1:8000", changeOrigin: true },
        "/materials": { target: env.VITE_API_URL || "http://127.0.0.1:8000", changeOrigin: true },
        "/search": { target: env.VITE_API_URL || "http://127.0.0.1:8000", changeOrigin: true },
        "/scores": { target: env.VITE_API_URL || "http://127.0.0.1:8000", changeOrigin: true },
        "/simulations": { target: env.VITE_API_URL || "http://127.0.0.1:8000", changeOrigin: true },
      },
    },
  };
});
