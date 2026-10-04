import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the Skoiv MTK Workbench UI.
// - host 0.0.0.0 + allowedHosts for container preview environments
// - port 5173 must match src-tauri/tauri.conf.json devUrl
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    host: "0.0.0.0",
    allowedHosts: true,
  },
  build: {
    target: "es2021",
    sourcemap: true,
  },
});
