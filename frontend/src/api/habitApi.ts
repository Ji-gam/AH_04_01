import { apiFetch } from "./client";
import type {
  HabitRecommendationsResult,
  HabitsTodayResult,
  ReasonFeedbackResult,
  ReasonFeedbackValue,
} from "./types";

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
  submitReasonFeedback: (habitKey: string, value: ReasonFeedbackValue) =>
    apiFetch<ReasonFeedbackResult>(`/habits/${habitKey}/reason-feedback`, {
      method: "POST",
      body: JSON.stringify({ value }),
    }),
};
