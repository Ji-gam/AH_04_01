import { apiFetch, apiFetchRaw } from "./client";

export interface IntakeRecord {
  source_type: "medication_schedule" | "notification_schedule";
  source_id: number;
  scheduled_time: string; // "HH:MM"
}

export interface IntakeDailyCount {
  date: string; // "YYYY-MM-DD"
  checked_count: number;
}

export const intakeApi = {
  list: (date: string) => apiFetch<IntakeRecord[]>(`/intake?date=${date}`),
  dailyCounts: (start: string, end: string) =>
    apiFetch<IntakeDailyCount[]>(`/intake/daily-counts?start=${start}&end=${end}`),
  // 204 No Content라 JSON 바디가 없다 — apiFetch(res.json())를 쓰면 파싱 에러가 나서 raw fetch를 쓴다.
  toggle: async (record: IntakeRecord, date: string, checked: boolean) => {
    await apiFetchRaw("/intake/toggle", {
      method: "POST",
      body: JSON.stringify({ ...record, date, checked }),
    });
  },
};
