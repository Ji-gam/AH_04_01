import { apiFetch } from "./client";
import type { HealthNewsDetailResult, HealthNewsFeedResult } from "./types";

/**
 * T-LLM-6 건강 뉴스. 기존 `contentApi`(T-LLM-3)를 대체한다.
 *
 * `/contents/me`와 마찬가지로 로그인 없이 호출 가능한 공개 엔드포인트다 — 건강 뉴스는
 * 사용자별 데이터가 아니고, 개인화 정렬이 붙기 전까지는 누가 봐도 같은 결과다.
 */
export const healthNewsApi = {
  getFeed: (limit?: number) => {
    const query = limit ? `?limit=${limit}` : "";
    return apiFetch<HealthNewsFeedResult>(`/news${query}`);
  },
  // 상세 응답에 card_summary가 함께 실려 오므로, [카드요약보기]에 추가 요청이 없다.
  getById: (id: number) => apiFetch<HealthNewsDetailResult>(`/news/${id}`),
};
