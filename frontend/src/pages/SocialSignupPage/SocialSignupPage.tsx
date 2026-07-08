import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import type { AgreementPayload } from "../../api/types";

function usePendingSignupParams() {
  const [params] = useSearchParams();
  return {
    pendingToken: params.get("pending_token"),
    provider: (params.get("provider") ?? "").toLowerCase(),
    email: params.get("email") ?? "",
    name: params.get("name") ?? "",
  };
}

const REQUIRED_AGREEMENTS: { key: keyof AgreementPayload; label: string }[] = [
  { key: "service_terms", label: "[필수] 서비스 이용약관 동의" },
  { key: "privacy", label: "[필수] 개인정보 수집이용 동의" },
  { key: "sensitive_info", label: "[필수] 민감정보(건강정보) 수집이용 동의" },
];

/** 생년월일 문자열(YYYY-MM-DD)로 만 나이를 계산한다. 값이 없거나 형식이 이상하면 null. */
function calcAge(birthDate: string): number | null {
  if (!birthDate) return null;
  const birth = new Date(birthDate);
  if (Number.isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const hasHadBirthdayThisYear =
    today.getMonth() > birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() >= birth.getDate());
  if (!hasHadBirthdayThisYear) age -= 1;
  return age;
}

/** [T-AUTH-7] 소셜 가입 완료 화면. 이메일 가입과 동일하게 1단계 약관동의(먼저) -> 2단계
 * 정보입력(이름/이메일은 소셜에서 받은 값으로 이미 채워져 있어 성별/생년월일/휴대폰번호만 받음)
 * 순서로 분리한다 - 이메일 가입 플로우와 단계 구조를 통일했다.
 * [건강정보는 여기서 받지 않는다 - 가입 완료 후 바로 홈으로 이동하고,
 *  건강정보는 더보기 > 개인건강관리(/health-info)에서 별도로 입력한다] */
export default function SocialSignupPage() {
  const { pendingToken, provider, email, name: providerName } = usePendingSignupParams();
  const { completeSocialSignup } = useAuth();
  const navigate = useNavigate();

  const [agreements, setAgreements] = useState<AgreementPayload>({
    service_terms: false,
    privacy: false,
    sensitive_info: false,
    marketing: false,
  });
  const [showForm, setShowForm] = useState(false);
  const allRequiredAgreed = REQUIRED_AGREEMENTS.every((a) => agreements[a.key]);

  const [name, setName] = useState(providerName);
  const [gender, setGender] = useState<"MALE" | "FEMALE" | "">("");
  const [birthDate, setBirthDate] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const allRequiredFieldsFilled = name.trim() !== "" && gender !== "" && birthDate !== "" && phoneNumber.trim() !== "";

  if (!pendingToken) {
    return (
      <div style={{ maxWidth: 320, margin: "80px auto", textAlign: "center" }}>
        <p>잘못된 접근입니다. 로그인 화면에서 다시 시도해주세요.</p>
      </div>
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!allRequiredFieldsFilled || isSubmitting) return; // [누락항목 가드]

    setError(null);
    setIsSubmitting(true);
    try {
      await completeSocialSignup(provider, {
        pending_token: pendingToken!,
        name,
        gender: gender as "MALE" | "FEMALE",
        birth_date: birthDate,
        phone_number: phoneNumber,
        agreements,
      });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "가입 완료 처리 중 오류가 발생했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  // 1단계: 약관 동의 (이메일 가입과 동일한 순서 - 먼저 동의부터)
  if (!showForm) {
    return (
      <div style={{ maxWidth: 320, margin: "40px auto" }}>
        <h1>이용약관 동의</h1>
        <p style={{ color: "#888", fontSize: 14 }}>
          {provider ? provider.toUpperCase() : "소셜"} 계정{email ? `(${email})` : ""}으로 가입합니다.
        </p>
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
          서비스 이용을 위해 아래 약관에 동의해주세요. [필수] 항목에 모두 동의하셔야 가입을 진행할 수 있습니다.
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

  // 2단계: 나머지 정보 입력 (이름/이메일은 소셜에서 이미 받음 - 이름은 수정 가능하게 기본값으로 채움)
  return (
    <div style={{ maxWidth: 320, margin: "40px auto" }}>
      <h1>추가 정보 입력</h1>
      <button type="button" onClick={() => setShowForm(false)} style={{ marginBottom: 8 }}>
        ← 약관 다시 보기
      </button>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <input type="text" placeholder="이름" value={name} onChange={(e) => setName(e.target.value)} required />
        <select value={gender} onChange={(e) => setGender(e.target.value as "MALE" | "FEMALE" | "")} required>
          <option value="">성별 선택</option>
          <option value="MALE">남성</option>
          <option value="FEMALE">여성</option>
        </select>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          생년월일
          <input
            type="date"
            value={birthDate}
            onChange={(e) => setBirthDate(e.target.value)}
            required
            aria-label="생년월일"
          />
          {calcAge(birthDate) !== null && <span style={{ fontSize: 12, color: "#888" }}>만 {calcAge(birthDate)}세</span>}
        </label>
        <input
          type="tel"
          placeholder="휴대폰번호 (01012345678)"
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(e.target.value)}
          required
        />
        {error && <p style={{ color: "red" }}>{error}</p>}
        {/* [누락항목 가드] 정보 미입력 시 버튼 자체가 비활성화된다 */}
        <button type="submit" disabled={!allRequiredFieldsFilled || isSubmitting}>
          {isSubmitting ? "처리 중..." : "가입 완료"}
        </button>
        {!allRequiredFieldsFilled && (
          <p style={{ color: "#c0392b", fontSize: 13 }}>이름/성별/생년월일/휴대폰번호를 모두 입력해주세요.</p>
        )}
      </form>
    </div>
  );
}
