/**
 * API 클라이언트 베이스 (fetch wrapper). 모든 api/*.ts가 이걸 통해서만 호출한다.
 * 인증: JWT — Authorization: Bearer 헤더 (decision_log.md 2026-07, httpOnly 쿠키에서 변경).
 * Access Token은 메모리에만 보관 권장 (localStorage/sessionStorage 지양 — XSS 리스크).
 */
let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  // 콘솔에 수동으로 붙여넣을 때 줄바꿈/공백이 섞여 들어가는 실수를 방어한다.
  accessToken = token ? token.replace(/\s+/g, "") : token;
}

// 로그인 기능이 아직 없어 콘솔에서 수동으로 토큰을 넣어 테스트하는 용도.
// 프로덕션 빌드에는 포함되지 않는다 (import.meta.env.DEV).
if (import.meta.env.DEV) {
  (window as unknown as { __setToken: typeof setAccessToken }).__setToken = setAccessToken;
  (window as unknown as { __getToken: () => string | null }).__getToken = () => accessToken;
}

/** JSON이 아닌 응답(스트리밍 등)이 필요할 때 쓰는 저수준 fetch — chatApi.ts 참고. */
export async function apiFetchRaw(path: string, options: RequestInit = {}): Promise<Response> {
  const res = await fetch(`/api/v1${path}`, {
    ...options,
    // refresh_token이 httpOnly 쿠키로 내려오므로(백엔드 auth_routers.py), 쿠키를 계속 주고받으려면 필요하다.
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message ?? `API 오류 (${res.status})`);
  }
  return res;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetchRaw(path, options);
  return res.json() as Promise<T>;
}
