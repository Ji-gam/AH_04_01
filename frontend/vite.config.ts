import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // 개발 중 CORS 신경 안 쓰고 바로 백엔드 호출하고 싶으면 아래 프록시를 쓰세요.
    // (또는 .env의 VITE_API_BASE_URL을 백엔드 주소로 직접 지정해도 됩니다.)
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
