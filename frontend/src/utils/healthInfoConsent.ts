// 개인건강정보 제공동의 여부를 이메일별로 저장/조회한다. 계정 하나가 동의했다고 같은
// 브라우저의 다른 계정까지 동의한 걸로 치면 안 되기 때문(동의는 사람마다 따로 받아야 함 -
// 개인정보보호법 제23조 취지). ConsentPage/HealthInfoPage가 공통으로 쓴다.
//
// [주의] profile_id(자동증가 숫자)가 아니라 email로 키를 잡는다 - DB를 초기화하면
// profile_id가 다시 1번부터 시작되는데, 브라우저 localStorage는 DB랑 별개라 안 지워진다.
// 그래서 profile_id를 키로 쓰면 "예전에 지웠던 계정이 남긴 동의 기록을, 우연히 같은 번호를
// 받은 새 계정이 그대로 물려받는" 문제가 생긴다. email은 재사용되지 않으니 이 문제가 없다.
const CONSENT_KEY_PREFIX = "healthInfoConsentGiven_";

export function hasConsented(email: string): boolean {
  return localStorage.getItem(CONSENT_KEY_PREFIX + email) === "true";
}

export function markConsented(email: string): void {
  localStorage.setItem(CONSENT_KEY_PREFIX + email, "true");
}
