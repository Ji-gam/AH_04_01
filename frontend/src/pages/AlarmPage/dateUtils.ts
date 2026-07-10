import type { NotificationScheduleResult } from "../../api/types";

export const KOREAN_DAYS = ["일", "월", "화", "수", "목", "금", "토"] as const;

export function toDateString(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function isScheduleDueOnDate(schedule: NotificationScheduleResult, date: Date): boolean {
  if (schedule.frequency_type === "DAILY") return true;
  return schedule.target_day_of_week === KOREAN_DAYS[date.getDay()];
}
