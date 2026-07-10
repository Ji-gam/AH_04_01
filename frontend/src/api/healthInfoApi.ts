import { apiFetch } from "./client";
import type { HealthInfoResult, HealthInfoUpdatePayload } from "./types";

export const healthInfoApi = {
  get: () => apiFetch<HealthInfoResult>("/users/me/health-info"),
  update: (data: HealthInfoUpdatePayload) =>
    apiFetch<HealthInfoResult>("/users/me/health-info", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
};
