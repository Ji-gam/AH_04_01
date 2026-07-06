// src/api/endpoints/healthMetric.ts
import { apiClient } from "../client";
import type { HealthMetricCreate } from "../../types";

export const healthMetricApi = {
  create: (data: HealthMetricCreate) => apiClient.post("/health-metrics", data),
  // TODO(조원 구현): 백엔드에 목록 조회 API가 아직 없습니다. 추이 그래프가 필요하면
  // backend/domains/health_metric/router.py에 GET 엔드포인트부터 추가해주세요.
};
