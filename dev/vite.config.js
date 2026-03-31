import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // Allow Docker-internal host headers (e.g. blackbox probing http://frontend:5173)
    allowedHosts: ['frontend', 'localhost', '127.0.0.1'],
  },
});
