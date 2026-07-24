/// <reference types="vite/client" />

interface ImportMetaEnv {
  // FCM(Firebase Cloud Messaging) 웹 설정값 - Firebase 콘솔 > 프로젝트 설정에서 발급받는다.
  // 비어있으면 fcmWeb.ts가 조용히 FCM 구독을 건너뛴다(기존 웹푸시는 그대로 동작).
  readonly VITE_FIREBASE_API_KEY?: string;
  readonly VITE_FIREBASE_PROJECT_ID?: string;
  readonly VITE_FIREBASE_MESSAGING_SENDER_ID?: string;
  readonly VITE_FIREBASE_APP_ID?: string;
  // 클라우드 메시징 탭 > "웹 푸시 인증서" - 우리가 쓰는 VAPID_PUBLIC_KEY(pywebpush용)와는
  // 다른, Firebase 전용 VAPID 키다.
  readonly VITE_FIREBASE_VAPID_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
