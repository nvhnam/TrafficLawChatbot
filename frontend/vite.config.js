import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const BACKEND = 'http://localhost:1904'

const PROXY_ROUTES = [
  '/chat_stream',
  '/answer_with_image_input',
  '/get_system_stats',
  '/process_folder_and_build',
  '/check_progress',
  '/delete_document',
  '/ocr_text',
  '/build_graph',
]

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: Object.fromEntries(
      PROXY_ROUTES.map(r => [r, { target: BACKEND, changeOrigin: true }])
    ),
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  },
})
