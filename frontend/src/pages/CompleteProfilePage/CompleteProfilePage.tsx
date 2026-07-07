import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { userApi } from "../../api/userApi";
import type { Disease } from "../../api/types";

const DISEASE_OPTIONS: { key: Disease; label: string }[] = [
  { key: "CANCER", label: "암" },
  { key: "HEART_DISEASE", label: "심장질환" },
  { key: "CEREBROVASCULAR_DISEASE", label: "뇌혈관질환" },
  { key: "DIABETES", label: "당뇨" },
  { key: "LIVER_DISEASE", label: "간질환" },
];

function toggle(list: Disease[], key: Disease): Disease[] {
  return list.includes(key) ? list.filter((d) => d !== key) : [...list, key];
}

/** [T-PROFILE-1] 회원가입(이메일/소셜 공통) 직후 자동 로그인된 상태로 오는 화면.
 * 전부 선택 입력이라 "건너뛰기"로 바로 홈에 갈 수 있다 - 나중에 마이페이지 등에서 다시 채울 수 있다. */
export default function CompleteProfilePage() {
  const navigate = useNavigate();

  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [diagnosisHistory, setDiagnosisHistory] = useState<Disease[]>([]);
  const [familyHistory, setFamilyHistory] = useState<Disease[]>([]);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function handleSkip() {
    navigate("/", { replace: true });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await userApi.updateBiometricInfo({
        ...(heightCm !== "" ? { height_cm: Number(heightCm) } : {}),
        ...(weightKg !== "" ? { weight_kg: Number(weightKg) } : {}),
        diagnosis_history: diagnosisHistory,
        family_history: familyHistory,
      });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 320, margin: "40px auto" }}>
      <h1>건강 정보 입력</h1>
      <p style={{ color: "#888", fontSize: 14 }}>
        더 정확한 맞춤 정보를 위한 선택 입력이에요. 지금 안 채우셔도 나중에 다시 입력할 수 있어요.
      </p>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: 16 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          키 (cm)
          <input
            type="number"
            step="0.1"
            placeholder="예: 170.5"
            value={heightCm}
            onChange={(e) => setHeightCm(e.target.value)}
          />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          체중 (kg)
          <input
            type="number"
            step="0.1"
            placeholder="예: 65.2"
            value={weightKg}
            onChange={(e) => setWeightKg(e.target.value)}
          />
        </label>

        <div>
          <p style={{ marginBottom: 4 }}>진단받은 질환이 있다면 선택해주세요</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {DISEASE_OPTIONS.map((d) => (
              <label key={d.key} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <input
                  type="checkbox"
                  checked={diagnosisHistory.includes(d.key)}
                  onChange={() => setDiagnosisHistory((prev) => toggle(prev, d.key))}
                />
                {d.label}
              </label>
            ))}
          </div>
        </div>

        <div>
          <p style={{ marginBottom: 4 }}>가족(직계) 중 해당 질환 병력이 있다면 선택해주세요</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {DISEASE_OPTIONS.map((d) => (
              <label key={d.key} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <input
                  type="checkbox"
                  checked={familyHistory.includes(d.key)}
                  onChange={() => setFamilyHistory((prev) => toggle(prev, d.key))}
                />
                {d.label}
              </label>
            ))}
          </div>
        </div>

        {error && <p style={{ color: "red" }}>{error}</p>}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "저장 중..." : "저장하고 계속하기"}
        </button>
        <button type="button" onClick={handleSkip} style={{ background: "none", border: "none", color: "#888" }}>
          나중에 할게요 (건너뛰기)
        </button>
      </form>
    </div>
  );
}
