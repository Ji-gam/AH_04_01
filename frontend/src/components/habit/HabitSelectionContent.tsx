import { useEffect, useState } from "react";

import { habitApi } from "../../api/habitApi";
import type { HabitRecommendationItemResult, HabitsTodayResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme as t } from "../../theme/pinkTheme";

import SelectedHabitsModal from "./SelectedHabitsModal";

const MAX_SELECTIONS = 5;

interface Props {
  // 저장 성공 시 최신 습관 상태를 알려준다 - 홈 화면 모달로 띄웠을 때, 홈 화면 자체의
  // habitsToday 상태도 같이 갱신해서 모달을 닫고 나면 카드가 바로 최신 상태로 보이게 한다.
  onSaved?: (result: HabitsTodayResult) => void;
}

/** 생활습관 추천 화면의 본문(아바타+인사/선택한 습관 버튼/추천 리스트/저장). 원래
 * HabitSelectionPage 전용이었는데, 홈 화면 라이프스타일 카드를 눌렀을 때 페이지 이동 대신
 * 모달로도 띄울 수 있도록(2026-07-19) 본문만 뽑아냈다 - 페이지 이동(뒤로가기)은 이 컴포넌트를
 * 감싸는 쪽(HabitSelectionPage 또는 HomePage의 Modal)이 책임진다. */
export default function HabitSelectionContent({ onSaved }: Props) {
  const { user } = useAuth();
  const [habits, setHabits] = useState<HabitRecommendationItemResult[] | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [habitsToday, setHabitsToday] = useState<HabitsTodayResult | null>(null);
  const [showSelectedModal, setShowSelectedModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([habitApi.getRecommendations(), habitApi.getToday()])
      .then(([recommendations, today]) => {
        setHabits(recommendations.habits);
        setSelectedKeys(new Set(recommendations.selected_keys));
        setHabitsToday(today);
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
      const result = await habitApi.selectHabits(Array.from(selectedKeys));
      setHabitsToday(result);
      setSaved(true);
      onSaved?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    }
  }

  function handleCheckHabit(habitKey: string) {
    habitApi
      .check(habitKey)
      .then((result) => {
        setHabitsToday(result);
        onSaved?.(result);
      })
      .catch(() => {
        // 습관 체크는 부가 기능이라 실패해도 조용히 무시 - 다음 클릭에서 다시 시도하면 된다.
      });
  }

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <span
          aria-hidden
          style={{
            width: 48,
            height: 48,
            borderRadius: "50%",
            flexShrink: 0,
            border: `1.5px dashed ${t.border}`,
            background: t.cardBg,
            color: t.textMuted,
            fontSize: 18,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          👤
        </span>
        <div>
          <h1 style={{ fontSize: 16, fontWeight: 700, color: t.text, margin: 0 }}>
            {user ? `${user.name}님, 안녕하세요` : "안녕하세요"}
          </h1>
          <p style={{ fontSize: 13, color: t.textMuted, margin: "4px 0 0" }}>
            이번 주 라이프스타일을 골라보세요
          </p>
        </div>
      </div>

      {/* 선택한 습관 — 누르면 오늘 진행 상황(SelectedHabitsModal)을 모달로 보여준다. */}
      <button
        type="button"
        onClick={() => setShowSelectedModal(true)}
        style={{
          display: "block",
          width: "100%",
          textAlign: "left",
          background: t.cardBg,
          border: `1px solid ${t.border}`,
          borderRadius: 16,
          padding: 16,
          marginBottom: 20,
          boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
          cursor: "pointer",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: t.text }}>✅ 선택한 습관</p>
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
      </button>

      <h2 style={{ fontSize: 15, fontWeight: 700, color: t.text, margin: "0 0 6px" }}>
        🌿 추천 받은 습관 리스트
      </h2>
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

      {user && habitsToday && showSelectedModal && (
        <SelectedHabitsModal
          userName={user.name}
          habitsToday={habitsToday}
          onCheck={handleCheckHabit}
          onClose={() => setShowSelectedModal(false)}
        />
      )}
    </>
  );
}
