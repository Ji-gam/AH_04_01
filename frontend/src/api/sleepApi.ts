import { apiFetch } from "./client";
import type { SleepLogCreateRequest, SleepRecentResult, SleepTodayResult } from "./types";

export const sleepApi = {
  logSleep: (payload: SleepLogCreateRequest) =>
    apiFetch<SleepTodayResult>("/sleep/logs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getToday: () => apiFetch<SleepTodayResult>("/sleep/today"),
  getRecent: () => apiFetch<SleepRecentResult>("/sleep/recent"),
};
