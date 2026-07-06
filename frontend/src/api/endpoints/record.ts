// src/api/endpoints/record.ts
import { apiClient } from "../client";
import type { RecordDetail } from "../../types";

export const recordApi = {
  uploadOcr: async (file: File, documentType: "PRESCRIPTION" | "BAG") => {
    const form = new FormData();
    form.append("file", file);
    form.append("document_type", documentType);
    const res = await apiClient.post("/medical-records/ocr", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data as { task_id: string; status: string };
  },
  getOcrStatus: async (taskId: string) => {
    const res = await apiClient.get(`/medical-records/ocr/status/${taskId}`);
    return res.data;
  },
  create: (data: Record<string, unknown>) => apiClient.post("/medical-records", data),
  getDetail: async (recordId: number): Promise<RecordDetail> => {
    const res = await apiClient.get(`/medical-records/${recordId}`);
    return res.data;
  },
};
