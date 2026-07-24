import { apiFetch } from "./client";
import type { WeeklyReportListResult } from "./types";

export const weeklyReportApi = {
  list: () => apiFetch<WeeklyReportListResult>("/weekly-reports"),
};
