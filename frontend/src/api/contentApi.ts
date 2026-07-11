import { apiFetch } from "./client";
import type { ContentCategory, ContentsFeedResult } from "./types";

export const contentApi = {
  // 로그인 없이도 호출 가능한 공개 엔드포인트다(T-LLM-3, app/apis/v1/content_routers.py 참고).
  getContents: (category?: ContentCategory, limit?: number) => {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (limit) params.set("limit", String(limit));
    const query = params.toString();
    return apiFetch<ContentsFeedResult>(`/contents/me${query ? `?${query}` : ""}`);
  },
};
