import { apiFetch } from "./client";
import type {
  DietLogCreateRequest,
  DietRecentResult,
  DietTodayResult,
  FoodSearchResult,
  ReasonFeedbackResult,
  ReasonFeedbackValue,
} from "./types";

export const dietApi = {
  searchFood: (query: string) =>
    apiFetch<FoodSearchResult>(`/diet/search?query=${encodeURIComponent(query)}`),
  logFood: (payload: DietLogCreateRequest) =>
    apiFetch<DietTodayResult>("/diet/logs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getToday: () => apiFetch<DietTodayResult>("/diet/today"),
  deleteLog: (logId: number) =>
    apiFetch<DietTodayResult>(`/diet/logs/${logId}`, { method: "DELETE" }),
  getRecent: () => apiFetch<DietRecentResult>("/diet/recent"),
  submitKcalReasonFeedback: (value: ReasonFeedbackValue) =>
    apiFetch<ReasonFeedbackResult>("/diet/kcal-reason-feedback", {
      method: "POST",
      body: JSON.stringify({ value }),
    }),
};
