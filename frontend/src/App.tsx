/**
 * React Router 설정.
 * [변경] 홈이 시작화면 - 로그인 안 해도 접근 가능하다. 개인건강정보는 개인정보라 로그인이 꼭 필요하지만,
 * 나머지 탭(트랙커/상담/정보/복약알림/더보기)은 로그인 안 해도 기본적으로 볼 수 있게 열어둔다.
 * /login 하나로 로그인/가입을 다 처리한다(SignupPage 별도 라우트 없음).
 */
import { createBrowserRouter } from "react-router-dom";

import Layout from "./components/common/Layout";
import RequireAuth from "./components/common/RequireAuth";
import AccountSettingsPage from "./pages/AccountSettingsPage/AccountSettingsPage";
import AlarmPage from "./pages/AlarmPage/AlarmPage";
import ChatPage from "./pages/ChatPage/ChatPage";
import ConsentPage from "./pages/ConsentPage/ConsentPage";
import ContentDetailPage from "./pages/ContentGenerationPage/ContentDetailPage";
import ContentGenerationPage from "./pages/ContentGenerationPage/ContentGenerationPage";
import HealthInfoPage from "./pages/HealthInfoPage/HealthInfoPage";
import HomePage from "./pages/HomePage/HomePage";
import InfoPage from "./pages/InfoPage/InfoPage";
import LoginPage from "./pages/LoginPage/LoginPage";
import MedicationPage from "./pages/medication/MedicationPage";
import MorePage from "./pages/MorePage/MorePage";
import SchedulePage from "./pages/SchedulePage/SchedulePage";
import TrackPage from "./pages/TrackPage/TrackPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    // 계정설정은 로그인은 필요하지만 5탭 네비게이션은 안 필요한 화면이라 Layout 밖에 둔다.
    element: <RequireAuth />,
    children: [{ path: "/account-settings", element: <AccountSettingsPage /> }],
  },
  {
    element: <Layout />,
    children: [
      // 홈 + 대부분의 탭은 로그인 안 해도 기본적으로 볼 수 있다.
      { path: "/", element: <HomePage /> },
      { path: "/alarms", element: <AlarmPage /> },
      { path: "/schedule", element: <SchedulePage /> },
      { path: "/track", element: <TrackPage /> },
      { path: "/medication", element: <MedicationPage /> },
      { path: "/chat", element: <ChatPage /> },
      { path: "/info", element: <InfoPage /> },
      { path: "/more", element: <MorePage /> },
      { path: "/content-generation", element: <ContentGenerationPage /> },
      { path: "/content-generation/:id", element: <ContentDetailPage /> },
      {
        // 개인건강정보는 민감정보(건강정보)라 로그인이 꼭 필요하다.
        element: <RequireAuth />,
        children: [
          { path: "/health-info", element: <HealthInfoPage /> },
          { path: "/health-info/consent", element: <ConsentPage /> },
        ],
      },
    ],
  },
]);
