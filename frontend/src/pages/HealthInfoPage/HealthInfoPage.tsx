import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { healthInfoApi } from "../../api/healthInfoApi";
import type { Disease, DiseaseEntry, HealthInfoResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";
import { hasConsented } from "../../utils/healthInfoConsent";

const DISEASE_OPTIONS: { key: Disease; label: string }[] = [
  { key: "CANCER", label: "암" },
  { key: "HEART_DISEASE", label: "심장질환" },
  { key: "CEREBROVASCULAR_DISEASE", label: "뇌혈관질환" },
  { key: "DIABETES", label: "당뇨" },
  { key: "LIVER_DISEASE", label: "간질환" },
  { key: "OTHER", label: "기타" },
];

function labelOf(key: Disease): string {
  return DISEASE_OPTIONS.find((d) => d.key === key)?.label ?? key;
}

function summaryOf(entries: DiseaseEntry[]): string {
  if (entries.length === 0) return "없음";
  return entries
    .map((e) => (e.detail ? `${labelOf(e.disease)}(${e.detail})` : labelOf(e.disease)))
    .join(", ");
}

/** 질병 체크박스 + "없음" 체크박스 + 항목별 상세입력을 같이 관리하는 훅.
 * "없음"을 누르면 나머지가 전부 풀리고, 하나라도 체크하면 "없음"이 자동으로 풀린다. */
function useDiseaseSelection(initial: DiseaseEntry[]) {
  const [entries, setEntries] = useState<DiseaseEntry[]>(initial);
  const [isNone, setIsNone] = useState(initial.length === 0);

  function isChecked(key: Disease) {
    return entries.some((e) => e.disease === key);
  }
  function detailOf(key: Disease) {
    return entries.find((e) => e.disease === key)?.detail ?? "";
  }
  function toggle(key: Disease) {
    setIsNone(false);
    setEntries((prev) =>
      prev.some((e) => e.disease === key)
        ? prev.filter((e) => e.disease !== key)
        : [...prev, { disease: key, detail: null }],
    );
  }
  function setDetail(key: Disease, detail: string) {
    setEntries((prev) =>
      prev.map((e) => (e.disease === key ? { ...e, detail: detail === "" ? null : detail } : e)),
    );
  }
  function toggleNone() {
    setIsNone((prev) => {
      const next = !prev;
      if (next) setEntries([]);
      return next;
    });
  }
  function reset(next: DiseaseEntry[]) {
    setEntries(next);
    setIsNone(next.length === 0);
  }

  return { entries, isNone, isChecked, detailOf, toggle, setDetail, toggleNone, reset };
}

function DiseaseChecklist({
  title,
  selection,
}: {
  title: string;
  selection: ReturnType<typeof useDiseaseSelection>;
}) {
  return (
    <div>
      <p style={{ marginBottom: 6, color: pinkTheme.text, fontWeight: 600 }}>{title}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {DISEASE_OPTIONS.map((d) => (
          <div key={d.key}>
            <label
              style={{ display: "flex", alignItems: "center", gap: "8px", color: pinkTheme.text }}
            >
              <input
                type="checkbox"
                checked={selection.isChecked(d.key)}
                onChange={() => selection.toggle(d.key)}
              />
              {d.label}
            </label>
            {selection.isChecked(d.key) && (
              <input
                type="text"
                placeholder="상세 메모 (선택)"
                value={selection.detailOf(d.key)}
                onChange={(e) => selection.setDetail(d.key, e.target.value)}
                maxLength={200}
                style={{
                  marginTop: 4,
                  marginLeft: 24,
                  width: "calc(100% - 24px)",
                  padding: "6px 10px",
                  border: `1px solid ${pinkTheme.border}`,
                  borderRadius: "6px",
                  fontSize: 13,
                }}
              />
            )}
          </div>
        ))}
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            borderTop: `1px solid ${pinkTheme.border}`,
            paddingTop: 6,
            color: pinkTheme.textMuted,
          }}
        >
          <input type="checkbox" checked={selection.isNone} onChange={selection.toggleNone} />
          없음
        </label>
      </div>
    </div>
  );
}

type Mode = "view" | "edit";

const cardStyle: React.CSSProperties = {
  background: pinkTheme.cardBg,
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: "12px",
  padding: "16px",
};

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: "8px",
  fontSize: 14,
};

/** 더보기 > 개인건강정보.
 * [변경] 가입 시 나이/성별을 안 받게 되어, 이 화면이 나이/성별을 처음 입력받는 곳이 됐다(편집 가능).
 * - 진입 시 보기 모드(현황 요약)부터 뜨고, "수정" 눌러야 편집 폼으로 바뀐다.
 * - 키/체중을 둘 다 입력하면 BMI를 계산해서 보여준다 (백엔드가 계산해서 내려줌).
 * - 진단병력/가족력은 질환 체크박스(+ 기타) + "없음" 체크박스 + 항목별 상세입력으로 관리한다. */
export default function HealthInfoPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [mode, setMode] = useState<Mode>("view");
  const [info, setInfo] = useState<HealthInfoResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const [age, setAge] = useState("");
  const [gender, setGender] = useState<"MALE" | "FEMALE">("MALE");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [specialNotes, setSpecialNotes] = useState("");
  const [otherNotes, setOtherNotes] = useState("");
  const diagnosis = useDiseaseSelection([]);
  const family = useDiseaseSelection([]);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await healthInfoApi.get();
      setInfo(data);
      setAge(data.age !== null ? String(data.age) : "");
      setGender(data.gender ?? "MALE");
      setHeightCm(data.height_cm !== null ? String(data.height_cm) : "");
      setWeightKg(data.weight_kg !== null ? String(data.weight_kg) : "");
      setSpecialNotes(data.special_notes ?? "");
      setOtherNotes(data.other_notes ?? "");
      diagnosis.reset(data.diagnosis_history);
      family.reset(data.family_history);

      // 아직 아무것도 입력 안 한 상태(전부 미입력)면, 보기 화면(전부 "미입력"만 나오는 표) 대신
      // 바로 입력 화면으로 들어간다. 하나라도 채워져 있으면 지금까지처럼 보기 화면부터 보여준다.
      const isEmpty =
        data.age === null &&
        data.gender === null &&
        data.height_cm === null &&
        data.weight_kg === null &&
        data.diagnosis_history.length === 0 &&
        data.family_history.length === 0 &&
        !data.special_notes &&
        !data.other_notes;
      setMode(isEmpty ? "edit" : "view");
    } catch (err) {
      setError(err instanceof Error ? err.message : "정보를 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!user || !hasConsented(user.profile_id)) {
      // 홈 배너를 거치지 않고 더보기 등에서 바로 들어온 경우 - 동의화면부터 거치게 한다.
      navigate("/health-info/consent", { replace: true });
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  function handleStartEdit() {
    setError(null);
    setSavedMessage(null);
    setMode("edit");
  }

  function handleCancelEdit() {
    if (info) {
      setAge(info.age !== null ? String(info.age) : "");
      setGender(info.gender ?? "MALE");
      setHeightCm(info.height_cm !== null ? String(info.height_cm) : "");
      setWeightKg(info.weight_kg !== null ? String(info.weight_kg) : "");
      setSpecialNotes(info.special_notes ?? "");
      setOtherNotes(info.other_notes ?? "");
      diagnosis.reset(info.diagnosis_history);
      family.reset(info.family_history);
    }
    setError(null);
    setMode("view");
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSavedMessage(null);
    setIsSaving(true);
    try {
      const updated = await healthInfoApi.update({
        age: age !== "" ? Number(age) : undefined,
        gender,
        height_cm: heightCm !== "" ? Number(heightCm) : undefined,
        weight_kg: weightKg !== "" ? Number(weightKg) : undefined,
        // "없음"이든 몇 개 선택했든, 매번 지금 선택 상태 그대로(빈 배열 포함) 보낸다 -
        // 그래야 체크 해제해서 "없음"으로 되돌리는 것도 실제로 반영된다.
        diagnosis_history: diagnosis.entries,
        family_history: family.entries,
        special_notes: specialNotes,
        other_notes: otherNotes,
      });
      setInfo(updated);
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

  if (!info) {
    return (
      <div style={{ maxWidth: 320, margin: "40px auto" }}>
        <p style={{ color: pinkTheme.danger }}>{error ?? "정보를 불러오지 못했습니다."}</p>
        <button type="button" onClick={load}>
          다시 시도
        </button>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100%", background: pinkTheme.pageBg, padding: "20px" }}>
      <div style={{ maxWidth: 400, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate("/more")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            marginBottom: 12,
            cursor: "pointer",
          }}
        >
          ← 뒤로가기
        </button>

        <h1 style={{ color: pinkTheme.text, fontSize: 20 }}>개인건강정보</h1>

        {savedMessage && <p style={{ color: pinkTheme.success }}>{savedMessage}</p>}
        {error && <p style={{ color: pinkTheme.danger }}>{error}</p>}

        {mode === "view" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={cardStyle}>
              <p style={{ margin: 0, color: pinkTheme.text }}>
                나이: {info.age !== null ? `${info.age}세` : "미입력"}
              </p>
              <p style={{ margin: 0, color: pinkTheme.text }}>
                성별:{" "}
                {info.gender === "MALE" ? "남성" : info.gender === "FEMALE" ? "여성" : "미입력"}
              </p>
            </div>

            <div style={cardStyle}>
              <p style={{ fontWeight: 600, marginBottom: 4, color: pinkTheme.text }}>키/체중/BMI</p>
              <p style={{ margin: 0, color: pinkTheme.text }}>
                키: {info.height_cm !== null ? `${info.height_cm} cm` : "미입력"}
              </p>
              <p style={{ margin: 0, color: pinkTheme.text }}>
                체중: {info.weight_kg !== null ? `${info.weight_kg} kg` : "미입력"}
              </p>
              <p style={{ margin: "8px 0 0", fontWeight: 600, color: pinkTheme.primary }}>
                BMI: {info.bmi !== null ? info.bmi : "키/체중을 모두 입력하면 계산돼요"}
              </p>
            </div>

            <div style={cardStyle}>
              <p style={{ fontWeight: 600, marginBottom: 4, color: pinkTheme.text }}>
                진단병력 (본인)
              </p>
              <p style={{ margin: 0, color: pinkTheme.text }}>
                {summaryOf(info.diagnosis_history)}
              </p>
            </div>

            <div style={cardStyle}>
              <p style={{ fontWeight: 600, marginBottom: 4, color: pinkTheme.text }}>
                가족력 (직계가족)
              </p>
              <p style={{ margin: 0, color: pinkTheme.text }}>{summaryOf(info.family_history)}</p>
            </div>

            <div style={cardStyle}>
              <p style={{ fontWeight: 600, marginBottom: 4, color: pinkTheme.text }}>특이사항</p>
              <p style={{ margin: 0, whiteSpace: "pre-wrap", color: pinkTheme.text }}>
                {info.special_notes || "미입력"}
              </p>
            </div>

            <div style={cardStyle}>
              <p style={{ fontWeight: 600, marginBottom: 4, color: pinkTheme.text }}>기타</p>
              <p style={{ margin: 0, whiteSpace: "pre-wrap", color: pinkTheme.text }}>
                {info.other_notes || "미입력"}
              </p>
            </div>

            <button
              type="button"
              onClick={handleStartEdit}
              style={{
                padding: "12px",
                border: "none",
                borderRadius: "10px",
                background: pinkTheme.primary,
                color: "#fff",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              수정
            </button>
          </div>
        ) : (
          <form
            onSubmit={handleSave}
            style={{ display: "flex", flexDirection: "column", gap: "16px" }}
          >
            <div style={{ display: "flex", gap: "8px" }}>
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                  flex: 1,
                  color: pinkTheme.text,
                }}
              >
                나이
                <input
                  type="number"
                  placeholder="예: 35"
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  style={inputStyle}
                />
              </label>
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                  flex: 1,
                  color: pinkTheme.text,
                }}
              >
                성별
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value as "MALE" | "FEMALE")}
                  style={inputStyle}
                >
                  <option value="MALE">남성</option>
                  <option value="FEMALE">여성</option>
                </select>
              </label>
            </div>

            <label
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                color: pinkTheme.text,
              }}
            >
              키 (cm)
              <input
                type="number"
                step="0.1"
                placeholder="예: 170.5"
                value={heightCm}
                onChange={(e) => setHeightCm(e.target.value)}
                style={inputStyle}
              />
            </label>
            <label
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                color: pinkTheme.text,
              }}
            >
              체중 (kg)
              <input
                type="number"
                step="0.1"
                placeholder="예: 65.2"
                value={weightKg}
                onChange={(e) => setWeightKg(e.target.value)}
                style={inputStyle}
              />
            </label>

            <DiseaseChecklist title="진단병력 (본인이 진단받은 질환)" selection={diagnosis} />
            <DiseaseChecklist title="가족력 (직계가족의 진단 이력)" selection={family} />

            <label
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                color: pinkTheme.text,
              }}
            >
              특이사항 (알레르기, 복용 중인 약 등)
              <textarea
                rows={3}
                maxLength={1000}
                value={specialNotes}
                onChange={(e) => setSpecialNotes(e.target.value)}
                style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }}
              />
            </label>

            <label
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                color: pinkTheme.text,
              }}
            >
              기타
              <textarea
                rows={3}
                maxLength={1000}
                value={otherNotes}
                onChange={(e) => setOtherNotes(e.target.value)}
                style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }}
              />
            </label>

            <button
              type="submit"
              disabled={isSaving}
              style={{
                padding: "12px",
                border: "none",
                borderRadius: "10px",
                background: pinkTheme.primary,
                color: "#fff",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {isSaving ? "저장 중..." : "저장하기"}
            </button>
            <button
              type="button"
              onClick={handleCancelEdit}
              style={{
                background: "none",
                border: "none",
                color: pinkTheme.textMuted,
                cursor: "pointer",
              }}
            >
              취소하고 보기로 돌아가기
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
