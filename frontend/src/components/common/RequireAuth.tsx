import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";

/** 로그인 안 했으면 /login으로 튕기는 가드. 5탭 라우트를 이걸로 감싼다.
 *
 * [2026-07-28] 회원가입 시 한 화면에서 받는 통합 동의(이용약관/건강정보/AI챗봇 필수,
 * 마케팅 선택)를 아직 안 마쳤으면 /health-info/consent로 보낸다 - 소셜/이메일 가입
 * 직후 LoginPage에서도 보내지만, 세션이 남아있는 상태로 새로고침하는 경우(로그인
 * 페이지를 안 거치는 경우)까지 여기서 한 번 더 확인한다. 그 페이지 자체는 무한
 * 리다이렉트를 막기 위해 이 체크에서 제외한다.
 *
 * [버그 수정] 계정설정(/account-settings)처럼 건강정보/동의와 무관한 화면까지 이
 * 체크에 걸려서, 마이그레이션 이전 계정(통합 동의 3종이 아직 비어있는 기존
 * 테스트 계정)이 "계정관리"를 눌러도 계속 동의 화면으로 튕기기만 하고 실제
 * 설정 화면엔 못 들어가는 문제가 있었다 - `skipConsentCheck`로 그 라우트만
 * 이 체크를 건너뛰게 한다(로그인 여부 확인은 그대로 함). */
export default function RequireAuth({ skipConsentCheck = false }: { skipConsentCheck?: boolean }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <p>로딩 중...</p>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  const consentDone =
    !!user?.terms_of_service_consented_at && !!user?.health_info_consented_at && !!user?.ai_chat_consented_at;
  if (!skipConsentCheck && !consentDone && location.pathname !== "/health-info/consent") {
    return <Navigate to="/health-info/consent" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
