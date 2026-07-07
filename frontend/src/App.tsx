/**
 * React Router 설정.
 * 5탭(홈/트랙커(복약관리 포함)/상담/정보/더보기)은 로그인해야 볼 수 있다 — RequireAuth로 감싼다.
 * /start, /login, /signup, /signup/email, /social-signup은 비로그인 상태에서만 의미 있는 공개 라우트.
 * /complete-profile, /account-settings는 로그인은 됐지만 5탭 네비게이션은 필요 없는 화면이라
 * RequireAuth 안이지만 Layout 밖에 둔다.
 */
import { createBrowserRouter } from "react-router-dom";

import AccountSettingsPage from "./pages/AccountSettingsPage/AccountSettingsPage";
import Layout from "./components/common/Layout";
import RequireAuth from "./components/common/RequireAuth";
import ChatPage from "./pages/ChatPage/ChatPage";
import CompleteProfilePage from "./pages/CompleteProfilePage/CompleteProfilePage";
import EmailSignupPage from "./pages/EmailSignupPage/EmailSignupPage";
import HomePage from "./pages/HomePage/HomePage";
import InfoPage from "./pages/InfoPage/InfoPage";
import LoginPage from "./pages/LoginPage/LoginPage";
import MorePage from "./pages/MorePage/MorePage";
import SignupPage from "./pages/SignupPage/SignupPage";
import SocialSignupPage from "./pages/SocialSignupPage/SocialSignupPage";
import StartPage from "./pages/StartPage/StartPage";
import TrackPage from "./pages/TrackPage/TrackPage";

export const router = createBrowserRouter([
  { path: "/start", element: <StartPage /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  { path: "/signup/email", element: <EmailSignupPage /> },
  { path: "/social-signup", element: <SocialSignupPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: "/complete-profile", element: <CompleteProfilePage /> },
      { path: "/account-settings", element: <AccountSettingsPage /> },
      {
        element: <Layout />,
        children: [
          { path: "/", element: <HomePage /> },
          { path: "/track", element: <TrackPage /> },
          { path: "/chat", element: <ChatPage /> },
          { path: "/info", element: <InfoPage /> },
          { path: "/more", element: <MorePage /> },
        ],
      },
    ],
  },
]);
