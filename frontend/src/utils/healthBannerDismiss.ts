// 홈 화면의 "건강정보 입력하시겠어요?" 배너를 "이번 로그인 세션 동안만" 숨기기 위한 저장소.
//
// localStorage가 아니라 sessionStorage를 쓰는 이유:
// - 앱(브라우저 탭)을 껐다가 다시 켜면 다시 물어봐야 한다 -> sessionStorage는 탭/브라우저를
//   닫으면 자동으로 비워지므로 별도 처리 없이 이 요구사항이 충족된다.
// - 로그인해서 앱을 쓰는 도중에는 "아니오"를 누른 뒤 화면을 옮겨다녀도 다시 뜨면 안 된다 ->
//   세션 동안은 값이 유지되므로 이것도 충족된다.
// - 로그아웃 후 (탭은 안 닫고) 같은 계정 혹은 다른 계정으로 다시 로그인하면, 그 "로그인 시점"에
//   다시 물어봐야 한다 -> 이건 sessionStorage의 자연 수명만으로는 안 풀리므로, useAuth의 login()
//   성공 시점에 clearDismissalForNewLogin()을 명시적으로 호출해서 리셋한다.
//
// profile_id별로 키를 잡아 계정마다 따로 관리한다 (계정 A에서 껐다고 계정 B까지 안 뜨면 안 됨).
const DISMISS_KEY_PREFIX = "healthBannerDismissed_";

export function isDismissedThisSession(profileId: number | string): boolean {
  return sessionStorage.getItem(DISMISS_KEY_PREFIX + profileId) === "true";
}

export function dismissForSession(profileId: number | string): void {
  sessionStorage.setItem(DISMISS_KEY_PREFIX + profileId, "true");
}

/** 로그인 성공 시점마다 호출한다 - 탭을 안 닫고 로그아웃 후 재로그인하는 경우에도
 * 배너를 다시 물어보게 하기 위함(sessionStorage는 탭 단위라 이 경우까진 못 잡아준다). */
export function clearDismissalForNewLogin(profileId: number | string): void {
  sessionStorage.removeItem(DISMISS_KEY_PREFIX + profileId);
}
