// "홈 화면에 추가" 설치 배너를 한 번 닫으면 다시 안 보이게 하는 저장소.
//
// 건강정보 배너(healthBannerDismiss.ts)와 달리 sessionStorage가 아니라 localStorage를
// 쓴다 - 설치 여부는 "이 기기/브라우저"에 대한 결정이라 로그인 세션이나 탭 닫힘과 무관하게
// 계속 기억해야 한다(매번 탭 열 때마다 다시 물어보면 성가시다). 로그인 여부와도 무관하므로
// profile_id별 구분도 필요 없다.
const DISMISS_KEY = "installPromptDismissed";

export function isInstallPromptDismissed(): boolean {
  return localStorage.getItem(DISMISS_KEY) === "true";
}

export function dismissInstallPrompt(): void {
  localStorage.setItem(DISMISS_KEY, "true");
}
