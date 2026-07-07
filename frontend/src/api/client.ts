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

interface PydanticValidationError {
  loc: (string | number)[];
  msg: string;
}

/**
 * FastAPI 에러 응답의 `detail`은 두 가지 형태로 온다:
 * 1) HTTPException(detail="...") → 문자열
 * 2) Pydantic 유효성 검증 실패(422) → [{loc, msg, type, input}, ...] 배열
 * 배열을 그대로 Error에 넘기면 "[object Object]"로 찍힌다 — 반드시 문자열로 변환해야 한다.
 */
function extractErrorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((e: PydanticValidationError) => {
        const field = e.loc?.[e.loc.length - 1];
        return field ? `${field}: ${e.msg}` : e.msg;
      })
      .join(", ");
  }
  const message = (body as { message?: unknown } | undefined)?.message;
  if (typeof message === "string") {
    return message;
  }
  return `API 오류 (${status})`;
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
    throw new Error(extractErrorMessage(body, res.status));
  }
  return res;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetchRaw(path, options);
  return res.json() as Promise<T>;
}
