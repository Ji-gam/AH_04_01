import { useEffect, useState } from "react";

import { goalApi } from "../../api/goalApi";
import type { GoalItemResult } from "../../api/types";
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

interface FormState {
  title: string;
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
    setSaving(true);
    setFormError(null);
    try {
      const payload = {
        title: form.title.trim(),
        start_value: toNumberOrUndefined(form.startValue),
        target_value: toNumberOrUndefined(form.targetValue),
        current_value: toNumberOrUndefined(form.currentValue),
        unit: form.unit.trim() || undefined,
        start_date: form.startDate,
        end_date: form.endDate,
      };
      const saved =
        editingId !== null
          ? await goalApi.update(editingId, payload)
          : await goalApi.create(payload);
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
    } catch (err) {
      setLogError((prev) => ({
        ...prev,
        [goalId]: err instanceof Error ? err.message : "기록 중 오류가 발생했습니다.",
      }));
    } finally {
      setLoggingGoalId(null);
    }
  }

  return (
    <div style={cardStyle}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 14,
        }}
      >
        <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: t.primary }}>🎯 목표 설정</p>
        {!showForm && (
          <button
            type="button"
            onClick={openCreateForm}
            style={{
              border: "none",
              background: t.primary,
              color: "#fff",
              borderRadius: 10,
              padding: "6px 12px",
              fontSize: 12.5,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            + 새 목표
          </button>
        )}
      </div>

      {loading && <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>}
      {error && <p style={{ color: t.danger, fontSize: 13 }}>{error}</p>}

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
          <div style={{ display: "flex", gap: 6 }}>
            <input
              type="number"
              value={form.currentValue}
              onChange={(e) => setForm((prev) => ({ ...prev, currentValue: e.target.value }))}
              placeholder="현재 수치(선택, 비우면 시작값)"
              style={inputStyle}
            />
            <input
              type="text"
              value={form.unit}
              onChange={(e) => setForm((prev) => ({ ...prev, unit: e.target.value }))}
              placeholder="단위(예: kg)"
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
        <p style={{ color: t.textMuted, fontSize: 13, textAlign: "center", padding: "12px 0" }}>
          아직 등록한 목표가 없어요. "+ 새 목표"로 첫 목표를 만들어보세요.
        </p>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {goals.map((goal) => {
          const progressPct =
            goal.progress_rate !== null ? Math.round(goal.progress_rate * 100) : null;
          return (
            <div
              key={goal.id}
              style={{
                border: `1px solid ${t.border}`,
                borderRadius: 12,
                padding: 12,
                background: t.pageBg,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 8,
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                    <strong style={{ fontSize: 14, color: t.text }}>{goal.title}</strong>
                    <span
                      style={{
                        fontSize: 10.5,
                        fontWeight: 700,
                        color: t.primary,
                        background: t.primarySoft,
                        borderRadius: 999,
                        padding: "1.5px 8px",
                      }}
                    >
                      {goal.term}
                    </span>
                    {goal.is_achieved && (
                      <span style={{ fontSize: 10.5, fontWeight: 700, color: t.success }}>
                        ✓ 달성
                      </span>
                    )}
                  </div>
                  <p style={{ margin: 0, fontSize: 11.5, color: t.textMuted }}>
                    {goal.start_date} ~ {goal.end_date}
                    {goal.target_value !== null && (
                      <>
                        {" · "}
                        {goal.current_value ?? "-"}
                        {goal.unit ?? ""} → {goal.target_value}
                        {goal.unit ?? ""}
                      </>
                    )}
                  </p>
                </div>
                <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                  <button
                    type="button"
                    onClick={() => openEditForm(goal)}
                    aria-label="목표 수정"
                    style={{
                      border: "none",
                      background: "transparent",
                      color: t.textMuted,
                      cursor: "pointer",
                    }}
                  >
                    ✏️
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(goal.id)}
                    aria-label="목표 삭제"
                    style={{
                      border: "none",
                      background: "transparent",
                      color: t.danger,
                      cursor: "pointer",
                    }}
                  >
                    🗑
                  </button>
                </div>
              </div>

              {progressPct !== null && (
                <div
                  style={{
                    marginTop: 8,
                    height: 8,
                    borderRadius: 999,
                    background: t.border,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${progressPct}%`,
                      height: "100%",
                      background: t.primary,
                      borderRadius: 999,
                    }}
                  />
                </div>
              )}

              {/* 오늘 기록하기 - 목표 수정과 별개로 하루 수치만 빠르게 남긴다 */}
              <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                <input
                  type="number"
                  value={logText[goal.id] ?? ""}
                  onChange={(e) => setLogText((prev) => ({ ...prev, [goal.id]: e.target.value }))}
                  placeholder={`오늘 수치 입력${goal.unit ? ` (${goal.unit})` : ""}`}
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
                    borderRadius: 10,
                    background: t.primary,
                    color: "#fff",
                    fontSize: 12.5,
                    fontWeight: 700,
                    cursor: loggingGoalId === goal.id ? "default" : "pointer",
                  }}
                >
                  {loggingGoalId === goal.id ? "기록 중..." : "오늘 기록"}
                </button>
              </div>
              {logError[goal.id] && (
                <p style={{ color: t.danger, fontSize: 11.5, margin: "4px 0 0" }}>
                  {logError[goal.id]}
                </p>
              )}

              {goal.recent_logs.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    gap: 4,
                    alignItems: "flex-end",
                    height: 40,
                    marginTop: 10,
                  }}
                >
                  {(() => {
                    const maxValue = Math.max(1, ...goal.recent_logs.map((l) => l.value));
                    return goal.recent_logs.map((log) => (
                      <div
                        key={log.log_date}
                        style={{
                          flex: 1,
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

              {goal.guide_content && (
                <p
                  style={{
                    margin: "10px 0 0",
                    fontSize: 12.5,
                    color: t.text,
                    lineHeight: 1.6,
                    whiteSpace: "pre-line",
                    background: t.primarySoft,
                    borderRadius: 10,
                    padding: "8px 10px",
                  }}
                >
                  💡 {goal.guide_content}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
