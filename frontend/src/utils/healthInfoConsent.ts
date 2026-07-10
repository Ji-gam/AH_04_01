// 개인건강정보 제공동의 여부를 profile_id별로 저장/조회한다. 계정 하나가 동의했다고 같은
// 브라우저의 다른 계정까지 동의한 걸로 치면 안 되기 때문(동의는 사람마다 따로 받아야 함 -
// 개인정보보호법 제23조 취지). ConsentPage/HealthInfoPage가 공통으로 쓴다.
const CONSENT_KEY_PREFIX = "healthInfoConsentGiven_";

export function hasConsented(profileId: number): boolean {
  return localStorage.getItem(CONSENT_KEY_PREFIX + profileId) === "true";
}

export function markConsented(profileId: number): void {
  localStorage.setItem(CONSENT_KEY_PREFIX + profileId, "true");
}
