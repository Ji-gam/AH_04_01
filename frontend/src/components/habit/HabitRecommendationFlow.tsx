import { useEffect, useState } from "react";

import { habitApi } from "../../api/habitApi";
import type { HabitRecommendationItemResult, HabitsTodayResult } from "../../api/types";

import HabitRecommendationModal from "./HabitRecommendationModal";

const MAX_SELECTIONS = 5;

interface Props {
  onClose: () => void;
  onSaved?: (result: HabitsTodayResult) => void;
}

/** "🌿 추천 받은 습관 리스트" 조회/토글/저장 로직 - 마이다이어리 허브(HabitSelectionContent)의
 * 버튼과 홈 화면의 "아직 습관을 하나도 안 골랐을 때" 카드 두 곳에서 똑같이 이 화면이 바로
 * 떠야 해서(2026-07-30, 홈에서는 마이다이어리 허브 전체가 아니라 이 목록이 바로 떠야 한다는
 * 피드백) 데이터 fetch/상태를 이 컴포넌트로 뽑아냈다. 화면 자체는 HabitRecommendationModal이
 * 그대로 담당한다(그 안에서 Modal도 같이 렌더링한다). */
export default function HabitRecommendationFlow({ onClose, onSaved }: Props) {
  const [habits, setHabits] = useState<HabitRecommendationItemResult[] | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    habitApi
      .getRecommendations()
      .then((recommendations) => {
        setHabits(recommendations.habits);
        setSelectedKeys(new Set(recommendations.selected_keys));
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
      setSaved(true);
      onSaved?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    }
  }

  return (
    <HabitRecommendationModal
      habits={habits}
      selectedKeys={selectedKeys}
      maxSelections={MAX_SELECTIONS}
      loading={loading}
      error={error}
      saved={saved}
      onToggle={toggle}
      onSave={handleSave}
      onClose={onClose}
    />
  );
}
