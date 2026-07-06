// src/api/endpoints/generatedGuide.ts
import { apiClient } from "../client";
import type { GeneratedGuide } from "../../types";

export const generatedGuideApi = {
  requestGuide: (recordId: number, guideType: string) =>
    apiClient.post("/generated-guides", { record_id: recordId, guide_type: guideType }),
  getGuide: async (guideId: number): Promise<GeneratedGuide> => {
    const res = await apiClient.get(`/generated-guides/${guideId}`);
    return res.data;
  },
};
