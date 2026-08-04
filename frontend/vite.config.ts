import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend runs on 127.0.0.1:8000; the API is rooted at /auth and /projects.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/projects": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
