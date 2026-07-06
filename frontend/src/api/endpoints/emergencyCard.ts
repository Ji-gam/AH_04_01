// src/api/endpoints/emergencyCard.ts
import { apiClient } from "../client";
import type { EmergencyCard } from "../../types";

export const emergencyCardApi = {
  get: async (): Promise<EmergencyCard> => {
    const res = await apiClient.get("/emergency-cards");
    return res.data;
  },
  upsert: async (data: Partial<EmergencyCard>): Promise<EmergencyCard> => {
    const res = await apiClient.put("/emergency-cards", data);
    return res.data;
  },
};
