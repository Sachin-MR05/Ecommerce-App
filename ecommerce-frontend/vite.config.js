import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Force dev server config reload
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000
  }
});
