import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the API runs separately (`uvicorn api.index:app --reload`);
// the proxy keeps the frontend on one origin, as it is once deployed.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
  build: {
    rolldownOptions: {
      output: {
        // Vega is by far the largest dependency and only needed once the
        // first chart renders; its own chunk lets the shell paint first.
        advancedChunks: {
          groups: [{ name: 'vega', test: /node_modules[\\/]vega/ }],
        },
      },
    },
  },
})
