/** 위치 권한이 없거나 실패했을 때 쓰는 기본 지역명 — 위치 없이도 서울 중심으로 미리보기를 제공한다. */
export const DEFAULT_REGION_LABEL = "서울";

/**
 * 카카오맵 장소검색 공유링크(API 키 불필요)는 "검색어,위도,경도" 형식을 지원하지 않고 좌표를
 * 검색어 문자열로 그대로 취급해 검색결과가 안 나온다(직접 확인함). 대신 지역명을 검색어 앞에
 * 붙이면("서울 강남구 응급실") 카카오맵이 해당 지역 기준으로 정상 검색해준다.
 */
export function buildKakaoMapSearchUrl(query: string, regionLabel: string): string {
  return `https://map.kakao.com/link/search/${encodeURIComponent(`${regionLabel} ${query}`)}`;
}

export function openNearbySearch(query: string, regionLabel: string): void {
  window.open(buildKakaoMapSearchUrl(query, regionLabel), "_blank", "noopener,noreferrer");
}
