import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { healthInfoApi } from "../../api/healthInfoApi";
import type { HealthInfoResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";

/** 아직 아무 건강정보도 입력하지 않은 상태인지 — 로그인 직후 입력 화면으로 보낼지 판단 기준. */
function isHealthInfoEmpty(h: HealthInfoResult): boolean {
  return (
    h.height_cm === null &&
    h.weight_kg === null &&
    h.diagnosis_history.length === 0 &&
    h.family_history.length === 0 &&
    !h.special_notes &&
    !h.other_notes
  );
}

/** 이메일+비밀번호만 있는 최소 로그인 화면. 실제로 로그인이 되는지 증명하는 게 목적, 디자인은 아직 없음. */
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
      // 온보딩: 건강정보를 아직 하나도 입력하지 않았으면 홈 대신 입력 화면부터 띄운다.
      // (조회가 실패해도 로그인 자체는 성공이므로 홈으로 보낸다.)
      let firstScreen = "/";
      try {
        if (isHealthInfoEmpty(await healthInfoApi.get())) firstScreen = "/health-info";
      } catch {
        firstScreen = "/";
      }
      navigate(firstScreen, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

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
      <p>
        계정이 없으신가요? <Link to="/signup">회원가입</Link>
      </p>
    </div>
  );
}
