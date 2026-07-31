import { useState } from "react";

export type LocationStatus = "idle" | "requesting" | "granted" | "denied" | "unsupported";

/**
 * 브라우저 위치 권한 요청 + 무료 역지오코딩(BigDataCloud)으로 "서울 강남구" 같은 사람이
 * 읽을 수 있는 지역명을 돌려주는 훅. 응급안내/홈 화면의 "가까운 OO 찾기" 카드가 공유한다.
 */
export function useNearbyRegionLabel() {
  const [status, setStatus] = useState<LocationStatus>("idle");
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [addressLabel, setAddressLabel] = useState<string | null>(null);

  const requestLocation = () => {
    if (!("geolocation" in navigator)) {
      setStatus("unsupported");
      return;
    }
    setStatus("requesting");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const next = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setCoords(next);
        setStatus("granted");
        fetch(
          `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${next.lat}&longitude=${next.lng}&localityLanguage=ko`,
        )
          .then((res) => res.json())
          .then((data: { city?: string; locality?: string }) => {
            const label = [data.city, data.locality].filter(Boolean).join(" ");
            if (label) setAddressLabel(label);
          })
          .catch(() => {
            // 주소 변환은 실패해도 좌표 기반 검색엔 문제 없으니 조용히 무시한다.
          });
      },
      () => setStatus("denied"),
    );
  };

  return { status, coords, addressLabel, requestLocation };
}
