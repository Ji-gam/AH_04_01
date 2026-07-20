import { pushApi } from "../api/pushApi";

// pushManager.subscribe()의 applicationServerKey는 Uint8Array(또는 ArrayBuffer)를 요구하는데,
// 서버가 주는 VAPID 공개키는 base64url 문자열이라 변환이 필요하다 (웹푸시 표준 예제 그대로).
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export type PushSubscribeStatus = "unsupported" | "denied" | "subscribed" | "error";

/** 브라우저 알림 권한을 요청하고, 서비스워커를 등록한 뒤, 웹푸시를 구독해서 서버에 등록한다.
 * 이미 구독돼 있으면(서비스워커가 기존 구독을 그대로 반환) 그 구독 정보를 그대로 서버에
 * 다시 보낸다 - 백엔드의 subscribe()가 같은 endpoint면 중복 저장 안 하게 되어 있다. */
export async function enableWebPush(): Promise<PushSubscribeStatus> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return "unsupported";
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    return "denied";
  }

  try {
    const registration = await navigator.serviceWorker.register("/service-worker.js");
    await navigator.serviceWorker.ready;

    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      const { public_key: vapidPublicKey } = await pushApi.getVapidPublicKey();
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey) as BufferSource,
      });
    }

    await pushApi.subscribe(subscription.toJSON() as PushSubscriptionJSON);
    return "subscribed";
  } catch (err) {
    console.error("웹푸시 구독 실패:", err);
    return "error";
  }
}

export async function disableWebPush(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.getRegistration("/service-worker.js");
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) return;
  await pushApi.unsubscribe(subscription.endpoint);
  await subscription.unsubscribe();
}
