// src/api/endpoints/intakeLog.ts
import { apiClient } from "../client";
import type { IntakeLog } from "../../types";

export const intakeLogApi = {
  list: async (startDate?: string, endDate?: string): Promise<IntakeLog[]> => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const res = await apiClient.get(`/intake-logs?${params.toString()}`);
    return res.data;
  },
  markComplete: (logId: number, verificationMediaUrl?: string) =>
    apiClient.patch(`/intake-logs/${logId}`, {
      status: "COMPLETED",
      verification_media_url: verificationMediaUrl,
    }),
};
