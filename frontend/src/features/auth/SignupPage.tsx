// src/features/auth/SignupPage.tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useSignup } from "./useAuth";
import type { Gender } from "../../types/auth";
import "./auth.css";

// 약관 동의 항목들 (필요하면 여기에 항목을 추가/수정하세요)
const AGREEMENTS = [
  { key: "service", label: "[필수] 서비스 이용약관 동의", required: true },
  { key: "privacy", label: "[필수] 개인정보 수집 및 이용 동의", required: true },
  { key: "marketing", label: "[선택] 마케팅 정보 수신 동의", required: false },
];

export default function SignupPage() {
  // 1단계: 약관 동의 여부. 필수 항목을 전부 체크해야 2단계(가입 폼)로 넘어갑니다.
  const [agreements, setAgreements] = useState<Record<string, boolean>>(
    Object.fromEntries(AGREEMENTS.map((a) => [a.key, false]))
  );
  const allRequiredAgreed = AGREEMENTS.filter((a) => a.required).every((a) => agreements[a.key]);
  const allAgreed = AGREEMENTS.every((a) => agreements[a.key]);
  const [showForm, setShowForm] = useState(false);

  const toggleAgreement = (key: string) => setAgreements((prev) => ({ ...prev, [key]: !prev[key] }));
  const toggleAll = () => {
    const next = !allAgreed;
    setAgreements(Object.fromEntries(AGREEMENTS.map((a) => [a.key, next])));
  };

  // 2단계: 실제 가입 폼
  const [form, setForm] = useState({
    email: "",
    password: "",
    name: "",
    gender: "MALE" as Gender,
    birth_date: "",
    phone_number: "",
  });
  const { signup, isPending, error, isSuccess } = useSignup();

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  // [핀포인트 추가] 1단계에서 이미 필수 약관 체크를 통과해야만 이 함수가 호출되는 화면 구조라,
  // 여기 도달한 시점엔 항상 true로 보내면 됩니다. 백엔드가 이 값으로 동의 시각을 기록합니다.
  const submitSignup = () => signup({ ...form, agreed_terms: true });

  // ---------- 1단계: 약관 동의 화면 ----------
  if (!showForm) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1 className="auth-title">이용약관 동의</h1>

          <div className="auth-terms-box">
            <p className="auth-terms-text">
              서비스 이용을 위해 아래 약관에 동의해주세요. [필수] 항목에 모두 동의하셔야 회원가입을 진행할 수
              있습니다. (여기에 실제 약관/개인정보처리방침 전문을 넣으시면 됩니다.)
            </p>
          </div>

          <label className="auth-checkbox-row auth-checkbox-all">
            <input type="checkbox" checked={allAgreed} onChange={toggleAll} />
            <span>전체 동의</span>
          </label>

          <div className="auth-checkbox-list">
            {AGREEMENTS.map((a) => (
              <label key={a.key} className="auth-checkbox-row">
                <input type="checkbox" checked={agreements[a.key]} onChange={() => toggleAgreement(a.key)} />
                <span>{a.label}</span>
              </label>
            ))}
          </div>

          <button
            className="auth-submit"
            type="button"
            disabled={!allRequiredAgreed}
            onClick={() => setShowForm(true)}
          >
            동의하고 계속하기
          </button>

          <p className="auth-footer">
            이미 계정이 있으신가요? <Link to="/login">로그인</Link>
          </p>
        </div>
      </div>
    );
  }

  // ---------- 2단계: 실제 가입 폼 ----------
  return (
    <div className="auth-page">
      <form
        className="auth-card"
        onSubmit={(e) => {
          e.preventDefault();
          submitSignup();
        }}
      >
        <h1 className="auth-title">회원가입</h1>

        <button type="button" className="auth-back-link" onClick={() => setShowForm(false)}>
          ← 약관 다시 보기
        </button>

        <div className="auth-field">
          <label className="auth-label">이름</label>
          <input className="auth-input" required value={form.name} onChange={update("name")} />
        </div>

        <div className="auth-field">
          <label className="auth-label">이메일</label>
          <input className="auth-input" type="email" required value={form.email} onChange={update("email")} />
        </div>

        <div className="auth-field">
          <label className="auth-label">비밀번호</label>
          <input
            className="auth-input"
            type="password"
            required
            value={form.password}
            onChange={update("password")}
          />
          <p className="auth-hint">최소 8자, 대문자·소문자·숫자·특수문자 각 1개 이상 포함</p>
        </div>

        <div className="auth-field">
          <label className="auth-label">성별</label>
          <select className="auth-input" value={form.gender} onChange={update("gender")}>
            <option value="MALE">남성</option>
            <option value="FEMALE">여성</option>
          </select>
        </div>

        <div className="auth-field">
          <label className="auth-label">생년월일</label>
          <input
            className="auth-input"
            type="date"
            required
            value={form.birth_date}
            onChange={update("birth_date")}
          />
        </div>

        <div className="auth-field">
          <label className="auth-label">휴대폰번호</label>
          <input
            className="auth-input"
            required
            placeholder="01012345678"
            value={form.phone_number}
            onChange={update("phone_number")}
          />
          <p className="auth-hint">010-1234-5678 / 01012345678 형식</p>
        </div>

        {error && <p className="auth-error">{error}</p>}
        {isSuccess && <p className="auth-success">가입 완료! 로그인 페이지로 이동합니다.</p>}

        <button className="auth-submit" type="submit" disabled={isPending}>
          {isPending ? "가입 중..." : "회원가입"}
        </button>

        <p className="auth-footer">
          이미 계정이 있으신가요? <Link to="/login">로그인</Link>
        </p>
      </form>
    </div>
  );
}
