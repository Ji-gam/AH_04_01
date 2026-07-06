// src/api/endpoints/schedule.ts
import { apiClient } from "../client";
import type { Schedule, ScheduleCreate } from "../../types";

export const scheduleApi = {
  list: async (): Promise<Schedule[]> => {
    const res = await apiClient.get("/medication-schedules");
    return res.data;
  },
  create: async (data: ScheduleCreate): Promise<Schedule> => {
    const res = await apiClient.post("/medication-schedules", data);
    return res.data;
  },
};
