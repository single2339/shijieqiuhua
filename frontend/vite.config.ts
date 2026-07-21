import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true, proxyTimeout: 300_000 } } },
  build: {
    // MapLibre is isolated behind a lazy import and transport-compressed after build.
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          map: ['maplibre-gl'],
        },
      },
    },
  },
})
