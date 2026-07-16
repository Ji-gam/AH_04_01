import { apiFetch } from "./client";
import type { HabitRecommendationsResult, HabitsTodayResult } from "./types";

export const habitApi = {
  getToday: () => apiFetch<HabitsTodayResult>("/habits/today"),
  check: (habitKey: string) =>
    apiFetch<HabitsTodayResult>(`/habits/today/${habitKey}/check`, { method: "POST" }),
  getRecommendations: () => apiFetch<HabitRecommendationsResult>("/habits/recommendations"),
  selectHabits: (habitKeys: string[]) =>
    apiFetch<HabitsTodayResult>("/habits/selections", {
      method: "POST",
      body: JSON.stringify({ habit_keys: habitKeys }),
    }),
};
