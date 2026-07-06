// src/api/endpoints/appointment.ts
import { apiClient } from "../client";
import type { AppointmentCreate } from "../../types";

export const appointmentApi = {
  create: (data: AppointmentCreate) => apiClient.post("/appointments", data),
  // TODO(조원 구현): 목록/취소 API는 백엔드에 아직 없습니다.
};
