/**
 * 인증 상태 공유 훅 — 로그인 여부/유저 정보만 전역 공유 (FRONTEND_ARCHITECTURE.md 6번 공통모듈).
 * 전역 상태 라이브러리는 도입하지 않고 Context 1~2개로 최소화하는 팀 방침에 따른다.
 */
import { useState } from "react";

export function useAuth() {
  const [user, setUser] = useState<{ id: string; name: string } | null>(null);
  return { user, setUser };
}
