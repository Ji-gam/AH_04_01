import { apiFetch } from "./client";
import type { NotificationSettingsResult, NotificationSettingsUpdateRequest } from "./types";

export const notificationSettingsApi = {
  get: () => apiFetch<NotificationSettingsResult>("/notifications/settings"),
  update: (data: NotificationSettingsUpdateRequest) =>
    apiFetch<NotificationSettingsResult>("/notifications/settings", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
};
