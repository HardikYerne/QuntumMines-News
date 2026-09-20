import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Optional: forward /api calls to your backend so you don't need CORS.
    // proxy: { "/api": "http://localhost:8000" },
  },
});
