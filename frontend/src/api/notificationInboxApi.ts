import { apiFetch, apiFetchRaw } from "./client";
import type { NotificationLogListResult } from "./types";

export const notificationInboxApi = {
  list: () => apiFetch<NotificationLogListResult>("/notifications/inbox"),
  // 204 No Content라 JSON 바디가 없다 — apiFetch(res.json())를 쓰면 파싱 에러가 나서 raw fetch를 쓴다.
  markAllRead: async () => {
    await apiFetchRaw("/notifications/inbox/read-all", { method: "POST" });
  },
};
