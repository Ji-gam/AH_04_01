import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { router } from "./App";
import { AuthProvider } from "./hooks/useAuth";
import { registerServiceWorker } from "./utils/webPush";
import "./index.css";

// PWA "홈 화면에 추가" 설치 배너가 뜨려면 서비스워커가 페이지 로드 시점에 등록돼 있어야
// 한다 - 로그인 여부/알림 권한 요청과 무관하게 앱이 켜지자마자 바로 호출한다.
registerServiceWorker();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  </React.StrictMode>,
);
