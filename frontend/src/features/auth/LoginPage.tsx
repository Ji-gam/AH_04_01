// src/features/auth/LoginPage.tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useLogin } from "./useAuth";
import { authApi } from "../../api/endpoints/auth";
import "./auth.css";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { login, isPending, error } = useLogin();

  return (
    <div className="auth-page">
      <form
        className="auth-card"
        onSubmit={(e) => {
          e.preventDefault();
          login({ email, password });
        }}
      >
        <h1 className="auth-title">로그인</h1>

        <div className="auth-field">
          <label className="auth-label">이메일</label>
          <input
            className="auth-input"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div className="auth-field">
          <label className="auth-label">비밀번호</label>
          <input
            className="auth-input"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && <p className="auth-error">{error}</p>}

        <button className="auth-submit" type="submit" disabled={isPending}>
          {isPending ? "로그인 중..." : "로그인"}
        </button>

        <p className="auth-footer">
          계정이 없으신가요? <Link to="/signup">회원가입</Link>
        </p>

        <p className="auth-divider">또는</p>
        <div className="auth-social-list">
          <a className="auth-social-btn" href={authApi.socialLoginUrl("google")}>
            구글로 로그인
          </a>
          <a className="auth-social-btn" href={authApi.socialLoginUrl("naver")}>
            네이버로 로그인
          </a>
          <a className="auth-social-btn" href={authApi.socialLoginUrl("kakao")}>
            카카오로 로그인
          </a>
        </div>
      </form>
    </div>
  );
}
