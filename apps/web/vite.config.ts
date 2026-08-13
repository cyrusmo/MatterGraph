import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8001";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/health": { target: proxyTarget, changeOrigin: true },
        "/capabilities": { target: proxyTarget, changeOrigin: true },
        "/demo": { target: proxyTarget, changeOrigin: true },
        "/materials": { target: proxyTarget, changeOrigin: true },
        "/search": { target: proxyTarget, changeOrigin: true },
        "/scores": { target: proxyTarget, changeOrigin: true },
        "/simulations": { target: proxyTarget, changeOrigin: true },
        "/workflows": { target: proxyTarget, changeOrigin: true },
      },
    },
  };
});
