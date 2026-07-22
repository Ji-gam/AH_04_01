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

/** 앱이 켜질 때(로그인 여부/알림 권한과 무관하게) 무조건 한 번 호출한다 - PWA "홈 화면에
 * 추가" 설치 배너가 뜨려면 브라우저가 "이 페이지에 활성 서비스워커가 있다"를 페이지 로드
 * 시점에 확인해야 하기 때문이다. 예전엔 enableWebPush() 안에서만 등록해서, 사용자가
 * "알림 켜기"를 누르기 전까진 서비스워커가 아예 없어 설치 자체가 안 될 수 있었다
 * (2026-07-21, PWA 전환 준비 중 발견). 이미 등록돼 있으면 브라우저가 조용히 재사용하니
 * 여러 번 호출해도 안전하다. */
export async function registerServiceWorker(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  try {
    await navigator.serviceWorker.register("/service-worker.js");
  } catch (err) {
    // 설치 배너/푸시 둘 다 부가 기능이라, 실패해도 앱 사용 자체를 막지 않는다.
    console.error("서비스워커 등록 실패:", err);
  }
}

/** 브라우저 알림 권한을 요청하고, 웹푸시를 구독해서 서버에 등록한다. 서비스워커 자체는
 * registerServiceWorker()가 앱 시작 시 이미 등록해뒀다고 가정하고, 여기서는 그 등록을
 * 재사용만 한다(register()를 다시 불러도 안전하긴 하지만, 책임을 분리해서 "언제 뭘 하는지"
 * 명확히 하기 위함).
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
