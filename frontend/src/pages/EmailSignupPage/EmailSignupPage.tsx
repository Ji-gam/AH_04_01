import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../../api/authApi";
import { useAuth } from "../../hooks/useAuth";
import type { AgreementPayload, SignupPayload } from "../../api/types";

const initialForm: SignupPayload = {
  email: "",
  password: "",
  name: "",
  gender: "MALE",
  birth_date: "",
  phone_number: "",
  agreements: { service_terms: false, privacy: false, sensitive_info: false, marketing: false },
};

const REQUIRED_AGREEMENTS: { key: keyof AgreementPayload; label: string }[] = [
  { key: "service_terms", label: "[필수] 서비스 이용약관 동의" },
  { key: "privacy", label: "[필수] 개인정보 수집이용 동의" },
  { key: "sensitive_info", label: "[필수] 민감정보(건강정보) 수집이용 동의" },
];

/** 이메일 회원가입: 1단계 약관동의(먼저!) -> 2단계 이메일/이름 포함 전체 정보 입력.
 * "동의 먼저, 수집은 그다음" 순서를 지키기 위해 약관 화면이 항상 먼저 온다. */
export default function EmailSignupPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [agreements, setAgreements] = useState<AgreementPayload>({
    service_terms: false,
    privacy: false,
    sensitive_info: false,
    marketing: false,
  });
  const [showForm, setShowForm] = useState(false);
  const allRequiredAgreed = REQUIRED_AGREEMENTS.every((a) => agreements[a.key]);

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
      await authApi.signup({ ...form, agreements });
      // [자동로그인] 가입 직후 다시 로그인 화면으로 보내는 대신, 방금 입력한 자격증명으로
      // 바로 로그인시키고 "건강 정보 입력(생체정보)" 화면으로 이어준다.
      await login(form.email, form.password);
      navigate("/complete-profile", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "회원가입에 실패했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!showForm) {
    return (
      <div style={{ maxWidth: 320, margin: "40px auto" }}>
        <h1>이용약관 동의</h1>
        <div
          style={{
            border: "1px solid #ccc",
            padding: "12px",
            maxHeight: 140,
            overflowY: "auto",
            fontSize: 13,
            color: "#555",
          }}
        >
          서비스 이용을 위해 아래 약관에 동의해주세요. [필수] 항목에 모두 동의하셔야 회원가입을 진행할 수 있습니다.
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", margin: "12px 0" }}>
          {REQUIRED_AGREEMENTS.map((a) => (
            <label key={a.key} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <input
                type="checkbox"
                checked={agreements[a.key]}
                onChange={() => setAgreements((prev) => ({ ...prev, [a.key]: !prev[a.key] }))}
              />
              {a.label}
            </label>
          ))}
          <label style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <input
              type="checkbox"
              checked={agreements.marketing}
              onChange={() => setAgreements((prev) => ({ ...prev, marketing: !prev.marketing }))}
            />
            [선택] 마케팅 정보 수신 동의
          </label>
        </div>
        <button type="button" disabled={!allRequiredAgreed} onClick={() => setShowForm(true)} style={{ width: "100%" }}>
          동의하고 계속하기
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 320, margin: "40px auto" }}>
      <h1>회원가입</h1>
      <button type="button" onClick={() => setShowForm(false)} style={{ marginBottom: 8 }}>
        ← 약관 다시 보기
      </button>
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
        <input type="date" value={form.birth_date} onChange={(e) => update("birth_date", e.target.value)} required />
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
      <p style={{ textAlign: "center", marginTop: 16 }}>
        <Link to="/signup">← 다른 방법으로 가입하기</Link>
      </p>
    </div>
  );
}
