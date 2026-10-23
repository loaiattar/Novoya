/// <reference types="vitest/config" />
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig, type ProxyOptions } from 'vite'

// The browser calls the API at /api on the web app's own origin, so the session cookie is
// always first-party (docs/adr/0011-same-origin-api-proxy.md). The proxy strips /api.
// In docker compose the API is http://api:8000; run alone, it is http://localhost:8000.
const apiProxy: Record<string, ProxyOptions> = {
  '/api': {
    target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
    rewrite: (path) => path.replace(/^\/api/, ''),
    xfwd: true, // X-Forwarded-For: the API rate-limits by the browser's IP, not the proxy's
  },
}

// https://vite.dev/config/
export default defineConfig({
  // The router plugin must come before react(). It generates src/routeTree.gen.ts.
  plugins: [tanstackRouter({ target: 'react', autoCodeSplitting: true }), react(), tailwindcss()],
  // `@/` is `src/`, as shadcn/ui components expect.
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { host: true, port: 5173, proxy: apiProxy },
  preview: { proxy: apiProxy },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
