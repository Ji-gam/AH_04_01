// src/api/endpoints/pwaSubscription.ts
import { apiClient } from "../client";
import type { SubscriptionCreate } from "../../types";

export const pwaSubscriptionApi = {
  register: (data: SubscriptionCreate) => apiClient.post("/pwa-subscriptions", data),
  unsubscribe: (endpoint_url: string) => apiClient.delete("/pwa-subscriptions", { data: { endpoint_url } }),
};
