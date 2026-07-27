import { apiFetch, apiFetchRaw } from "./client";
import type {
  GoalCreateRequest,
  GoalItemResult,
  GoalListResult,
  GoalProgressLogCreateRequest,
  GoalUpdateRequest,
} from "./types";

export const goalApi = {
  list: () => apiFetch<GoalListResult>("/goals"),
  create: (data: GoalCreateRequest) =>
    apiFetch<GoalItemResult>("/goals", { method: "POST", body: JSON.stringify(data) }),
  update: (goalId: number, data: GoalUpdateRequest) =>
    apiFetch<GoalItemResult>(`/goals/${goalId}`, { method: "PATCH", body: JSON.stringify(data) }),
  logProgress: (goalId: number, data: GoalProgressLogCreateRequest) =>
    apiFetch<GoalItemResult>(`/goals/${goalId}/logs`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  // 204 No Content라 JSON 바디가 없다 — apiFetch(res.json())를 쓰면 파싱 에러가 나서 raw fetch를 쓴다.
  remove: async (goalId: number) => {
    await apiFetchRaw(`/goals/${goalId}`, { method: "DELETE" });
  },
};
