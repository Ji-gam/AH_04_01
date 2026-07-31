import { apiFetch, apiFetchRaw } from "./client";

export type PushSourceType = "notification_schedule" | "medication_schedule";

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
  // 아래 셋(markTaken/reduceFrequency/snooze)은 원래 service-worker.js가 액션 버튼 클릭 시
  // 인증 없이 직접 호출하던 엔드포인트다(로그인 세션에 접근 불가) - 알림 본문을 탭해서 여는
  // 인앱 스누즈 화면(SnoozeSheet, F-NTFY-3)에서도 같은 엔드포인트를 그대로 재사용한다.
  markTaken: (profileId: number, sourceType: PushSourceType, sourceId: number, alarmTime: string) =>
    apiFetchRaw("/push/mark-taken", {
      method: "POST",
      body: JSON.stringify({
        profile_id: profileId,
        source_type: sourceType,
        source_id: sourceId,
        alarm_time: alarmTime,
      }),
    }),
  reduceFrequency: (
    profileId: number,
    sourceType: PushSourceType,
    sourceId: number,
    alarmTime: string,
  ) =>
    apiFetchRaw("/push/reduce-frequency", {
      method: "POST",
      body: JSON.stringify({
        profile_id: profileId,
        source_type: sourceType,
        source_id: sourceId,
        alarm_time: alarmTime,
      }),
    }),
  snooze: (
    profileId: number,
    sourceType: PushSourceType,
    sourceId: number,
    name: string,
    alarmTime: string,
    minutes: 30 | 60,
  ) =>
    apiFetchRaw("/push/snooze", {
      method: "POST",
      body: JSON.stringify({
        profile_id: profileId,
        source_type: sourceType,
        source_id: sourceId,
        name,
        alarm_time: alarmTime,
        minutes,
      }),
    }),
};
