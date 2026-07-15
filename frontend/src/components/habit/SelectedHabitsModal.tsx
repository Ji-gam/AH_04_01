import type { HabitsTodayResult } from "../../api/types";
import Modal from "../../pages/AlarmPage/components/Modal";
import { pinkTheme } from "../../theme/pinkTheme";

interface Props {
  userName: string;
  habitsToday: HabitsTodayResult;
  onCheck: (habitKey: string) => void;
  onClose: () => void;
}

/**
 * "내가 선택한 습관" 모달 - 오늘 선택한 습관의 진행 상황을 보고 체크할 수 있다.
 * 홈 화면 라이프스타일 카드와 습관 선택 페이지("선택한 습관" 클릭) 양쪽에서 재사용한다.
 */
export default function SelectedHabitsModal({ userName, habitsToday, onCheck, onClose }: Props) {
  return (
    <Modal onClose={onClose}>
      <div
        style={{
          background: pinkTheme.cardBg,
          border: `1px solid ${pinkTheme.border}`,
          borderRadius: 16,
          padding: 18,
          boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
        }}
      >
        <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: pinkTheme.primary }}>
          🌿 {userName}님을 위한 추천 라이프스타일
        </p>
        <p style={{ margin: "4px 0 14px", fontSize: 12, color: pinkTheme.textMuted }}>
          오늘의 당신, 할 수 있어요!
        </p>
        {habitsToday.habits.length === 0 ? (
          <p
            style={{
              margin: 0,
              fontSize: 13,
              color: pinkTheme.textMuted,
              textAlign: "center",
              padding: "20px 0",
            }}
          >
            아직 선택한 습관이 없어요.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {habitsToday.habits.map((habit) => (
              <div
                key={habit.key}
                style={{
                  background: pinkTheme.primarySoft,
                  borderRadius: 12,
                  padding: "10px 14px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 6,
                  }}
                >
                  <span style={{ fontSize: 13, fontWeight: 700, color: pinkTheme.text }}>
                    {habit.label}
                  </span>
                  <span style={{ fontSize: 12, color: pinkTheme.textMuted }}>
                    {habit.progress}/{habit.target}
                    {habit.unit}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ display: "flex", gap: 4, flex: 1, flexWrap: "wrap" }}>
                    {Array.from({ length: habit.target }, (_, i) => (
                      <span
                        key={i}
                        aria-hidden
                        style={{
                          fontSize: 18,
                          opacity: i < habit.progress ? 1 : 0.25,
                          filter: i < habit.progress ? "none" : "grayscale(100%)",
                        }}
                      >
                        {habit.icon}
                      </span>
                    ))}
                  </div>
                  <button
                    type="button"
                    disabled={habit.completed}
                    onClick={() => onCheck(habit.key)}
                    style={{
                      flexShrink: 0,
                      border: "none",
                      borderRadius: 999,
                      padding: "6px 14px",
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: habit.completed ? "default" : "pointer",
                      background: habit.completed ? pinkTheme.success : pinkTheme.primary,
                      color: "#fff",
                    }}
                  >
                    {habit.completed ? "완료!" : "체크"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}
