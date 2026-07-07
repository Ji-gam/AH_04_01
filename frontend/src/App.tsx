/**
 * React Router 설정.
 * ⚠ 5탭(홈/추적/상담/Info/더보기) 구성은 decision_log.md에 "가안(확정 아님)"으로 표기되어 있다.
 * 바뀌어도 FRONTEND_ARCHITECTURE.md 1~2, 4~7번(계층구조/상태관리/API연동/스타일/충돌방지)은 그대로 유효하다.
 */
import { createBrowserRouter } from "react-router-dom";

import ChatPage from "./pages/ChatPage/ChatPage";
import HomePage from "./pages/HomePage/HomePage";
import InfoPage from "./pages/InfoPage/InfoPage";
import MorePage from "./pages/MorePage/MorePage";
import TrackPage from "./pages/TrackPage/TrackPage";

export const router = createBrowserRouter([
  { path: "/", element: <HomePage /> },
  { path: "/track", element: <TrackPage /> },
  { path: "/chat", element: <ChatPage /> },
  { path: "/info", element: <InfoPage /> },
  { path: "/more", element: <MorePage /> },
]);
