import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { authApi } from "../../api/authApi";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";

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
  fontWeight: 600,
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
      await login(email, password);
      navigate("/", { replace: true });
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
      await authApi.signup({ name: signupName, email: signupEmail, password: signupPassword });
      // 가입 성공 후 로그인 탭으로 넘기지 않고, 방금 만든 계정으로 바로 로그인시켜서 홈으로 보낸다.
      await login(signupEmail, signupPassword);
      navigate("/", { replace: true });
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
              placeholder="이메일"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={inputStyle}
              required
            />
            <input
              type="password"
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
            <p style={{ color: pinkTheme.textMuted, fontSize: 12, margin: 0 }}>
              닉네임, 이메일, 비밀번호만 있으면 바로 시작할 수 있어요. 건강정보는 나중에 입력해요.
            </p>
            <input
              type="text"
              placeholder="닉네임"
              value={signupName}
              onChange={(e) => setSignupName(e.target.value)}
              style={inputStyle}
              required
            />
            <input
              type="email"
              placeholder="이메일"
              value={signupEmail}
              onChange={(e) => setSignupEmail(e.target.value)}
              style={inputStyle}
              required
            />
            <input
              type="password"
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
      </div>
    </div>
  );
}
