import { apiFetch } from "./client";
import type { Disease, DiseaseSubtypeSearchResult } from "./types";

export const diseaseApi = {
  // 구체적 질환명 자동완성 검색 (원티드 스킬태그 검색과 같은 방식). q가 빈 문자열이면 해당
  // 대분류의 전체 목록을 보여준다.
  searchSubtypes: (category: Disease, q: string) =>
    apiFetch<DiseaseSubtypeSearchResult[]>(
      `/diseases/${category}/subtypes?q=${encodeURIComponent(q)}`,
    ),
};
