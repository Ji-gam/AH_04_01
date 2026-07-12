import { apiFetch } from "./client";
import type { HabitsTodayResult } from "./types";

export const habitApi = {
  getToday: () => apiFetch<HabitsTodayResult>("/habits/today"),
  check: (habitKey: string) =>
    apiFetch<HabitsTodayResult>(`/habits/today/${habitKey}/check`, { method: "POST" }),
};
