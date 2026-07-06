// src/api/endpoints/symptomLog.ts
import { apiClient } from "../client";
import type { SymptomLogCreate } from "../../types";

export const symptomLogApi = {
  create: (data: SymptomLogCreate) => apiClient.post("/symptom-logs", data),
  // TODO(조원 구현): 목록 조회 API는 백엔드에 아직 없습니다.
};
