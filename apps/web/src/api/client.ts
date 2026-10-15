import { client } from './generated/client.gen'

// Point the generated client at the backend. Set VITE_API_URL to override.
client.setConfig({
  baseUrl: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
  credentials: 'include',
})
