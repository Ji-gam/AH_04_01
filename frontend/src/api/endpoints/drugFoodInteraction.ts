// src/api/endpoints/drugFoodInteraction.ts
import { apiClient } from "../client";
import type { InteractionRule } from "../../types";

export const drugFoodInteractionApi = {
  getRules: async (medicationId: number): Promise<InteractionRule[]> => {
    const res = await apiClient.get(`/drug-food-interactions?medication_id=${medicationId}`);
    return res.data;
  },
  // ⚠️ [단순화] 백엔드가 아직 규칙기반 임시 구현이라 실제 LLM 생성 문구가 아닙니다.
  analyze: async (foodLogId: number) => {
    const res = await apiClient.post("/drug-food-interactions/analyze", { food_log_id: foodLogId });
    return res.data as { matched_rules: number[]; interaction_notes: string };
  },
};
