import { apiFetch } from "./client";
import type { ContentCategory, ContentsFeedResult } from "./types";

export const contentApi = {
  // 로그인 없이도 호출 가능한 공개 엔드포인트다(T-LLM-3, app/apis/v1/content_routers.py 참고).
  getContents: (category?: ContentCategory) =>
    apiFetch<ContentsFeedResult>(`/contents/me${category ? `?category=${category}` : ""}`),
};
