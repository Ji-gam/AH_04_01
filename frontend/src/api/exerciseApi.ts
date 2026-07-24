import { apiFetch } from "./client";
import type {
  ExerciseLogCreateRequest,
  ExerciseRecentResult,
  ExerciseSearchResult,
  ExerciseTodayResult,
} from "./types";

export const exerciseApi = {
  searchExercise: (query: string) =>
    apiFetch<ExerciseSearchResult>(`/exercise/search?query=${encodeURIComponent(query)}`),
  logExercise: (payload: ExerciseLogCreateRequest) =>
    apiFetch<ExerciseTodayResult>("/exercise/logs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getToday: () => apiFetch<ExerciseTodayResult>("/exercise/today"),
  deleteLog: (logId: number) =>
    apiFetch<ExerciseTodayResult>(`/exercise/logs/${logId}`, { method: "DELETE" }),
  getRecent: () => apiFetch<ExerciseRecentResult>("/exercise/recent"),
};
