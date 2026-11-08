import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectRoot, "VITE_");
  const walletTarget = env.VITE_API_TARGET || "http://localhost:5000";

  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      strictPort: true,
      proxy: {
        "/api": { target: walletTarget },
        "/lab/api": {
          target: "http://localhost:5002",
          configure: (proxy) => {
            proxy.on("proxyReq", (proxyRequest, request) => {
              if (request.method !== "GET" && request.method !== "HEAD") {
                proxyRequest.setHeader("Origin", "http://localhost:5002");
              }
            });
          },
        },
        "/lab/artifacts": { target: "http://localhost:5002" },
      },
    },
    build: {
      rollupOptions: {
        input: {
          wallet: resolve(projectRoot, "index.html"),
          guide: resolve(projectRoot, "guide.html"),
        },
      },
    },
  };
});
