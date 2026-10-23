import { defineConfig } from '@hey-api/openapi-ts'

// Generates a typed client and TanStack Query helpers from the backend's OpenAPI file.
// Run `pnpm gen:api` after the backend changes apps/api/openapi.json.
export default defineConfig({
  input: '../api/openapi.json',
  output: 'src/api/generated',
  plugins: ['@hey-api/client-fetch', '@tanstack/react-query'],
})
