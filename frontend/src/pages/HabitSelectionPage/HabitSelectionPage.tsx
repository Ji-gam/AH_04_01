import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { habitApi } from "../../api/habitApi";
import type { HabitRecommendationItemResult } from "../../api/types";
import { pinkTheme as t } from "../../theme/pinkTheme";

const MAX_SELECTIONS = 5;

export default function HabitSelectionPage() {
  const navigate = useNavigate();
  const [habits, setHabits] = useState<HabitRecommendationItemResult[] | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    habitApi
      .getRecommendations()
      .then((result) => {
        setHabits(result.habits);
        setSelectedKeys(new Set(result.selected_keys));
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "추천 습관을 불러오지 못했습니다.");
      })
      .finally(() => setLoading(false));
  }, []);

  function toggle(key: string) {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else if (next.size < MAX_SELECTIONS) {
        next.add(key);
      }
      return next;
    });
    setSaved(false);
  }

  async function handleSave() {
    try {
      await habitApi.selectHabits(Array.from(selectedKeys));
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    }
  }

  return (
    <div style={{ background: t.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate("/more")}
          style={{
            background: "none",
            border: "none",
            color: t.textMuted,
            padding: 0,
            marginBottom: 12,
            cursor: "pointer",
          }}
        >
          ← 뒤로가기
        </button>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 6,
          }}
        >
          <h1 style={{ fontSize: 18, fontWeight: 700, color: t.text, margin: 0 }}>
            🌿 오늘의 추천 습관
          </h1>
          <span
            style={{
              background: t.primarySoft,
              color: t.primary,
              borderRadius: 999,
              padding: "5px 12px",
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            {selectedKeys.size}/{MAX_SELECTIONS} 선택
          </span>
        </div>

        <p style={{ margin: "0 0 20px", fontSize: 13, color: t.textMuted, lineHeight: 1.5 }}>
          오늘 해보고 싶은 습관을 최대 {MAX_SELECTIONS}개까지 골라보세요. 하나도 안 골라도 괜찮아요.
        </p>

        {loading && <p style={{ color: t.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: t.danger, fontSize: 14 }}>{error}</p>}

        {!loading && habits && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
            {habits.map((habit) => {
              const checked = selectedKeys.has(habit.key);
              const disabled = !checked && selectedKeys.size >= MAX_SELECTIONS;
              return (
                <button
                  key={habit.key}
                  type="button"
                  onClick={() => toggle(habit.key)}
                  disabled={disabled}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "14px 16px",
                    borderRadius: 16,
                    border: `1.5px solid ${checked ? t.primary : t.border}`,
                    background: checked ? t.primarySoft : t.cardBg,
                    textAlign: "left",
                    cursor: disabled ? "not-allowed" : "pointer",
                    opacity: disabled ? 0.5 : 1,
                    boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
                  }}
                >
                  <span
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 6,
                      flexShrink: 0,
                      border: checked ? "none" : `2px solid ${t.border}`,
                      background: checked ? t.primary : "#fff",
                      color: "#fff",
                      fontSize: 13,
                      lineHeight: 1,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                    aria-hidden
                  >
                    {checked ? "✓" : ""}
                  </span>
                  <span style={{ fontSize: 18 }} aria-hidden>
                    {habit.icon}
                  </span>
                  <span style={{ flex: 1 }}>
                    <strong style={{ display: "block", fontSize: 14, color: t.text }}>
                      {habit.label}
                    </strong>
                    <span style={{ fontSize: 12, color: t.textMuted }}>
                      목표 {habit.target}
                      {habit.unit}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        )}

        <button
          type="button"
          onClick={handleSave}
          disabled={loading}
          style={{
            width: "100%",
            padding: "14px 0",
            borderRadius: 12,
            border: "none",
            background: t.primary,
            color: "#fff",
            fontSize: 15,
            fontWeight: 700,
            cursor: loading ? "default" : "pointer",
          }}
        >
          저장
        </button>

        {saved && (
          <p style={{ margin: "10px 0 0", fontSize: 13, color: t.success, textAlign: "center" }}>
            ✓ 저장되었습니다. 홈 화면 라이프스타일 카드에서 확인해보세요.
          </p>
        )}
      </div>
    </div>
  );
}
