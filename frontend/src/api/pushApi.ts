import { apiFetch, apiFetchRaw } from "./client";

export const pushApi = {
  getVapidPublicKey: () => apiFetch<{ public_key: string }>("/push/vapid-public-key"),
  subscribe: (subscription: PushSubscriptionJSON) =>
    apiFetchRaw("/push/subscribe", { method: "POST", body: JSON.stringify(subscription) }),
  unsubscribe: (endpoint: string) =>
    apiFetchRaw("/push/unsubscribe", { method: "POST", body: JSON.stringify({ endpoint }) }),
  registerFcmToken: (platform: "WEB" | "IOS" | "ANDROID", deviceToken: string) =>
    apiFetchRaw("/push/register-fcm-token", {
      method: "POST",
      body: JSON.stringify({ platform, device_token: deviceToken }),
    }),
  unregisterFcmToken: (deviceToken: string) =>
    apiFetchRaw("/push/unregister-fcm-token", {
      method: "POST",
      body: JSON.stringify({ device_token: deviceToken }),
    }),
};
