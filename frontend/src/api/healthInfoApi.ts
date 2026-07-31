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
  // (2026-07-30) 마케팅만 유일하게 껐다 켤 수 있어서, 필수 3종(update)과는 별개
  // 엔드포인트로 분리 - 실수로 필수 항목까지 철회되는 걸 원천 차단.
  updateMarketing: (enabled: boolean) =>
    apiFetch<ConsentStatusResult>("/users/me/consent/marketing", {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),
};
