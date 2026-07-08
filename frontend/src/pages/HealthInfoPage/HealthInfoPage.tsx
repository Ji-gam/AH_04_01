import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { userApi } from "../../api/userApi";
import { authApi } from "../../api/authApi";
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

function labelsOf(list: Disease[]): string {
  if (list.length === 0) return "없음";
  return DISEASE_OPTIONS.filter((d) => list.includes(d.key))
    .map((d) => d.label)
    .join(", ");
}

type TabKey = "basic" | "history" | "etc";

const TABS: { key: TabKey; label: string }[] = [
  { key: "basic", label: "키/체중" },
  { key: "history", label: "질병이력" },
  { key: "etc", label: "기타" },
];

type ViewMode = "view" | "edit";

/** 더보기 > 개인건강관리.
 * - 진입하면 지금까지 저장된 값을 한눈에 볼 수 있는 "보기 모드"가 먼저 뜬다.
 * - "수정" 버튼을 눌러야 탭별 입력 폼(편집 모드)으로 전환된다 - 실수로 잘못 눌러 바로
 *   수정 화면으로 들어가는 걸 막기 위함.
 * - 편집 모드에서도 탭별로 독립적으로 저장할 수 있고, 저장하면 다시 보기 모드로 돌아온다.
 * - 상단에 "뒤로가기"를 둬서 잘못 들어왔을 때 더보기로 바로 나갈 수 있게 한다. */
export default function HealthInfoPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<ViewMode>("view");
  const [activeTab, setActiveTab] = useState<TabKey>("basic");

  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [diagnosisHistory, setDiagnosisHistory] = useState<Disease[]>([]);
  const [familyHistory, setFamilyHistory] = useState<Disease[]>([]);
  const [healthNotes, setHealthNotes] = useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const me = await authApi.me();
        setHeightCm(me.height_cm !== null ? String(me.height_cm) : "");
        setWeightKg(me.weight_kg !== null ? String(me.weight_kg) : "");
        setDiagnosisHistory(me.diagnosis_history);
        setFamilyHistory(me.family_history);
        setHealthNotes(me.health_notes ?? "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "정보를 불러오지 못했습니다.");
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  function handleBack() {
    navigate("/more");
  }

  function handleStartEdit() {
    setError(null);
    setSavedMessage(null);
    setMode("edit");
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSavedMessage(null);
    setIsSaving(true);
    try {
      if (activeTab === "basic") {
        await userApi.updateBiometricInfo({
          ...(heightCm !== "" ? { height_cm: Number(heightCm) } : {}),
          ...(weightKg !== "" ? { weight_kg: Number(weightKg) } : {}),
        });
      } else if (activeTab === "history") {
        await userApi.updateBiometricInfo({
          diagnosis_history: diagnosisHistory,
          family_history: familyHistory,
        });
      } else {
        await userApi.updateBiometricInfo({ health_notes: healthNotes });
      }
      // 저장 후엔 편집 모드에서 나와서, 방금 반영된 내용을 보기 모드로 바로 확인시켜준다.
      setMode("view");
      setSavedMessage("저장되었습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return <p style={{ textAlign: "center", marginTop: 80 }}>불러오는 중...</p>;
  }

  return (
    <div style={{ maxWidth: 320, margin: "40px auto" }}>
      <button
        type="button"
        onClick={handleBack}
        style={{ background: "none", border: "none", color: "#555", padding: 0, marginBottom: 8, cursor: "pointer" }}
      >
        ← 뒤로가기
      </button>

      <h1>개인건강관리</h1>
      <p style={{ color: "#888", fontSize: 14 }}>
        키/체중, 질병이력, 기타 메모를 관리해요. 개인정보(이름/연락처 등) 수정은{" "}
        <b>계정 설정</b>에서 따로 하실 수 있어요.
      </p>

      {savedMessage && <p style={{ color: "green" }}>{savedMessage}</p>}

      {mode === "view" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: 16 }}>
          <div>
            <p style={{ fontWeight: "bold", marginBottom: 4 }}>키/체중</p>
            <p style={{ margin: 0, color: "#333" }}>키: {heightCm !== "" ? `${heightCm} cm` : "미입력"}</p>
            <p style={{ margin: 0, color: "#333" }}>체중: {weightKg !== "" ? `${weightKg} kg` : "미입력"}</p>
          </div>

          <div>
            <p style={{ fontWeight: "bold", marginBottom: 4 }}>질병이력</p>
            <p style={{ margin: 0, color: "#333" }}>진단받은 질환: {labelsOf(diagnosisHistory)}</p>
            <p style={{ margin: 0, color: "#333" }}>가족력: {labelsOf(familyHistory)}</p>
          </div>

          <div>
            <p style={{ fontWeight: "bold", marginBottom: 4 }}>기타</p>
            <p style={{ margin: 0, color: "#333", whiteSpace: "pre-wrap" }}>
              {healthNotes.trim() !== "" ? healthNotes : "미입력"}
            </p>
          </div>

          {error && <p style={{ color: "red" }}>{error}</p>}

          <button type="button" onClick={handleStartEdit}>
            수정
          </button>
        </div>
      ) : (
        <>
          <div style={{ display: "flex", borderBottom: "1px solid #ccc", margin: "16px 0" }}>
            {TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => {
                  setActiveTab(tab.key);
                  setSavedMessage(null);
                  setError(null);
                }}
                style={{
                  flex: 1,
                  padding: "8px",
                  border: "none",
                  borderBottom: activeTab === tab.key ? "2px solid #ff6b35" : "2px solid transparent",
                  background: "none",
                  fontWeight: activeTab === tab.key ? "bold" : "normal",
                  color: activeTab === tab.key ? "#ff6b35" : "#555",
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {activeTab === "basic" && (
              <>
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
              </>
            )}

            {activeTab === "history" && (
              <>
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
              </>
            )}

            {activeTab === "etc" && (
              <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                기타 (복용 중인 영양제, 알레르기, 특이사항 등 자유롭게 적어주세요)
                <textarea
                  rows={6}
                  maxLength={1000}
                  value={healthNotes}
                  onChange={(e) => setHealthNotes(e.target.value)}
                  style={{ resize: "vertical", fontFamily: "inherit" }}
                />
                <span style={{ fontSize: 12, color: "#888", textAlign: "right" }}>{healthNotes.length}/1000</span>
              </label>
            )}

            {error && <p style={{ color: "red" }}>{error}</p>}

            <button type="submit" disabled={isSaving}>
              {isSaving ? "저장 중..." : "저장하기"}
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("view");
                setError(null);
                setSavedMessage(null);
              }}
              style={{ background: "none", border: "none", color: "#888" }}
            >
              취소하고 보기로 돌아가기
            </button>
          </form>
        </>
      )}
    </div>
  );
}
