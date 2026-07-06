// src/api/endpoints/foodIntake.ts
import { apiClient } from "../client";
import type { FoodIntakeCreate } from "../../types";

export const foodIntakeApi = {
  create: (data: FoodIntakeCreate) => apiClient.post("/food-intake-logs", data),
};
