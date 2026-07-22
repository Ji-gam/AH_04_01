import { type FirebaseApp, getApps, initializeApp } from "firebase/app";
import { deleteToken, getMessaging, getToken, isSupported } from "firebase/messaging";

import { pushApi } from "../api/pushApi";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY;

function isFirebaseConfigured(): boolean {
  return Boolean(
    firebaseConfig.apiKey && firebaseConfig.projectId && firebaseConfig.appId && vapidKey,
  );
}

function getFirebaseApp(): FirebaseApp {
  const existing = getApps();
  return existing.length > 0 ? existing[0] : initializeApp(firebaseConfig);
}

// getToken()에 넘겨서 서버에 등록한 토큰 - disableFcmWeb()이 해제 요청을 보낼 때 필요하다.
let lastRegisteredToken: string | null = null;

/** FCM(Firebase Cloud Messaging) 구독 - 기존 웹푸시(pywebpush/VAPID)와 나란히 시도하는
 * 추가 채널이다. 별도의 firebase-messaging-sw.js를 새로 두지 않고 이미 등록된
 * service-worker.js를 그대로 재사용한다(getToken()의 serviceWorkerRegistration 옵션) -
 * FCM 웹푸시도 결국 표준 브라우저 Push API를 타므로, service-worker.js의 기존 'push'
 * 이벤트 리스너가 그대로 받아 처리한다. 이렇게 하면 Firebase SDK 코드를 서비스워커 안에
 * 넣지 않아도 되어, 기존 스누즈/빈도줄이기/부작용알림 액션 버튼 처리 로직과 충돌할
 * 위험(중복 알림, notificationclick 핸들러 덮어쓰기 - firebase-js-sdk 이슈로 보고된 바 있음)이
 * 없다.
 *
 * .env에 Firebase 설정값(VITE_FIREBASE_*)이 비어있으면 조용히 건너뛴다 - 아직 설정 전이라도
 * 기존 웹푸시(enableWebPush)는 그대로 동작해야 하기 때문이다. */
export async function enableFcmWeb(): Promise<void> {
  if (!isFirebaseConfigured()) return;
  if (!("serviceWorker" in navigator)) return;

  const supported = await isSupported().catch(() => false);
  if (!supported) return;

  try {
    const messaging = getMessaging(getFirebaseApp());
    const registration = await navigator.serviceWorker.ready;

    const token = await getToken(messaging, { vapidKey, serviceWorkerRegistration: registration });
    if (!token) return;

    lastRegisteredToken = token;
    await pushApi.registerFcmToken("WEB", token);
  } catch (err) {
    console.error("FCM 구독 실패:", err);
  }
}

export async function disableFcmWeb(): Promise<void> {
  if (!isFirebaseConfigured() || !lastRegisteredToken) return;
  try {
    const messaging = getMessaging(getFirebaseApp());
    await deleteToken(messaging);
    await pushApi.unregisterFcmToken(lastRegisteredToken);
    lastRegisteredToken = null;
  } catch (err) {
    console.error("FCM 구독 해제 실패:", err);
  }
}
