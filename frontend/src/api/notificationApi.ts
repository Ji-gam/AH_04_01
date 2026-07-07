import { apiFetch, apiFetchRaw } from "./client";
import type {
  NotificationScheduleCreateRequest,
  NotificationScheduleResult,
  NotificationScheduleUpdateRequest,
} from "./types";

export const notificationApi = {
  list: () => apiFetch<NotificationScheduleResult[]>("/notifications/schedules"),
  create: (data: NotificationScheduleCreateRequest) =>
    apiFetch<NotificationScheduleResult>("/notifications/schedules", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (scheduleId: number, data: NotificationScheduleUpdateRequest) =>
    apiFetch<NotificationScheduleResult>(`/notifications/schedules/${scheduleId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  // 204 No Content라 JSON 바디가 없다 — apiFetch(res.json())를 쓰면 파싱 에러가 나서 raw fetch를 쓴다.
  remove: async (scheduleId: number) => {
    await apiFetchRaw(`/notifications/schedules/${scheduleId}`, { method: "DELETE" });
  },
};
