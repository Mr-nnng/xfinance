import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fastapi from './vite-plugin-fastapi.js'

export default defineConfig({
  plugins: [vue(), fastapi()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: '../app/frontend-build',
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
  },
})
