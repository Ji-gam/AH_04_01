import { apiFetch } from "./client";
import type {
  ContentCategory,
  ContentsFeedResult,
  GenerateContentPayload,
  HealthContentResult,
  RelatedContentResult,
} from "./types";

export const contentApi = {
  // 로그인 없이도 호출 가능한 공개 엔드포인트다(T-LLM-3, app/apis/v1/content_routers.py 참고).
  getContents: (category?: ContentCategory, limit?: number) => {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (limit) params.set("limit", String(limit));
    const query = params.toString();
    return apiFetch<ContentsFeedResult>(`/contents/me${query ? `?${query}` : ""}`);
  },
  // [QA 전용] 실제로 ai_worker LLM 생성을 호출한다. 더보기 > 컨텐츠생성 화면 전용.
  generate: (payload: GenerateContentPayload = {}) =>
    apiFetch<HealthContentResult>("/contents/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // "정보" 탭 상세화면(T-LLM-3-1) 전용 — 라우터 state가 아니라 항상 서버에서 다시 조회하므로
  // 새로고침/직접 URL 접근에도 동작한다.
  getContentById: (id: number) => apiFetch<HealthContentResult>(`/contents/${id}`),
  getRelatedContents: (id: number, limit?: number) => {
    const query = limit ? `?limit=${limit}` : "";
    return apiFetch<RelatedContentResult>(`/contents/${id}/related${query}`);
  },
};
