import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    // api/client.ts가 상대경로(/api/v1/...)로 호출한다 — 운영은 NGINX가 이 역할을 하므로
    // (decision_log.md), 로컬 dev 서버에서도 동일하게 백엔드로 포워딩한다.
    proxy: { "/api/v1": "http://localhost:8000" },
  },
});
