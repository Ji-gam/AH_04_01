import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

const BACKEND_BASE_URL = "http://localhost:8000";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const socialButtonStyle = {
    textAlign: "center" as const,
    padding: "8px",
    border: "1px solid #ccc",
    textDecoration: "none",
    color: "#000",
    display: "block",
  };

  return (
    <div style={{ maxWidth: 320, margin: "80px auto" }}>
      <h1>로그인</h1>
      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", flexDirection: "column", gap: "8px" }}
      >
        <input
          type="email"
          placeholder="이메일"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="비밀번호"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "로그인 중..." : "로그인"}
        </button>
      </form>

      <p style={{ textAlign: "center", color: "#888", margin: "16px 0 8px" }}>또는</p>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <a href={`${BACKEND_BASE_URL}/api/v1/auth/google/login`} style={socialButtonStyle}>
          구글로 로그인
        </a>
        <a href={`${BACKEND_BASE_URL}/api/v1/auth/naver/login`} style={socialButtonStyle}>
          네이버로 로그인
        </a>
        <a href={`${BACKEND_BASE_URL}/api/v1/auth/kakao/login`} style={socialButtonStyle}>
          카카오로 로그인
        </a>
      </div>

      <p>
        계정이 없으신가요? <Link to="/signup">회원가입</Link>
      </p>
    </div>
  );
}
