import type { HabitRecommendationItemResult } from "../../api/types";
import Modal from "../../pages/AlarmPage/components/Modal";
import { pinkTheme as t } from "../../theme/pinkTheme";

interface Props {
  habits: HabitRecommendationItemResult[] | null;
  selectedKeys: Set<string>;
  maxSelections: number;
  loading: boolean;
  error: string | null;
  saved: boolean;
  onToggle: (key: string) => void;
  onSave: () => void;
  onClose: () => void;
}

/** "🌿 추천 받은 습관 리스트" 모달 - 원래 HabitSelectionContent에 인라인으로 항상 펼쳐져
 * 있던 토글 리스트+저장 버튼을, "✅ 선택한 습관"과 같은 버튼→모달 방식으로 통일하기 위해
 * 분리했다(2026-07-24). 선택 상태(selectedKeys)/토글/저장 로직은 그대로 부모가 들고 있고,
 * 이 컴포넌트는 화면만 담당한다. */
export default function HabitRecommendationModal({
  habits,
  selectedKeys,
  maxSelections,
  loading,
  error,
  saved,
  onToggle,
  onSave,
  onClose,
}: Props) {
  return (
    <Modal onClose={onClose}>
      <div
        style={{
          background: t.cardBg,
          border: `1px solid ${t.border}`,
          borderRadius: 16,
          padding: 18,
          boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: t.text }}>🌿 추천 받은 습관 리스트</p>
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
            {selectedKeys.size}/{maxSelections} 선택
          </span>
        </div>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: t.textMuted, lineHeight: 1.5 }}>
          오늘 해보고 싶은 습관을 최대 {maxSelections}개까지 골라보세요. 하나도 안 골라도 괜찮아요.
        </p>

        {loading && <p style={{ color: t.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: t.danger, fontSize: 14 }}>{error}</p>}

        {!loading && habits && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
            {habits.map((habit) => {
              const checked = selectedKeys.has(habit.key);
              const disabled = !checked && selectedKeys.size >= maxSelections;
              return (
                <button
                  key={habit.key}
                  type="button"
                  onClick={() => onToggle(habit.key)}
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
                    <strong style={{ display: "block", fontSize: 14, color: t.text }}>{habit.label}</strong>
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
          onClick={onSave}
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
            ✓ 저장되었습니다.
          </p>
        )}
      </div>
    </Modal>
  );
}
