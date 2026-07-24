import { apiFetch } from "./client";
import type {
  DiaryEntryItemResult,
  DiaryEntryListResult,
  DiaryEntrySaveRequest,
  DiaryTodayResult,
} from "./types";

export const diaryApi = {
  getToday: () => apiFetch<DiaryTodayResult>("/diary/today"),
  saveToday: (payload: DiaryEntrySaveRequest) =>
    apiFetch<DiaryEntryItemResult>("/diary/today", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  list: () => apiFetch<DiaryEntryListResult>("/diary"),
  deleteEntry: (entryId: number) =>
    apiFetch<DiaryEntryListResult>(`/diary/${entryId}`, { method: "DELETE" }),
};
