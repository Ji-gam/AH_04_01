import { apiFetch, apiFetchRaw } from "./client";
import type {
  DayOfWeek,
  FrequencyType,
  NotificationScheduleCreateRequest,
  NotificationScheduleResult,
  NotificationScheduleUpdateRequest,
} from "./types";

export type {
  DayOfWeek,
  FrequencyType,
  NotificationScheduleCreateRequest,
  NotificationScheduleResult,
  NotificationScheduleUpdateRequest,
};

// notificationApi.ts(본인 몫)와 로직이 겹치지만, 기존 파일을 안전하게 두기 위해 완전히 새
// 파일로 분리했다 - 백엔드도 /family/{target_profile_id} 별도 엔드포인트로 분리해뒀다
// (docs/decision_log/2026-07-16-family-medication-registration-duplication.md 참고).
export const familyNotificationApi = {
  list: (targetProfileId: number) =>
    apiFetch<NotificationScheduleResult[]>(`/notifications/schedules/family/${targetProfileId}`),
  create: (targetProfileId: number, data: NotificationScheduleCreateRequest) =>
    apiFetch<NotificationScheduleResult>(`/notifications/schedules/family/${targetProfileId}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (scheduleId: number, data: NotificationScheduleUpdateRequest) =>
    apiFetch<NotificationScheduleResult>(`/notifications/schedules/${scheduleId}/for-family`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  // 204 No Content라 JSON 바디가 없다 — apiFetch(res.json())를 쓰면 파싱 에러가 나서 raw fetch를 쓴다.
  remove: async (scheduleId: number) => {
    await apiFetchRaw(`/notifications/schedules/${scheduleId}/for-family`, { method: "DELETE" });
  },
};
