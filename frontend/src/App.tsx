/**
 * React Router 설정.
 * [변경] 홈이 시작화면 - 로그인 안 해도 접근 가능하다. 개인건강정보는 개인정보라 로그인이 꼭 필요하고,
 * 복약 관리(/medication)도 비로그인 상태에서 복약정보를 등록할 수 있는 문제가 있어 로그인을 다시
 * 요구하게 되돌렸다. 나머지 탭(트랙커/상담/정보/복약알림/스케줄/더보기)은 로그인 안 해도 기본적으로
 * 볼 수 있게 열어둔다. /login 하나로 로그인/가입을 다 처리한다(SignupPage 별도 라우트 없음).
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
import DataConsentPage from "./pages/DataConsentPage/DataConsentPage";
import DurScreeningPage from "./pages/dur/DurScreeningPage";
import EmergencyGuidePage from "./pages/EmergencyGuidePage/EmergencyGuidePage";
import HabitSelectionPage from "./pages/HabitSelectionPage/HabitSelectionPage";
import HealthInfoPage from "./pages/HealthInfoPage/HealthInfoPage";
import HomePage from "./pages/HomePage/HomePage";
import InfoPage from "./pages/InfoPage/InfoPage";
import LifestyleInfoPage from "./pages/LifestyleInfoPage/LifestyleInfoPage";
import LoginPage from "./pages/LoginPage/LoginPage";
import MedicationPage from "./pages/medication/MedicationPage";
import MorePage from "./pages/MorePage/MorePage";
import NotificationSettingsPage from "./pages/NotificationSettingsPage/NotificationSettingsPage";
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
      { path: "/chat", element: <ChatPage /> },
      { path: "/info", element: <InfoPage /> },
      { path: "/more", element: <MorePage /> },
      { path: "/lifestyle-info", element: <LifestyleInfoPage /> },
      { path: "/notification-settings", element: <NotificationSettingsPage /> },
      { path: "/data-consent", element: <DataConsentPage /> },
      { path: "/content-generation", element: <ContentGenerationPage /> },
      { path: "/content-generation/:id", element: <ContentDetailPage /> },
      { path: "/emergency-guide", element: <EmergencyGuidePage /> },
      // DUR 스크리닝(T-MED-14)은 profile_id를 안 쓰는 공개 API라 로그인 불필요.
      { path: "/dur-screening", element: <DurScreeningPage /> },
      {
        // 개인건강정보(민감정보)와 복약 관리(비로그인 상태로 복약정보 등록이 가능했던 문제)는
        // 로그인이 꼭 필요하다.
        element: <RequireAuth />,
        children: [
          { path: "/health-info", element: <HealthInfoPage /> },
          { path: "/health-info/consent", element: <ConsentPage /> },
          { path: "/medication", element: <MedicationPage /> },
          { path: "/habit-selection", element: <HabitSelectionPage /> },
        ],
      },
    ],
  },
]);
