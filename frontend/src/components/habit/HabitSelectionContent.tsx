import { useState } from "react";

import type { HabitsTodayResult } from "../../api/types";
import DiaryEntryContent from "../../components/diary/DiaryEntryContent";
import DietLogContent from "../../components/diet/DietLogContent";
import ExerciseLogContent from "../../components/exercise/ExerciseLogContent";
import GoalContent from "../../components/goal/GoalContent";
import SleepLogContent from "../../components/sleep/SleepLogContent";
import { useAuth } from "../../hooks/useAuth";
import Modal from "../../pages/AlarmPage/components/Modal";
import { pinkTheme as t } from "../../theme/pinkTheme";

import HabitRecommendationFlow from "./HabitRecommendationFlow";

const menuButtonStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  textAlign: "left",
  background: t.cardBg,
  border: `1px solid ${t.border}`,
  borderRadius: 16,
  padding: 16,
  marginBottom: 10,
  boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
  cursor: "pointer",
  fontSize: 15,
  fontWeight: 700,
  color: t.text,
};

interface Props {
  // 저장 성공 시 최신 습관 상태를 알려준다 - 홈 화면 모달로 띄웠을 때, 홈 화면 자체의
  // habitsToday 상태도 같이 갱신해서 모달을 닫고 나면 카드가 바로 최신 상태로 보이게 한다.
  onSaved?: (result: HabitsTodayResult) => void;
}

/** 마이다이어리 화면의 본문(아바타+인사/추천 습관·식단 기록·운동 기록 모달 버튼). 원래
 * HabitSelectionPage 전용이었는데, 홈 화면 라이프스타일 카드를 눌렀을 때 페이지 이동 대신
 * 모달로도 띄울 수 있도록(2026-07-19) 본문만 뽑아냈다 - 페이지 이동(뒤로가기)은 이 컴포넌트를
 * 감싸는 쪽(HabitSelectionPage 또는 HomePage의 Modal)이 책임진다. 추천 습관 리스트/식단
 * 기록(DietLogContent, F-DIET-1/2)/운동 기록(ExerciseLogContent, 2026-07-25)은 셋 다
 * 버튼→모달 방식이다. "선택한 습관"(오늘 진행 체크) 버튼은 여기 있으면 안 예뻐서 뺐다
 * (2026-07-24) - 이미 선택한 습관이 있으면 홈 화면 라이프스타일 카드가 SelectedHabitsModal로
 * 바로 연결되니 기능 자체는 그대로 남아있다. */
export default function HabitSelectionContent({ onSaved }: Props) {
  const { user } = useAuth();
  const [showRecommendationModal, setShowRecommendationModal] = useState(false);
  const [showDietModal, setShowDietModal] = useState(false);
  const [showExerciseModal, setShowExerciseModal] = useState(false);
  const [showSleepModal, setShowSleepModal] = useState(false);
  const [showDiaryModal, setShowDiaryModal] = useState(false);
  const [showGoalModal, setShowGoalModal] = useState(false);

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

      {/* 추천 받은 습관 리스트 — 누르면 HabitRecommendationModal(토글+저장)을 모달로 보여준다. */}
      <button
        type="button"
        onClick={() => setShowRecommendationModal(true)}
        style={menuButtonStyle}
      >
        🌿 추천 받은 습관 리스트
      </button>

      {/* 오늘의 식단 기록 — 누르면 DietLogContent(F-DIET-1/2)를 모달로 보여준다. */}
      <button type="button" onClick={() => setShowDietModal(true)} style={menuButtonStyle}>
        🍽 오늘의 식단 기록
      </button>

      {/* 오늘의 운동 기록 — 누르면 ExerciseLogContent를 모달로 보여준다. */}
      <button type="button" onClick={() => setShowExerciseModal(true)} style={menuButtonStyle}>
        🏃 오늘의 운동 기록
      </button>

      {/* 오늘의 수면 기록 — 누르면 SleepLogContent(REQ-TRCK-003)를 모달로 보여준다. */}
      <button type="button" onClick={() => setShowSleepModal(true)} style={menuButtonStyle}>
        😴 오늘의 수면 기록
      </button>

      {/* 오늘의 한 줄 — 누르면 DiaryEntryContent(일기)를 모달로 보여준다. */}
      <button type="button" onClick={() => setShowDiaryModal(true)} style={menuButtonStyle}>
        📝 오늘의 한 줄
      </button>

      {/* 목표 설정 — 누르면 GoalContent(F-GOAL-1/2)를 모달로 보여준다. */}
      <button
        type="button"
        onClick={() => setShowGoalModal(true)}
        style={{ ...menuButtonStyle, marginBottom: 20 }}
      >
        🎯 목표 설정
      </button>

      {showRecommendationModal && (
        <HabitRecommendationFlow
          onClose={() => setShowRecommendationModal(false)}
          onSaved={onSaved}
        />
      )}

      {showDietModal && (
        <Modal onClose={() => setShowDietModal(false)}>
          <DietLogContent />
        </Modal>
      )}

      {showExerciseModal && (
        <Modal onClose={() => setShowExerciseModal(false)}>
          <ExerciseLogContent />
        </Modal>
      )}

      {showSleepModal && (
        <Modal onClose={() => setShowSleepModal(false)}>
          <SleepLogContent />
        </Modal>
      )}

      {showDiaryModal && (
        <Modal onClose={() => setShowDiaryModal(false)}>
          <DiaryEntryContent />
        </Modal>
      )}

      {showGoalModal && (
        <Modal onClose={() => setShowGoalModal(false)}>
          <GoalContent />
        </Modal>
      )}
    </>
  );
}
