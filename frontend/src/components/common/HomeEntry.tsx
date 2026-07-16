import { useState } from "react";

import { useAuth } from "../../hooks/useAuth";
import HomePage from "../../pages/HomePage/HomePage";
import OnboardingPage from "../../pages/OnboardingPage/OnboardingPage";

const ONBOARDING_SEEN_KEY = "remedi_onboarding_seen";

/** "/" 진입점 게이트(2026-07-16) - 비로그인 + 이번 세션에 아직 온보딩을 안 봤으면 온보딩부터
 * 보여주고, 로그인 상태거나 이미 봤으면 곧장 HomePage를 보여준다. sessionStorage 플래그라
 * 새 탭/새로고침(로그아웃 상태)에서는 다시 보이고, 로그인 중엔 절대 안 보인다 - 회원가입도
 * 가입 즉시 로그인 처리라 가입 후에는 isAuthenticated가 true가 되어 자연히 안 보인다. */
export default function HomeEntry() {
  const { isAuthenticated, isLoading } = useAuth();
  const [seen, setSeen] = useState(() => sessionStorage.getItem(ONBOARDING_SEEN_KEY) === "1");

  if (isLoading) {
    return <p>로딩 중...</p>;
  }

  if (!isAuthenticated && !seen) {
    return (
      <OnboardingPage
        onFinish={() => {
          sessionStorage.setItem(ONBOARDING_SEEN_KEY, "1");
          setSeen(true);
        }}
      />
    );
  }

  return <HomePage />;
}
