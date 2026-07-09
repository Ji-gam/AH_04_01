/**
 * React Router 설정.
 * 5탭(홈/트랙커(복약관리 포함)/상담/정보/더보기)은 로그인해야 볼 수 있다 — RequireAuth로 감싼다.
 * /login, /signup은 비로그인 상태에서만 의미 있는 공개 라우트.
 */
import { createBrowserRouter } from "react-router-dom";

import Layout from "./components/common/Layout";
import RequireAuth from "./components/common/RequireAuth";
import AlarmPage from "./pages/AlarmPage/AlarmPage";
import ChatPage from "./pages/ChatPage/ChatPage";
import HomePage from "./pages/HomePage/HomePage";
import InfoPage from "./pages/InfoPage/InfoPage";
import LoginPage from "./pages/LoginPage/LoginPage";
import MedicationPage from "./pages/medication/MedicationPage";
import MorePage from "./pages/MorePage/MorePage";
import SchedulePage from "./pages/SchedulePage/SchedulePage";
import SignupPage from "./pages/SignupPage/SignupPage";
import TrackPage from "./pages/TrackPage/TrackPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: "/", element: <HomePage /> },
          { path: "/alarms", element: <AlarmPage /> },
          { path: "/schedule", element: <SchedulePage /> },
          { path: "/track", element: <TrackPage /> },
          { path: "/medication", element: <MedicationPage /> },
          { path: "/chat", element: <ChatPage /> },
          { path: "/info", element: <InfoPage /> },
          { path: "/more", element: <MorePage /> },
        ],
      },
    ],
  },
]);
