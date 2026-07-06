// src/features/auth/LoginPage.tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useLogin } from "./useAuth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate({ email, password });
        }}
        className="w-full max-w-sm rounded-2xl border p-8"
        style={{ background: "var(--panel-bg)", borderColor: "var(--panel-border)" }}
      >
        <h1 className="mb-6 text-2xl font-bold">로그인</h1>

        <label className="mb-1 block text-sm" style={{ color: "var(--text-secondary)" }}>
          이메일
        </label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded-lg border bg-transparent px-3 py-2 outline-none"
          style={{ borderColor: "var(--panel-border)" }}
        />

        <label className="mb-1 block text-sm" style={{ color: "var(--text-secondary)" }}>
          비밀번호
        </label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-6 w-full rounded-lg border bg-transparent px-3 py-2 outline-none"
          style={{ borderColor: "var(--panel-border)" }}
        />

        {login.isError && (
          <p className="mb-4 text-sm" style={{ color: "var(--accent-pink)" }}>
            이메일 또는 비밀번호가 일치하지 않습니다.
          </p>
        )}

        <button
          type="submit"
          disabled={login.isPending}
          className="w-full rounded-lg py-2 font-semibold text-black"
          style={{ background: "var(--accent-cyan)" }}
        >
          {login.isPending ? "로그인 중..." : "로그인"}
        </button>

        <p className="mt-4 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
          계정이 없으신가요? <Link to="/signup" className="underline">회원가입</Link>
        </p>

        {/* TODO(조원 구현): Google 소셜 로그인 버튼. 백엔드 auth 도메인에 OAuth 콜백 라우트부터 추가 필요 */}
      </form>
    </div>
  );
}
