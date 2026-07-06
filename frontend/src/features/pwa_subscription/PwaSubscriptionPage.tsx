import PlaceholderPage from "../../components/ui/PlaceholderPage";
export default function PwaSubscriptionPage() {
  return (
    <PlaceholderPage
      title="푸시 알림 설정"
      apiFile="src/api/endpoints/pwaSubscription.ts"
      note="브라우저 Push API로 구독 정보(endpoint_url 등)를 만드는 부분부터 필요합니다 (navigator.serviceWorker.ready 등)."
    />
  );
}
