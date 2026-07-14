import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { healthInfoApi } from "../../api/healthInfoApi";
import type {
  Disease,
  DiagnosisEntry,
  FamilyHistoryEntry,
  FamilyRelation,
  DiseaseStatus,
  HealthInfoResult,
} from "../../api/types";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";
import { hasConsented } from "../../utils/healthInfoConsent";

import BirthDateInput from "./BirthDateInput";
import DiseaseSubtypeSearchInput from "./DiseaseSubtypeSearchInput";

/** "YYYY-MM-DD" -> {year, month, day} 문자열 3개로 쪼갠다. 캘린더 위젯 대신 칸별 입력을 쓰는 이유:
 * 옛날 생년(예: 1970년대)을 고를 때 브라우저 기본 날짜선택기는 달력을 한 달씩 눌러 넘겨야 해서
 * 너무 오래 걸린다 - 숫자 직접입력이 훨씬 빠르다. */
function splitBirthDate(birthDate: string | null): { year: string; month: string; day: string } {
  if (!birthDate) return { year: "", month: "", day: "" };
  const [year, month, day] = birthDate.split("-");
  return { year: year ?? "", month: String(Number(month) || ""), day: String(Number(day) || "") };
}

/** 년/월/일 세 칸이 전부 채워졌을 때만 "YYYY-MM-DD"로 합친다(하나라도 비었으면 undefined - 미입력 처리). */
function combineBirthDate(year: string, month: string, day: string): string | undefined {
  if (year === "" || month === "" || day === "") return undefined;
  const mm = month.padStart(2, "0");
  const dd = day.padStart(2, "0");
  return `${year}-${mm}-${dd}`;
}

/** is_pregnant(boolean | null)를 select용 문자열("", "true", "false")로 변환한다.
 * ""는 "미입력(모름)" 상태를 뜻한다 - 임신 여부는 답하기 부담스러울 수 있어 강제하지 않는다. */
function boolToSelectValue(value: boolean | null): string {
  if (value === null) return "";
  return value ? "true" : "false";
}

function selectValueToBool(value: string): boolean | undefined {
  if (value === "") return undefined;
  return value === "true";
}

const DISEASE_OPTIONS: { key: Disease; label: string }[] = [
  { key: "CANCER", label: "암" },
  { key: "HEART_DISEASE", label: "심장질환" },
  { key: "CEREBROVASCULAR_DISEASE", label: "뇌혈관질환" },
  { key: "DIABETES", label: "당뇨" },
  { key: "LIVER_DISEASE", label: "간질환" },
  { key: "OTHER", label: "기타" },
];

const STATUS_OPTIONS: { key: DiseaseStatus; label: string }[] = [
  { key: "WELL_CONTROLLED", label: "잘 조절됨" },
  { key: "MODERATE", label: "보통" },
  { key: "UNCONTROLLED", label: "조절안됨" },
  { key: "CURED", label: "완치" },
];

const RELATION_OPTIONS: { key: FamilyRelation; label: string }[] = [
  { key: "PARENT", label: "부모" },
  { key: "SIBLING", label: "형제자매" },
  { key: "GRANDPARENT", label: "조부모" },
  { key: "OTHER", label: "기타" },
];

function labelOf(key: Disease): string {
  return DISEASE_OPTIONS.find((d) => d.key === key)?.label ?? key;
}

function statusLabelOf(key: DiseaseStatus | null): string | null {
  return STATUS_OPTIONS.find((s) => s.key === key)?.label ?? null;
}

function relationLabelOf(key: FamilyRelation | null): string | null {
  return RELATION_OPTIONS.find((r) => r.key === key)?.label ?? null;
}

function diagnosisSummary(entries: DiagnosisEntry[]): string {
  if (entries.length === 0) return "없음";
  return entries
    .map((e) => {
      const name = e.disease_subtype
        ? `${labelOf(e.disease)}(${e.disease_subtype})`
        : labelOf(e.disease);
      const bits = [
        e.diagnosed_years_ago != null ? `${e.diagnosed_years_ago}년째` : null,
        statusLabelOf(e.status),
        e.on_medication ? "약물치료 중" : null,
        e.detail,
      ].filter(Boolean);
      return bits.length > 0 ? `${name} - ${bits.join(", ")}` : name;
    })
    .join(" / ");
}

function familyHistorySummary(entries: FamilyHistoryEntry[]): string {
  if (entries.length === 0) return "없음";
  return entries
    .map((e) => {
      const name = e.disease_subtype
        ? `${labelOf(e.disease)}(${e.disease_subtype})`
        : labelOf(e.disease);
      const bits = [relationLabelOf(e.relation), e.detail].filter(Boolean);
      return bits.length > 0 ? `${name} - ${bits.join(", ")}` : name;
    })
    .join(" / ");
}

/** 질병 체크박스 + "없음" 체크박스를 관리하는 공통 훅. DiagnosisEntry/FamilyHistoryEntry 둘 다
 * disease 필드를 공유하므로 제네릭으로 만들고, 항목별 나머지 필드는 makeEntry/update로 다룬다. */
function useEntrySelection<T extends { disease: Disease }>(
  initial: T[],
  makeEntry: (key: Disease) => T,
) {
  const [entries, setEntries] = useState<T[]>(initial);
  const [isNone, setIsNone] = useState(initial.length === 0);

  function isChecked(key: Disease) {
    return entries.some((e) => e.disease === key);
  }
  function get(key: Disease): T | undefined {
    return entries.find((e) => e.disease === key);
  }
  function toggle(key: Disease) {
    setIsNone(false);
    setEntries((prev) =>
      prev.some((e) => e.disease === key)
        ? prev.filter((e) => e.disease !== key)
        : [...prev, makeEntry(key)],
    );
  }
  function update(key: Disease, patch: Partial<T>) {
    setEntries((prev) => prev.map((e) => (e.disease === key ? { ...e, ...patch } : e)));
  }
  function toggleNone() {
    setIsNone((prev) => {
      const next = !prev;
      if (next) setEntries([]);
      return next;
    });
  }
  function reset(next: T[]) {
    setEntries(next);
    setIsNone(next.length === 0);
  }

  return { entries, isNone, isChecked, get, toggle, update, toggleNone, reset };
}

const smallInputStyle: React.CSSProperties = {
  padding: "6px 10px",
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: "6px",
  fontSize: 13,
};

function DiagnosisChecklist({
  selection,
}: {
  selection: ReturnType<typeof useEntrySelection<DiagnosisEntry>>;
}) {
  return (
    <div>
      <p style={{ marginBottom: 6, color: pinkTheme.text, fontWeight: 600 }}>
        진단병력 (본인이 진단받은 질환)
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {DISEASE_OPTIONS.map((d) => {
          const entry = selection.get(d.key);
          return (
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
              {entry && (
                <div
                  style={{
                    marginTop: 4,
                    marginLeft: 24,
                    width: "calc(100% - 24px)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                  }}
                >
                  <DiseaseSubtypeSearchInput
                    category={d.key}
                    value={entry.disease_subtype}
                    onChange={(v) => selection.update(d.key, { disease_subtype: v })}
                  />
                  <div style={{ display: "flex", gap: "4px" }}>
                    <input
                      type="number"
                      placeholder="진단 후 경과(년)"
                      value={entry.diagnosed_years_ago ?? ""}
                      onChange={(e) =>
                        selection.update(d.key, {
                          diagnosed_years_ago:
                            e.target.value === "" ? null : Number(e.target.value),
                        })
                      }
                      min={0}
                      max={100}
                      style={{ ...smallInputStyle, flex: 1 }}
                    />
                    <select
                      value={entry.status ?? ""}
                      onChange={(e) =>
                        selection.update(d.key, {
                          status: e.target.value === "" ? null : (e.target.value as DiseaseStatus),
                        })
                      }
                      style={{ ...smallInputStyle, flex: 1 }}
                    >
                      <option value="">조절상태 (선택)</option>
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s.key} value={s.key}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      fontSize: 13,
                      color: pinkTheme.textMuted,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={entry.on_medication ?? false}
                      onChange={(e) => selection.update(d.key, { on_medication: e.target.checked })}
                    />
                    현재 약물치료 중
                  </label>
                  <input
                    type="text"
                    placeholder="상세 메모 (선택)"
                    value={entry.detail ?? ""}
                    onChange={(e) => selection.update(d.key, { detail: e.target.value || null })}
                    maxLength={200}
                    style={smallInputStyle}
                  />
                </div>
              )}
            </div>
          );
        })}
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

function FamilyHistoryChecklist({
  selection,
}: {
  selection: ReturnType<typeof useEntrySelection<FamilyHistoryEntry>>;
}) {
  return (
    <div>
      <p style={{ marginBottom: 6, color: pinkTheme.text, fontWeight: 600 }}>
        가족력 (직계가족의 진단 이력)
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {DISEASE_OPTIONS.map((d) => {
          const entry = selection.get(d.key);
          return (
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
              {entry && (
                <div
                  style={{
                    marginTop: 4,
                    marginLeft: 24,
                    width: "calc(100% - 24px)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                  }}
                >
                  <DiseaseSubtypeSearchInput
                    category={d.key}
                    value={entry.disease_subtype}
                    onChange={(v) => selection.update(d.key, { disease_subtype: v })}
                  />
                  <select
                    value={entry.relation ?? ""}
                    onChange={(e) =>
                      selection.update(d.key, {
                        relation: e.target.value === "" ? null : (e.target.value as FamilyRelation),
                      })
                    }
                    style={smallInputStyle}
                  >
                    <option value="">관계 (선택)</option>
                    {RELATION_OPTIONS.map((r) => (
                      <option key={r.key} value={r.key}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    placeholder="상세 메모 (선택)"
                    value={entry.detail ?? ""}
                    onChange={(e) => selection.update(d.key, { detail: e.target.value || null })}
                    maxLength={200}
                    style={smallInputStyle}
                  />
                </div>
              )}
            </div>
          );
        })}
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
 * [나이 자동계산] 생일(월/일만, 연도 없음)을 같이 입력하면, 그 다음부터 매년 생일이 지날 때마다
 * 나이가 자동으로 +1 계산된다(실제 태어난 해는 여전히 안 받음).
 * - 진입 시 보기 모드(현황 요약)부터 뜨고, "수정" 눌러야 편집 폼으로 바뀐다.
 * - 키/체중을 둘 다 입력하면 BMI를 계산해서 보여준다 (백엔드가 계산해서 내려줌).
 * - 진단병력/가족력은 질환 체크박스(+ 기타) + "없음" 체크박스 + 항목별 구조화된 상세입력으로 관리한다. */
export default function HealthInfoPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [mode, setMode] = useState<Mode>("view");
  const [info, setInfo] = useState<HealthInfoResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  // 처음 불러왔을 때 이미 정보가 있었는지 - 있었다면 수정 화면에서 "뒤로가기"는 홈으로 나가지 않고
  // 그냥 보기 화면으로 돌아간다(취소랑 같은 동작). 원래부터 비어서 자동으로 입력화면에 들어온 거면
  // 홈으로 나간다.
  const [hadDataOnLoad, setHadDataOnLoad] = useState(false);

  const [birthYear, setBirthYear] = useState("");
  const [birthMonth, setBirthMonth] = useState("");
  const [birthDay, setBirthDay] = useState("");
  const [gender, setGender] = useState<"MALE" | "FEMALE">("MALE");
  // "" = 미입력(모름), "true"/"false" 문자열로 관리 - select 옵션값과 맞추기 위함.
  const [isPregnant, setIsPregnant] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [specialNotes, setSpecialNotes] = useState("");
  const [otherNotes, setOtherNotes] = useState("");
  const diagnosis = useEntrySelection<DiagnosisEntry>([], (key) => ({
    disease: key,
    disease_subtype: null,
    diagnosed_years_ago: null,
    status: null,
    on_medication: null,
    detail: null,
  }));
  const family = useEntrySelection<FamilyHistoryEntry>([], (key) => ({
    disease: key,
    disease_subtype: null,
    relation: null,
    detail: null,
  }));

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await healthInfoApi.get();
      setInfo(data);
      {
        const { year, month, day } = splitBirthDate(data.birth_date);
        setBirthYear(year);
        setBirthMonth(month);
        setBirthDay(day);
      }
      setGender(data.gender ?? "MALE");
      setIsPregnant(boolToSelectValue(data.is_pregnant));
      setWeightKg(data.weight_kg !== null ? String(data.weight_kg) : "");
      setSpecialNotes(data.special_notes ?? "");
      setOtherNotes(data.other_notes ?? "");
      diagnosis.reset(data.diagnosis_history);
      family.reset(data.family_history);

      // 아직 아무것도 입력 안 한 상태(전부 미입력)면, 보기 화면(전부 "미입력"만 나오는 표) 대신
      // 바로 입력 화면으로 들어간다. 하나라도 채워져 있으면 지금까지처럼 보기 화면부터 보여준다.
      const isEmpty =
        data.birth_date === null &&
        data.gender === null &&
        data.height_cm === null &&
        data.weight_kg === null &&
        data.diagnosis_history.length === 0 &&
        data.family_history.length === 0 &&
        !data.special_notes &&
        !data.other_notes;
      setMode(isEmpty ? "edit" : "view");
      setHadDataOnLoad(!isEmpty);
    } catch (err) {
      setError(err instanceof Error ? err.message : "정보를 불러오지 못했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!user || !hasConsented(user.email)) {
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

  // 상단 "뒤로가기" 버튼 전용. 원래 정보가 있었는데 수정하러 들어온 거면 그냥 보기 화면으로
  // 돌아가고(취소하고 보기로 돌아가기와 동일), 애초에 정보가 없어서 자동으로 입력화면에
  // 들어온 거거나 처음부터 보기 화면이었으면 홈으로 나간다.
  function handleTopBack() {
    if (mode === "edit" && hadDataOnLoad) {
      handleCancelEdit();
    } else {
      navigate("/");
    }
  }

  function handleCancelEdit() {
    if (info) {
      {
        const { year, month, day } = splitBirthDate(info.birth_date);
        setBirthYear(year);
        setBirthMonth(month);
        setBirthDay(day);
      }
      setGender(info.gender ?? "MALE");
      setIsPregnant(boolToSelectValue(info.is_pregnant));
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
        birth_date: combineBirthDate(birthYear, birthMonth, birthDay),
        gender,
        is_pregnant: selectValueToBool(isPregnant),
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
          onClick={handleTopBack}
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
                생년월일: {info.birth_date ?? "미입력"}
                {info.age !== null ? ` (만 ${info.age}세)` : ""}
              </p>
              <p style={{ margin: 0, color: pinkTheme.text }}>
                성별:{" "}
                {info.gender === "MALE" ? "남성" : info.gender === "FEMALE" ? "여성" : "미입력"}
              </p>
              {info.gender === "FEMALE" && (
                <p style={{ margin: 0, color: pinkTheme.text }}>
                  임신 여부:{" "}
                  {info.is_pregnant === true
                    ? "예"
                    : info.is_pregnant === false
                      ? "아니오"
                      : "미입력"}
                </p>
              )}
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
                {diagnosisSummary(info.diagnosis_history)}
              </p>
            </div>

            <div style={cardStyle}>
              <p style={{ fontWeight: 600, marginBottom: 4, color: pinkTheme.text }}>
                가족력 (직계가족)
              </p>
              <p style={{ margin: 0, color: pinkTheme.text }}>
                {familyHistorySummary(info.family_history)}
              </p>
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
            <div>
              <p style={{ margin: "0 0 4px", color: pinkTheme.text }}>
                생년월일 (선택 - 입력하면 만 나이가 자동으로 계산돼요)
              </p>
              <BirthDateInput
                year={birthYear}
                month={birthMonth}
                day={birthDay}
                onChange={(y, m, d) => {
                  setBirthYear(y);
                  setBirthMonth(m);
                  setBirthDay(d);
                }}
              />
            </div>

            <label
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "4px",
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

            {gender === "FEMALE" && (
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                  color: pinkTheme.text,
                }}
              >
                현재 임신 중이신가요? (선택 - 답하기 부담스러우면 비워두셔도 돼요)
                <select
                  value={isPregnant}
                  onChange={(e) => setIsPregnant(e.target.value)}
                  style={inputStyle}
                >
                  <option value="">미입력</option>
                  <option value="true">예</option>
                  <option value="false">아니오</option>
                </select>
              </label>
            )}

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

            <DiagnosisChecklist selection={diagnosis} />
            <FamilyHistoryChecklist selection={family} />

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
