import { useEffect, useState } from "react";

import { goalApi } from "../../api/goalApi";
import type { GoalItemResult, GoalType } from "../../api/types";
import { pinkTheme as t } from "../../theme/pinkTheme";

const cardStyle: React.CSSProperties = {
  background: t.cardBg,
  border: `1px solid ${t.border}`,
  borderRadius: 16,
  padding: 16,
  marginBottom: 14,
  boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "8px 10px",
  marginBottom: 8,
  border: `1.5px solid ${t.border}`,
  borderRadius: 10,
  fontSize: 13,
  outline: "none",
};

/** 목표 하나를 담는 카드 - 달성 여부에 따라 톤이 바뀐다(달성 시 success 톤). */
function goalCardStyle(isAchieved: boolean): React.CSSProperties {
  return {
    border: `1px solid ${isAchieved ? t.success : t.border}`,
    borderRadius: 14,
    padding: 16,
    background: t.cardBg,
    boxShadow: `0 2px 8px ${isAchieved ? "rgba(123, 198, 154, 0.1)" : "rgba(255, 111, 145, 0.08)"}`,
  };
}

/** 마감까지 며칠 남았는지 - 지났으면 "N일 지남", 오늘이면 "오늘 마감". */
function daysLeftLabel(endDate: string): string {
  const end = new Date(`${endDate}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((end.getTime() - today.getTime()) / 86_400_000);
  if (days > 0) return `${days}일 남음`;
  if (days === 0) return "오늘 마감";
  return `${Math.abs(days)}일 지남`;
}

interface FormState {
  title: string;
  goalType: GoalType;
  startValue: string;
  targetValue: string;
  currentValue: string;
  unit: string;
  startDate: string;
  endDate: string;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyForm(): FormState {
  return {
    title: "",
    goalType: "NUMERIC",
    startValue: "",
    targetValue: "",
    currentValue: "",
    unit: "",
    startDate: todayIso(),
    endDate: "",
  };
}

function toFormState(goal: GoalItemResult): FormState {
  return {
    title: goal.title,
    goalType: goal.goal_type,
    startValue: goal.start_value !== null ? String(goal.start_value) : "",
    targetValue: goal.target_value !== null ? String(goal.target_value) : "",
    currentValue: goal.current_value !== null ? String(goal.current_value) : "",
    unit: goal.unit ?? "",
    startDate: goal.start_date,
    endDate: goal.end_date,
  };
}

function toNumberOrUndefined(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  const value = Number(trimmed);
  return Number.isNaN(value) ? undefined : value;
}

/** 마이다이어리 > "🎯 목표 설정" 모달 본문(F-GOAL-1 목표 CRUD + F-GOAL-2 AI 가이드). 관심
 * 질병 등록은 이미 HealthInfoPage의 진단 이력 칩이 하고 있어 여기서는 다루지 않고, 순수
 * 수치 목표(체중감량 등)만 다룬다. 저장/수정하면 서버가 AI로 맞춤 가이드를 같이
 * 생성해서 내려주므로(수 초 소요), 저장 버튼에 "가이드 생성 중..." 로딩 문구를 보여준다. */
export default function GoalContent() {
  const [goals, setGoals] = useState<GoalItemResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // "오늘 기록하기" - 목표 정의 수정과 별개로, 하루 수치만 빠르게 남기는 입력.
  // 기본 화면에선 "현재 수치 / 기록하기" 버튼만 보이고, 버튼을 누른 목표 하나만 인라인
  // 입력행으로 펼쳐진다(activeLogId) - 목표 카드를 늘 입력창으로 채우지 않기 위함.
  const [activeLogId, setActiveLogId] = useState<number | null>(null);
  const [logText, setLogText] = useState<Record<number, string>>({});
  const [loggingGoalId, setLoggingGoalId] = useState<number | null>(null);
  const [logError, setLogError] = useState<Record<number, string>>({});

  useEffect(() => {
    goalApi
      .list()
      .then((result) => setGoals(result.goals))
      .catch(() => setError("목표를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  function openCreateForm() {
    setEditingId(null);
    setForm(emptyForm());
    setFormError(null);
    setShowForm(true);
  }

  function openEditForm(goal: GoalItemResult) {
    setEditingId(goal.id);
    setForm(toFormState(goal));
    setFormError(null);
    setShowForm(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.endDate) {
      setFormError("목표명과 종료일은 필수예요.");
      return;
    }
    const isFrequency = form.goalType === "FREQUENCY";
    if (isFrequency && !form.targetValue.trim()) {
      setFormError("목표 횟수를 입력해주세요.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      // 횟수형은 "시작/현재 수치" 입력칸을 안 보여주고 항상 0에서 시작한다 - "오늘 완료"를
      // 누를 때마다 current_value가 1씩 늘어난다(handleFrequencyComplete 참고).
      const sharedFields = {
        title: form.title.trim(),
        start_value: isFrequency ? 0 : toNumberOrUndefined(form.startValue),
        target_value: toNumberOrUndefined(form.targetValue),
        current_value: isFrequency ? 0 : toNumberOrUndefined(form.currentValue),
        unit: form.unit.trim() || undefined,
        start_date: form.startDate,
        end_date: form.endDate,
      };
      const saved =
        editingId !== null
          ? await goalApi.update(editingId, sharedFields)
          : await goalApi.create({ ...sharedFields, goal_type: form.goalType });
      setGoals((prev) =>
        editingId !== null ? prev.map((g) => (g.id === saved.id ? saved : g)) : [...prev, saved],
      );
      setShowForm(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(goalId: number) {
    if (!window.confirm("이 목표를 삭제할까요?")) return;
    try {
      await goalApi.remove(goalId);
      setGoals((prev) => prev.filter((g) => g.id !== goalId));
    } catch {
      // 삭제 실패는 조용히 무시 - 목록이 그대로 남으니 다시 시도할 수 있다.
    }
  }

  async function handleLogProgress(goalId: number) {
    const raw = logText[goalId] ?? "";
    const value = Number(raw);
    if (!raw.trim() || Number.isNaN(value)) {
      setLogError((prev) => ({ ...prev, [goalId]: "숫자를 입력해주세요." }));
      return;
    }
    setLoggingGoalId(goalId);
    setLogError((prev) => ({ ...prev, [goalId]: "" }));
    try {
      const updated = await goalApi.logProgress(goalId, { value });
      setGoals((prev) => prev.map((g) => (g.id === goalId ? updated : g)));
      setLogText((prev) => ({ ...prev, [goalId]: "" }));
      setActiveLogId(null);
    } catch (err) {
      setLogError((prev) => ({
        ...prev,
        [goalId]: err instanceof Error ? err.message : "기록 중 오류가 발생했습니다.",
      }));
    } finally {
      setLoggingGoalId(null);
    }
  }

  /** FREQUENCY(횟수형) 전용 - 숫자를 직접 안 받고 "오늘 완료" 한 번으로 current_value를
   * 1 늘린다. 같은 날 중복 완료를 막기 위해, 오늘 날짜 기록이 이미 있으면 버튼을 비활성화한다
   * (isLoggedToday, 카드 렌더링 쪽 참고). */
  async function handleFrequencyComplete(goal: GoalItemResult) {
    setLoggingGoalId(goal.id);
    setLogError((prev) => ({ ...prev, [goal.id]: "" }));
    try {
      const updated = await goalApi.logProgress(goal.id, { value: (goal.current_value ?? 0) + 1 });
      setGoals((prev) => prev.map((g) => (g.id === goal.id ? updated : g)));
    } catch (err) {
      setLogError((prev) => ({
        ...prev,
        [goal.id]: err instanceof Error ? err.message : "기록 중 오류가 발생했습니다.",
      }));
    } finally {
      setLoggingGoalId(null);
    }
  }

  return (
    <div style={cardStyle}>
      <p style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 700, color: t.primary }}>
        🎯 목표 설정
      </p>

      {loading && <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>}
      {error && <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>}

      {!showForm && (
        <button
          type="button"
          onClick={openCreateForm}
          style={{
            width: "100%",
            padding: "14px 0",
            marginBottom: 16,
            border: "none",
            borderRadius: 12,
            background: `linear-gradient(135deg, ${t.primary} 0%, ${t.primaryHover} 100%)`,
            color: "#fff",
            fontSize: 15,
            fontWeight: 700,
            cursor: "pointer",
            boxShadow: "0 4px 12px rgba(255, 111, 145, 0.3)",
          }}
        >
          + 새 목표 생성
        </button>
      )}

      {showForm && (
        <form
          onSubmit={handleSubmit}
          style={{
            border: `1.5px dashed ${t.border}`,
            borderRadius: 12,
            padding: 12,
            marginBottom: 16,
          }}
        >
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
            placeholder="목표명 (예: 3kg 감량하기)"
            style={inputStyle}
          />

          {/* 목표 종류 - 생성 후에는 바꿀 수 없어서 수정 화면에서는 안 보여준다 */}
          {editingId === null && (
            <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
              {(
                [
                  { key: "NUMERIC" as const, label: "수치형 (예: 체중감량)" },
                  { key: "FREQUENCY" as const, label: "횟수형 (예: 운동하기)" },
                ]
              ).map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setForm((prev) => ({ ...prev, goalType: opt.key }))}
                  style={{
                    flex: 1,
                    padding: "8px 6px",
                    borderRadius: 10,
                    border: `1.5px solid ${form.goalType === opt.key ? t.primary : t.border}`,
                    background: form.goalType === opt.key ? t.primarySoft : t.cardBg,
                    color: form.goalType === opt.key ? t.primary : t.textMuted,
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}

          {form.goalType === "NUMERIC" ? (
            <div style={{ display: "flex", gap: 6 }}>
              <input
                type="number"
                value={form.startValue}
                onChange={(e) => setForm((prev) => ({ ...prev, startValue: e.target.value }))}
                placeholder="시작 수치(예: 68)"
                style={inputStyle}
              />
              <input
                type="number"
                value={form.targetValue}
                onChange={(e) => setForm((prev) => ({ ...prev, targetValue: e.target.value }))}
                placeholder="목표 수치(예: 65)"
                style={inputStyle}
              />
            </div>
          ) : (
            <input
              type="number"
              value={form.targetValue}
              onChange={(e) => setForm((prev) => ({ ...prev, targetValue: e.target.value }))}
              placeholder="목표 횟수(예: 3) - 0에서 시작해 '오늘 완료'를 누를 때마다 1씩 늘어나요"
              style={inputStyle}
            />
          )}
          <div style={{ display: "flex", gap: 6 }}>
            {form.goalType === "NUMERIC" && (
              <input
                type="number"
                value={form.currentValue}
                onChange={(e) => setForm((prev) => ({ ...prev, currentValue: e.target.value }))}
                placeholder="현재 수치(선택, 비우면 시작값)"
                style={inputStyle}
              />
            )}
            <input
              type="text"
              value={form.unit}
              onChange={(e) => setForm((prev) => ({ ...prev, unit: e.target.value }))}
              placeholder={form.goalType === "NUMERIC" ? "단위(예: kg)" : "단위(예: 회)"}
              style={inputStyle}
            />
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <input
              type="date"
              value={form.startDate}
              onChange={(e) => setForm((prev) => ({ ...prev, startDate: e.target.value }))}
              style={inputStyle}
            />
            <input
              type="date"
              value={form.endDate}
              onChange={(e) => setForm((prev) => ({ ...prev, endDate: e.target.value }))}
              style={inputStyle}
            />
          </div>

          {formError && (
            <p style={{ color: t.danger, fontSize: 12.5, margin: "0 0 8px" }}>{formError}</p>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="submit"
              disabled={saving}
              style={{
                flex: 1,
                padding: "10px 0",
                border: "none",
                borderRadius: 10,
                background: t.primary,
                color: "#fff",
                fontSize: 13,
                fontWeight: 700,
                cursor: saving ? "default" : "pointer",
              }}
            >
              {saving ? "저장 중... (AI 가이드 생성 중)" : "저장"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              disabled={saving}
              style={{
                padding: "10px 16px",
                borderRadius: 10,
                border: `1px solid ${t.border}`,
                background: t.cardBg,
                color: t.textMuted,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              취소
            </button>
          </div>
        </form>
      )}

      {!loading && goals.length === 0 && !showForm && (
        <div style={{ textAlign: "center", padding: "32px 12px" }}>
          <p style={{ fontSize: 32, margin: "0 0 8px" }}>🎯</p>
          <p style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 700, color: t.text }}>
            아직 등록한 목표가 없어요
          </p>
          <p style={{ margin: 0, fontSize: 12.5, color: t.textMuted }}>
            "+ 새 목표 생성"으로 첫 목표를 만들고 AI 가이드를 받아보세요.
          </p>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {goals.map((goal) => {
          const progressPct =
            goal.progress_rate !== null ? Math.round(goal.progress_rate * 100) : null;
          const hasRange = goal.start_value !== null && goal.target_value !== null;
          const isLogging = activeLogId === goal.id;
          const isFrequency = goal.goal_type === "FREQUENCY";
          const isLoggedToday = goal.recent_logs.some((log) => log.log_date === todayIso());
          return (
            <div key={goal.id} style={goalCardStyle(goal.is_achieved)}>
              {/* 헤더: 제목 + 수정/삭제 */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 8,
                  marginBottom: 4,
                }}
              >
                <strong style={{ fontSize: 16, fontWeight: 600, color: t.text }}>
                  {goal.title}
                </strong>
                <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                  <button
                    type="button"
                    onClick={() => openEditForm(goal)}
                    aria-label="목표 수정"
                    style={{ border: "none", background: "transparent", cursor: "pointer", fontSize: 15 }}
                  >
                    ✏️
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(goal.id)}
                    aria-label="목표 삭제"
                    style={{ border: "none", background: "transparent", cursor: "pointer", fontSize: 15 }}
                  >
                    🗑️
                  </button>
                </div>
              </div>

              {/* 서브타이틀: 수치범위(있으면) 또는 기간, 남은 일수 */}
              <p style={{ margin: "0 0 12px", fontSize: 12, color: t.textMuted }}>
                {hasRange
                  ? `${goal.start_value}${goal.unit ?? ""} → ${goal.target_value}${goal.unit ?? ""} (${daysLeftLabel(goal.end_date)})`
                  : `${goal.start_date} ~ ${goal.end_date} (${daysLeftLabel(goal.end_date)})`}
              </p>

              {/* 진행률 */}
              {progressPct !== null && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: t.textMuted, fontWeight: 500 }}>진행률</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: t.primary }}>
                      {progressPct}%
                    </span>
                  </div>
                  <div
                    style={{
                      height: 6,
                      background: t.primarySoft,
                      borderRadius: 999,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${progressPct}%`,
                        height: "100%",
                        borderRadius: 999,
                        background: `linear-gradient(90deg, ${t.primary} 0%, ${t.primaryHover} 100%)`,
                      }}
                    />
                  </div>
                </div>
              )}

              {/* 현재 수치 / 기록 - 수치형은 인라인 숫자입력, 횟수형은 "오늘 완료" 버튼 한 번 */}
              <div
                style={{
                  borderTop: `1px solid ${t.border}`,
                  borderBottom: `1px solid ${t.border}`,
                  padding: "10px 0",
                  marginBottom: 12,
                }}
              >
                {isFrequency ? (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <p style={{ margin: "0 0 2px", fontSize: 12, color: t.textMuted }}>현재 수치</p>
                      <p style={{ margin: 0, fontSize: 18, fontWeight: 600, color: t.text }}>
                        {goal.current_value ?? 0}
                        {goal.target_value !== null ? ` / ${goal.target_value}` : ""}
                        {goal.unit ?? "회"}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleFrequencyComplete(goal)}
                      disabled={isLoggedToday || loggingGoalId === goal.id}
                      style={{
                        background: isLoggedToday ? t.cardBg : t.primarySoft,
                        border: `1px solid ${isLoggedToday ? t.border : t.border}`,
                        borderRadius: 8,
                        padding: "8px 14px",
                        fontSize: 13,
                        color: isLoggedToday ? t.textMuted : t.primary,
                        fontWeight: 600,
                        cursor: isLoggedToday || loggingGoalId === goal.id ? "default" : "pointer",
                      }}
                    >
                      {loggingGoalId === goal.id ? "기록 중..." : isLoggedToday ? "오늘 완료 ✓" : "오늘 완료"}
                    </button>
                  </div>
                ) : !isLogging ? (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <p style={{ margin: "0 0 2px", fontSize: 12, color: t.textMuted }}>현재 수치</p>
                      <p style={{ margin: 0, fontSize: 18, fontWeight: 600, color: t.text }}>
                        {goal.current_value ?? "-"}
                        {goal.unit ?? ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setActiveLogId(goal.id)}
                      style={{
                        background: t.primarySoft,
                        border: `1px solid ${t.border}`,
                        borderRadius: 8,
                        padding: "8px 14px",
                        fontSize: 13,
                        color: t.primary,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      기록하기
                    </button>
                  </div>
                ) : (
                  <div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <input
                        type="number"
                        autoFocus
                        value={logText[goal.id] ?? ""}
                        onChange={(e) => setLogText((prev) => ({ ...prev, [goal.id]: e.target.value }))}
                        placeholder={`오늘 수치${goal.unit ? ` (${goal.unit})` : ""}`}
                        style={{ ...inputStyle, flex: 1, marginBottom: 0 }}
                      />
                      <button
                        type="button"
                        onClick={() => handleLogProgress(goal.id)}
                        disabled={loggingGoalId === goal.id}
                        style={{
                          flexShrink: 0,
                          padding: "0 14px",
                          border: "none",
                          borderRadius: 8,
                          background: t.primary,
                          color: "#fff",
                          fontSize: 12.5,
                          fontWeight: 700,
                          cursor: loggingGoalId === goal.id ? "default" : "pointer",
                        }}
                      >
                        {loggingGoalId === goal.id ? "저장 중..." : "저장"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setActiveLogId(null);
                          setLogError((prev) => ({ ...prev, [goal.id]: "" }));
                        }}
                        disabled={loggingGoalId === goal.id}
                        style={{
                          flexShrink: 0,
                          padding: "0 12px",
                          border: `1px solid ${t.border}`,
                          borderRadius: 8,
                          background: t.cardBg,
                          color: t.textMuted,
                          fontSize: 12.5,
                          cursor: "pointer",
                        }}
                      >
                        취소
                      </button>
                    </div>
                    {logError[goal.id] && (
                      <p style={{ color: t.danger, fontSize: 11.5, margin: "6px 0 0" }}>
                        {logError[goal.id]}
                      </p>
                    )}
                  </div>
                )}
                {isFrequency && logError[goal.id] && (
                  <p style={{ color: t.danger, fontSize: 11.5, margin: "6px 0 0" }}>{logError[goal.id]}</p>
                )}
              </div>

              {/* 최근 기록 미니 막대그래프 - 막대는 항상 고정 너비(기록이 1~2개뿐이어도 카드
                  전체 너비로 늘어나 통짜 배너처럼 보이지 않게, flex:1 대신 flex-basis 고정) */}
              {goal.recent_logs.length > 0 && (
                <div style={{ display: "flex", gap: 6, alignItems: "flex-end", height: 40, marginBottom: 12 }}>
                  {(() => {
                    const maxValue = Math.max(1, ...goal.recent_logs.map((l) => l.value));
                    return goal.recent_logs.map((log) => (
                      <div
                        key={log.log_date}
                        style={{
                          flex: "0 0 22px",
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "center",
                          gap: 2,
                        }}
                      >
                        <div
                          style={{
                            width: "100%",
                            height: Math.max(3, (log.value / maxValue) * 26),
                            borderRadius: 3,
                            background: t.primary,
                          }}
                          title={`${log.log_date}: ${log.value}${goal.unit ?? ""}`}
                        />
                        <span style={{ fontSize: 9, color: t.textMuted }}>
                          {log.log_date.slice(5).replace("-", "/")}
                        </span>
                      </div>
                    ));
                  })()}
                </div>
              )}

              {/* AI 가이드 */}
              {goal.guide_content && (
                <div
                  style={{
                    background: t.pageBg,
                    borderLeft: `3px solid ${t.primary}`,
                    borderRadius: 6,
                    padding: 12,
                    marginBottom: 10,
                  }}
                >
                  <p
                    style={{
                      margin: "0 0 6px",
                      fontSize: 11,
                      textTransform: "uppercase",
                      color: t.primary,
                      fontWeight: 700,
                      letterSpacing: 0.5,
                    }}
                  >
                    ✨ AI 가이드
                  </p>
                  <p style={{ margin: 0, fontSize: 12.5, color: t.text, lineHeight: 1.6, whiteSpace: "pre-line" }}>
                    {goal.guide_content}
                  </p>
                </div>
              )}

              {/* 하단 메타: 가이드 생성 시각 + 기간구분/달성여부 */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 11, color: t.textMuted }}>
                  {goal.guide_generated_at
                    ? `가이드 생성됨 • ${goal.guide_generated_at.slice(0, 10)}`
                    : "가이드 준비 중"}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: goal.is_achieved ? t.success : t.primary,
                  }}
                >
                  {goal.is_achieved ? "✓ 달성" : goal.term}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
