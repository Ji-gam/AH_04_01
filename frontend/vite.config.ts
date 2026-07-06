import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // [핀포인트 수정] 백엔드가 127.0.0.1:8000에 떠 있으므로, 프론트도 반드시 같은 호스트 이름(127.0.0.1)으로
    // 떠야 브라우저 쿠키 정책(SameSite)상 "같은 사이트"로 인식됩니다. localhost와 127.0.0.1은 포트가
    // 같아도 서로 다른 사이트로 취급되어 쿠키가 전달되지 않습니다 (오늘 겪었던 로그인 실패의 근본 원인).
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
