import { apiFetch } from "./client";
import type {
  ConsentStatusResult,
  ConsentUpdatePayload,
  HealthInfoResult,
  HealthInfoUpdatePayload,
} from "./types";

export const healthInfoApi = {
  get: () => apiFetch<HealthInfoResult>("/users/me/health-info"),
  update: (data: HealthInfoUpdatePayload) =>
    apiFetch<HealthInfoResult>("/users/me/health-info", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
};

export const consentApi = {
  get: () => apiFetch<ConsentStatusResult>("/users/me/consent"),
  update: (data: ConsentUpdatePayload) =>
    apiFetch<ConsentStatusResult>("/users/me/consent", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
};
