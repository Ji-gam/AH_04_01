// "데이터 활용 동의" 화면(건강정보/AI상담/위치정보/마케팅)의 항목별 동의 여부를 이메일별로
// 저장/조회한다. healthInfoConsent.ts와 같은 이유로 profile_id가 아니라 email을 키로 쓴다 -
// DB를 초기화하면 profile_id가 재사용될 수 있어, 이전 계정의 동의 기록을 새 계정이 물려받는
// 문제를 막기 위함이다.
export type ConsentKey =
  "termsOfService" | "health" | "sensitiveInfo" | "location" | "aiChat" | "marketing";

export type DataConsent = Record<ConsentKey, boolean>;

const STORAGE_KEY_PREFIX = "dataConsent_";

// 이용약관/건강정보/민감정보/위치정보는 서비스 핵심 기능(가입, 맞춤 알림, 응급카드,
// 응급실·약국 찾기)에 필요해 기본값을 켜둔다.
export const DEFAULT_CONSENT: DataConsent = {
  termsOfService: true,
  health: true,
  sensitiveInfo: true,
  aiChat: true,
  location: true,
  marketing: false,
};

export function loadConsent(email: string): DataConsent {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PREFIX + email);
    return raw
      ? { ...DEFAULT_CONSENT, ...(JSON.parse(raw) as Partial<DataConsent>) }
      : DEFAULT_CONSENT;
  } catch {
    return DEFAULT_CONSENT;
  }
}

export function saveConsent(email: string, consent: DataConsent): void {
  localStorage.setItem(STORAGE_KEY_PREFIX + email, JSON.stringify(consent));
}
