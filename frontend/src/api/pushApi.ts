import { apiFetch, apiFetchRaw } from "./client";

export const pushApi = {
  getVapidPublicKey: () => apiFetch<{ public_key: string }>("/push/vapid-public-key"),
  subscribe: (subscription: PushSubscriptionJSON) =>
    apiFetchRaw("/push/subscribe", { method: "POST", body: JSON.stringify(subscription) }),
  unsubscribe: (endpoint: string) =>
    apiFetchRaw("/push/unsubscribe", { method: "POST", body: JSON.stringify({ endpoint }) }),
};
