import { apiFetch } from "./client";
import type {
  ExerciseLogCreateRequest,
  ExerciseMetEstimateResult,
  ExerciseRecentResult,
  ExerciseSearchResult,
  ExerciseTodayResult,
} from "./types";

export const exerciseApi = {
  getCatalog: () => apiFetch<ExerciseSearchResult>("/exercise/catalog"),
  estimateMet: (exerciseName: string) =>
    apiFetch<ExerciseMetEstimateResult>("/exercise/estimate-met", {
      method: "POST",
      body: JSON.stringify({ exercise_name: exerciseName }),
    }),
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
