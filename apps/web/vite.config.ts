/// <reference types="vitest/config" />
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // The router plugin must come before react(). It generates src/routeTree.gen.ts.
  plugins: [tanstackRouter({ target: 'react', autoCodeSplitting: true }), react()],
  server: { host: true, port: 5173 },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
