import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { authApi, socialLoginUrl } from "../../api/authApi";
import type { UserInfoResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";

/** 카톡/메모앱 등에서 비밀번호를 복사해 붙여넣을 때, 화면엔 안 보이지만 같이 딸려오는
 * 줄바꿈/앞뒤 공백/zero-width 문자를 제거한다. 가입 때 타이핑으로 넣고 로그인 때 복붙으로
 * 넣으면(혹은 반대) 육안으로는 똑같아 보여도 실제 문자열이 달라 해시가 안 맞는 문제를 막는다.
 * client.ts의 accessToken 방어(줄바꿈/공백 제거)와 같은 이유. */
export function sanitizeCredential(value: string): string {
  return value.replace(/[\u200B-\u200D\uFEFF]/g, "").trim();
}

/** (2026-07-28) 회원가입 시 한 화면에서 받는 통합 동의 - 이용약관/건강정보/AI챗봇은 필수,
 * 마케팅은 선택이라 여기 체크에서 뺀다. RequireAuth.tsx와 동일한 기준. */
function consentIncomplete(me: UserInfoResult): boolean {
  return !me.terms_of_service_consented_at || !me.health_info_consented_at || !me.ai_chat_consented_at;
}

type Tab = "login" | "signup";

const inputStyle: React.CSSProperties = {
  padding: "12px 14px",
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: "10px",
  fontSize: "14px",
  outline: "none",
};

const primaryButtonStyle: React.CSSProperties = {
  padding: "12px",
  border: "none",
  borderRadius: "10px",
  background: pinkTheme.primary,
  color: "#fff",
  fontWeight: 700,
  cursor: "pointer",
};

/** 시작화면(홈)의 "로그인" 버튼으로 들어오는 화면. 로그인/가입을 탭으로 전환한다(별도 페이지 이동 없이).
 * [가입 최소화] 가입 탭은 닉네임+이메일+비밀번호만 받는다 - 성별/나이/휴대폰번호는 로그인 후
 * 더보기 > 개인건강정보에서 입력받는다. */
export default function LoginPage() {
  const [tab, setTab] = useState<Tab>("login");
  const { login } = useAuth();
  const navigate = useNavigate();

  // 로그인 폼
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // 가입 폼
  const [signupName, setSignupName] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [signupError, setSignupError] = useState<string | null>(null);
  const [isSigningUp, setIsSigningUp] = useState(false);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setLoginError(null);
    setIsLoggingIn(true);
    try {
      const me = await login(sanitizeCredential(email), sanitizeCredential(password));
      navigate(consentIncomplete(me) ? "/health-info/consent" : "/", { replace: true });
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    } finally {
      setIsLoggingIn(false);
    }
  }

  async function handleSignup(e: FormEvent) {
    e.preventDefault();
    setSignupError(null);
    setIsSigningUp(true);
    try {
      const cleanEmail = sanitizeCredential(signupEmail);
      const cleanPassword = sanitizeCredential(signupPassword);
      await authApi.signup({ name: signupName, email: cleanEmail, password: cleanPassword });
      // 가입 성공 후 로그인 탭으로 넘기지 않고, 방금 만든 계정으로 바로 로그인시켜서 홈으로 보낸다.
      // [2026-07-28] 신규 가입자는 통합 동의(이용약관/건강정보/AI챗봇)를 아직 안 거쳤으니
      // 무조건 그 화면부터 보낸다.
      const me = await login(cleanEmail, cleanPassword);
      navigate(consentIncomplete(me) ? "/health-info/consent" : "/", { replace: true });
    } catch (err) {
      setSignupError(err instanceof Error ? err.message : "회원가입에 실패했습니다.");
    } finally {
      setIsSigningUp(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100dvh",
        background: pinkTheme.pageBg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 340,
          background: pinkTheme.cardBg,
          borderRadius: "16px",
          border: `1px solid ${pinkTheme.border}`,
          padding: "24px",
          boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
        }}
      >
        <div
          style={{
            display: "flex",
            marginBottom: "20px",
            borderBottom: `1px solid ${pinkTheme.border}`,
          }}
        >
          <button
            type="button"
            onClick={() => setTab("login")}
            style={{
              flex: 1,
              padding: "10px",
              border: "none",
              background: "none",
              cursor: "pointer",
              fontWeight: tab === "login" ? 700 : 400,
              color: tab === "login" ? pinkTheme.primary : pinkTheme.textMuted,
              borderBottom:
                tab === "login" ? `2px solid ${pinkTheme.primary}` : "2px solid transparent",
            }}
          >
            로그인
          </button>
          <button
            type="button"
            onClick={() => setTab("signup")}
            style={{
              flex: 1,
              padding: "10px",
              border: "none",
              background: "none",
              cursor: "pointer",
              fontWeight: tab === "signup" ? 700 : 400,
              color: tab === "signup" ? pinkTheme.primary : pinkTheme.textMuted,
              borderBottom:
                tab === "signup" ? `2px solid ${pinkTheme.primary}` : "2px solid transparent",
            }}
          >
            가입
          </button>
        </div>

        {tab === "login" ? (
          <form
            onSubmit={handleLogin}
            style={{ display: "flex", flexDirection: "column", gap: "10px" }}
          >
            <input
              type="email"
              name="email"
              autoComplete="username"
              placeholder="이메일"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={inputStyle}
              required
            />
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              placeholder="비밀번호"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={inputStyle}
              required
            />
            {loginError && <p style={{ color: pinkTheme.danger, fontSize: 13 }}>{loginError}</p>}
            <button type="submit" disabled={isLoggingIn} style={primaryButtonStyle}>
              {isLoggingIn ? "로그인 중..." : "로그인"}
            </button>
          </form>
        ) : (
          <form
            onSubmit={handleSignup}
            style={{ display: "flex", flexDirection: "column", gap: "10px" }}
          >
            <p style={{ color: pinkTheme.textMuted, fontSize: 13, margin: 0 }}>
              닉네임, 이메일, 비밀번호만 있으면 바로 시작할 수 있어요. 건강정보는 나중에 입력해요.
            </p>
            <input
              type="text"
              name="nickname"
              autoComplete="off"
              placeholder="닉네임"
              value={signupName}
              onChange={(e) => setSignupName(e.target.value)}
              style={inputStyle}
              required
            />
            <input
              type="email"
              name="new-email"
              autoComplete="email"
              placeholder="이메일"
              value={signupEmail}
              onChange={(e) => setSignupEmail(e.target.value)}
              style={inputStyle}
              required
            />
            <input
              type="password"
              name="new-password"
              autoComplete="new-password"
              placeholder="비밀번호 (소문자·숫자·특수문자 포함 8자 이상)"
              value={signupPassword}
              onChange={(e) => setSignupPassword(e.target.value)}
              style={inputStyle}
              required
            />
            {signupError && <p style={{ color: pinkTheme.danger, fontSize: 13 }}>{signupError}</p>}
            <button type="submit" disabled={isSigningUp} style={primaryButtonStyle}>
              {isSigningUp ? "가입 중..." : "가입하기"}
            </button>
          </form>
        )}

        <p
          style={{
            textAlign: "center",
            color: pinkTheme.textMuted,
            fontSize: 13,
            margin: "16px 0 8px",
          }}
        >
          또는
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {/* 구글은 카카오/네이버처럼 브랜드컬러로 꽉 채운 공식 버튼이 없다(로고 자체가 다색이라
             단일색 배경 버튼을 공식으로 안 만듦) - 그래서 구글이 제공하는 3가지 공식 테마
             (Light/Neutral/Dark) 중 Dark를 써서 진한 배경 + 컬러 G 아이콘으로 통일감을 맞춘다. */}
          <a
            href={socialLoginUrl("google")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "10px",
              height: "44px",
              borderRadius: "10px",
              background: "#131314",
              textDecoration: "none",
              color: "#fff",
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            <img src="/icons/google-icon-dark.png" alt="" style={{ width: 20, height: 20 }} />
            구글 로그인
          </a>
          {/* 네이버/카카오는 한글 라벨까지 이미 박혀있는 공식 완성형 버튼 이미지를 그대로 쓴다 -
             자체 배경/모서리가 이미 있는 완성된 이미지라 우리 쪽 테두리를 안 덧씌운다. 카드 폭에 맞춰
             꽉 채우되(width:100%), 이미지 원래 비율은 그대로 유지한다(늘리기/찌그러뜨리기 없음). */}
          <a
            href={socialLoginUrl("naver")}
            style={{ display: "block", borderRadius: "10px", overflow: "hidden", lineHeight: 0 }}
          >
            <img
              src="/icons/naver-button-ko.png"
              alt="네이버 로그인"
              style={{ width: "100%", display: "block" }}
            />
          </a>
          <a
            href={socialLoginUrl("kakao")}
            style={{ display: "block", borderRadius: "10px", overflow: "hidden", lineHeight: 0 }}
          >
            <img
              src="/icons/kakao-button-ko.png"
              alt="카카오 로그인"
              style={{ width: "100%", display: "block" }}
            />
          </a>
        </div>
      </div>
    </div>
  );
}
