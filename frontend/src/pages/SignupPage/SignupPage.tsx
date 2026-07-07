import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { authApi } from "../../api/authApi";
import type { SignupPayload } from "../../api/types";

const initialForm: SignupPayload = {
  email: "",
  password: "",
  name: "",
  gender: "MALE",
  birth_date: "",
  phone_number: "",
};

/** 백엔드 SignUpRequest(app/dtos/auth.py)와 1:1 필드. 디자인 없이 "가입이 실제로 되는지"만 증명. */
export default function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<SignupPayload>(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function update<K extends keyof SignupPayload>(key: K, value: SignupPayload[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await authApi.signup(form);
      navigate("/login", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "회원가입에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 320, margin: "40px auto" }}>
      <h1>회원가입</h1>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <input
          type="email"
          placeholder="이메일"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="비밀번호 (대/소문자·숫자·특수문자 포함 8자 이상)"
          value={form.password}
          onChange={(e) => update("password", e.target.value)}
          required
        />
        <input
          type="text"
          placeholder="이름"
          value={form.name}
          onChange={(e) => update("name", e.target.value)}
          required
        />
        <select value={form.gender} onChange={(e) => update("gender", e.target.value as SignupPayload["gender"])}>
          <option value="MALE">남성</option>
          <option value="FEMALE">여성</option>
        </select>
        <input
          type="date"
          value={form.birth_date}
          onChange={(e) => update("birth_date", e.target.value)}
          required
        />
        <input
          type="tel"
          placeholder="휴대폰번호 (01012345678)"
          value={form.phone_number}
          onChange={(e) => update("phone_number", e.target.value)}
          required
        />
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "가입 중..." : "회원가입"}
        </button>
      </form>
    </div>
  );
}
