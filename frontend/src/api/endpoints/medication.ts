// src/api/endpoints/medication.ts
import { apiClient } from "../client";
import type { Medication } from "../../types";

export const medicationApi = {
  get: async (medicationId: number): Promise<Medication> => {
    const res = await apiClient.get(`/medications/${medicationId}`);
    return res.data;
  },
  // ⚠️ [보류] pgvector 도입 전까지는 항상 빈 배열만 돌아옵니다 (백엔드 스텁 상태).
  searchByImage: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await apiClient.post("/medications/search-by-image", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data as { candidates: unknown[] };
  },
};
