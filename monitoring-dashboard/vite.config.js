import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Runs entirely independently of ecommerce-frontend and merchant-agent-core -
// see README.md. Default dev port matches the project brief (5173, Vite's
// own default) so it's explicit rather than accidental.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
