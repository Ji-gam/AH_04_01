import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { healthInfoApi } from "../../api/healthInfoApi";
import type { Disease, HealthInfoResult } from "../../api/types";

const DISEASE_OPTIONS: { key: Disease; label: string }[] = [
  { key: "CANCER", label: "암" },
  { key: "HEART_DISEASE", label: "심장질환" },
  { key: "CEREBROVASCULAR_DISEASE", label: "뇌혈관질환" },
  { key: "DIABETES", label: "당뇨" },
  { key: "LIVER_DISEASE", label: "간질환" },
];

function labelsOf(list: Disease[]): string {
  if (list.length === 0) return "없음";
  return DISEASE_OPTIONS.filter((d) => list.includes(d.key))
    .map((d) => d.label)
    .join(", ");
}

/** 아직 아무 건강정보도 입력하지 않은 상태인지 — 이 경우 보기 모드 없이 바로 편집 모드로 연다. */
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

function calcAge(birthday: string): number | null {
  if (!birthday) return null;
  const birth = new Date(birthday);
  if (Number.isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const hadBirthdayThisYear =
    today.getMonth() > birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() >= birth.getDate());
  if (!hadBirthdayThisYear) age -= 1;
  return age;
}

/** 질병 체크박스 5개 + "없음" 체크박스를 같이 관리하는 훅.
 * "없음"을 누르면 나머지가 전부 풀리고, 5개 중 하나라도 누르면 "없음"이 자동으로 풀린다. */
function useDiseaseSelection(initial: Disease[]) {
  const [selected, setSelected] = useState<Disease[]>(initial);
  const [isNone, setIsNone] = useState(initial.length === 0);

  function toggleDisease(key: Disease) {
    setIsNone(false);
    setSelected((prev) => (prev.includes(key) ? prev.filter((d) => d !== key) : [...prev, key]));
  }

  function toggleNone() {
    setIsNone((prev) => {
      const next = !prev;
      if (next) setSelected([]); // "없음" 체크 -> 나머지 전부 해제
      return next;
    });
  }

  function reset(next: Disease[]) {
    setSelected(next);
    setIsNone(next.length === 0);
  }

  return { selected, isNone, toggleDisease, toggleNone, reset };
}

type Mode = "view" | "edit";

/** 더보기 > 개인건강정보.
 * - 진입 시 보기 모드(현황 요약)부터 뜨고, "수정" 눌러야 편집 폼으로 바뀐다.
 * - 생년월일/성별은 조회만 되고 여기서 수정 불가 (계정 정보 수정에서만 변경).
 * - 키/체중을 둘 다 입력하면 BMI를 계산해서 보여준다 (백엔드가 계산해서 내려줌).
 * - 진단병력/가족력은 5대질환 체크박스 + "없음" 체크박스로 관리한다. */
export default function HealthInfoPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("view");
  const [info, setInfo] = useState<HealthInfoResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

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
      setHeightCm(data.height_cm !== null ? String(data.height_cm) : "");
      setWeightKg(data.weight_kg !== null ? String(data.weight_kg) : "");
      setSpecialNotes(data.special_notes ?? "");
      setOtherNotes(data.other_notes ?? "");
      diagnosis.reset(data.diagnosis_history);
      family.reset(data.family_history);
      // 아무것도 입력한 적 없으면(온보딩 등) 보기 모드 없이 바로 편집 폼부터 연다.
      if (isHealthInfoEmpty(data)) setMode("edit");
    } catch (err) {
      setError(err instanceof Error ? err.message : "정보를 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleStartEdit() {
    setError(null);
    setSavedMessage(null);
    setMode("edit");
  }

  function handleCancelEdit() {
    if (info) {
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
        height_cm: heightCm !== "" ? Number(heightCm) : undefined,
        weight_kg: weightKg !== "" ? Number(weightKg) : undefined,
        // "없음"이든 몇 개 선택했든, 매번 지금 선택 상태 그대로(빈 배열 포함) 보낸다 -
        // 그래야 체크 해제해서 "없음"으로 되돌리는 것도 실제로 반영된다.
        diagnosis_history: diagnosis.selected,
        family_history: family.selected,
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
        <p style={{ color: "red" }}>{error ?? "정보를 불러오지 못했습니다."}</p>
        <button type="button" onClick={load}>
          다시 시도
        </button>
      </div>
    );
  }

  const age = calcAge(info.birthday);

  return (
    <div style={{ maxWidth: 360, margin: "40px auto" }}>
      <button
        type="button"
        onClick={() => navigate("/more")}
        style={{
          background: "none",
          border: "none",
          color: "#555",
          padding: 0,
          marginBottom: 8,
          cursor: "pointer",
        }}
      >
        ← 뒤로가기
      </button>

      <h1>개인건강정보</h1>

      {/* 생년월일/성별은 항상 보기 전용 - 이 화면에서 못 고침 */}
      <div style={{ display: "flex", gap: "16px", color: "#555", fontSize: 14, marginBottom: 16 }}>
        <span>
          생년월일: {info.birthday} {age !== null && `(만 ${age}세)`}
        </span>
        <span>성별: {info.gender === "MALE" ? "남성" : "여성"}</span>
      </div>

      {savedMessage && <p style={{ color: "green" }}>{savedMessage}</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}

      {mode === "view" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
            <p style={{ fontWeight: "bold", marginBottom: 4 }}>키/체중/BMI</p>
            <p style={{ margin: 0 }}>
              키: {info.height_cm !== null ? `${info.height_cm} cm` : "미입력"}
            </p>
            <p style={{ margin: 0 }}>
              체중: {info.weight_kg !== null ? `${info.weight_kg} kg` : "미입력"}
            </p>
            <p style={{ margin: "8px 0 0", fontWeight: "bold" }}>
              BMI: {info.bmi !== null ? info.bmi : "키/체중을 모두 입력하면 계산돼요"}
            </p>
          </div>

          <div>
            <p style={{ fontWeight: "bold", marginBottom: 4 }}>진단병력 (본인)</p>
            <p style={{ margin: 0 }}>{labelsOf(info.diagnosis_history)}</p>
          </div>

          <div>
            <p style={{ fontWeight: "bold", marginBottom: 4 }}>가족력 (직계가족)</p>
            <p style={{ margin: 0 }}>{labelsOf(info.family_history)}</p>
          </div>

          <div>
            <p style={{ fontWeight: "bold", marginBottom: 4 }}>특이사항</p>
            <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{info.special_notes || "미입력"}</p>
          </div>

          <div>
            <p style={{ fontWeight: "bold", marginBottom: 4 }}>기타</p>
            <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{info.other_notes || "미입력"}</p>
          </div>

          <button type="button" onClick={handleStartEdit}>
            수정
          </button>
        </div>
      ) : (
        <form
          onSubmit={handleSave}
          style={{ display: "flex", flexDirection: "column", gap: "16px" }}
        >
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
            <p style={{ marginBottom: 4 }}>진단병력 (본인이 진단받은 질환)</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              {DISEASE_OPTIONS.map((d) => (
                <label key={d.key} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <input
                    type="checkbox"
                    checked={diagnosis.selected.includes(d.key)}
                    onChange={() => diagnosis.toggleDisease(d.key)}
                  />
                  {d.label}
                </label>
              ))}
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  borderTop: "1px solid #eee",
                  paddingTop: 4,
                }}
              >
                <input type="checkbox" checked={diagnosis.isNone} onChange={diagnosis.toggleNone} />
                없음
              </label>
            </div>
          </div>

          <div>
            <p style={{ marginBottom: 4 }}>가족력 (직계가족의 진단 이력)</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              {DISEASE_OPTIONS.map((d) => (
                <label key={d.key} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <input
                    type="checkbox"
                    checked={family.selected.includes(d.key)}
                    onChange={() => family.toggleDisease(d.key)}
                  />
                  {d.label}
                </label>
              ))}
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  borderTop: "1px solid #eee",
                  paddingTop: 4,
                }}
              >
                <input type="checkbox" checked={family.isNone} onChange={family.toggleNone} />
                없음
              </label>
            </div>
          </div>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            특이사항 (알레르기, 복용 중인 약 등)
            <textarea
              rows={3}
              maxLength={1000}
              value={specialNotes}
              onChange={(e) => setSpecialNotes(e.target.value)}
              style={{ resize: "vertical", fontFamily: "inherit" }}
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            기타
            <textarea
              rows={3}
              maxLength={1000}
              value={otherNotes}
              onChange={(e) => setOtherNotes(e.target.value)}
              style={{ resize: "vertical", fontFamily: "inherit" }}
            />
          </label>

          <button type="submit" disabled={isSaving}>
            {isSaving ? "저장 중..." : "저장하기"}
          </button>
          <button
            type="button"
            onClick={handleCancelEdit}
            style={{ background: "none", border: "none", color: "#888" }}
          >
            취소하고 보기로 돌아가기
          </button>
        </form>
      )}
    </div>
  );
}
