import { useState } from "react";
import { useNavigate } from "react-router-dom";

import DisclaimerBanner from "../../components/common/DisclaimerBanner";
import { pinkTheme as t } from "../../theme/pinkTheme";
import { DEFAULT_REGION_LABEL, openNearbySearch } from "../../utils/kakaoMapSearch";

type LocationStatus = "idle" | "requesting" | "granted" | "denied" | "unsupported";

const cardStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  width: "100%",
  boxSizing: "border-box",
  padding: "16px",
  borderRadius: 16,
  border: `1px solid ${t.border}`,
  background: t.cardBg,
  cursor: "pointer",
  textDecoration: "none",
  color: t.text,
  font: "inherit",
  boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
};

const iconCircleStyle: React.CSSProperties = {
  width: 40,
  height: 40,
  borderRadius: "50%",
  background: t.primarySoft,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 18,
  flexShrink: 0,
};

interface ActionCardProps {
  icon: string;
  title: string;
  desc: string;
  href?: string;
  onClick?: () => void;
}

function ActionCard({ icon, title, desc, href, onClick }: ActionCardProps) {
  const content = (
    <>
      <span style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={iconCircleStyle}>{icon}</span>
        <span style={{ textAlign: "left" }}>
          <strong style={{ display: "block", fontSize: 15 }}>{title}</strong>
          <span style={{ fontSize: 12, color: t.textMuted }}>{desc}</span>
        </span>
      </span>
      <span aria-hidden style={{ color: t.textMuted }}>
        ›
      </span>
    </>
  );

  if (href) {
    return (
      <a href={href} style={cardStyle}>
        {content}
      </a>
    );
  }
  return (
    <button type="button" onClick={onClick} style={cardStyle}>
      {content}
    </button>
  );
}

export default function EmergencyGuidePage() {
  const navigate = useNavigate();
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

  const handleNearbySearch = (query: string) => {
    openNearbySearch(query, addressLabel ?? DEFAULT_REGION_LABEL);
  };

  return (
    <div style={{ background: t.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <button
            type="button"
            aria-label="뒤로"
            onClick={() => navigate("/more")}
            style={{
              border: "none",
              background: "none",
              color: t.text,
              fontSize: 20,
              cursor: "pointer",
              lineHeight: 1,
            }}
          >
            ←
          </button>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: t.text, margin: 0 }}>🚨 응급 안내</h1>
        </div>

        <p style={{ margin: "0 0 16px", fontSize: 14, fontWeight: 700, color: t.danger }}>
          응급 상황 시 119로 즉시 연락하세요
        </p>

        {status !== "granted" && (
          <div
            style={{
              marginBottom: 14,
              padding: "12px 14px",
              borderRadius: 14,
              background: t.primarySoft,
              fontSize: 13,
              color: t.text,
              lineHeight: 1.5,
            }}
          >
            📍 현재 위치를 허용하면 가까운 병원·약국·응급실을 더 정확히 찾아드려요.
            {status === "denied" && (
              <span style={{ display: "block", marginTop: 4, color: t.textMuted }}>
                위치 권한이 꺼져 있어 서울 중심으로 안내해요. 브라우저 설정에서 위치 권한을
                허용해주세요.
              </span>
            )}
            {status === "unsupported" && (
              <span style={{ display: "block", marginTop: 4, color: t.textMuted }}>
                이 브라우저는 위치 확인을 지원하지 않아 서울 중심으로 안내해요.
              </span>
            )}
            {(status === "idle" || status === "requesting") && (
              <button
                type="button"
                onClick={requestLocation}
                disabled={status === "requesting"}
                style={{
                  display: "block",
                  marginTop: 8,
                  padding: "8px 14px",
                  borderRadius: 10,
                  border: "none",
                  background: t.primary,
                  color: "#fff",
                  fontWeight: 700,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                {status === "requesting" ? "위치 확인 중..." : "위치 허용하기"}
              </button>
            )}
          </div>
        )}

        {status === "granted" && coords && (
          <p style={{ margin: "0 0 14px", fontSize: 12, color: t.textMuted }}>
            📍 현재 위치:{" "}
            {addressLabel ?? `위도 ${coords.lat.toFixed(3)}, 경도 ${coords.lng.toFixed(3)}`}
          </p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
          <ActionCard icon="📞" title="119" desc="응급구조·소방" href="tel:119" />
          <ActionCard
            icon="📍"
            title="가까운 병원 찾기"
            desc="현재 위치 기준"
            onClick={() => handleNearbySearch("병원")}
          />
          <ActionCard
            icon="📍"
            title="가까운 약국 찾기"
            desc="현재 위치 기준"
            onClick={() => handleNearbySearch("약국")}
          />
          <ActionCard
            icon="📍"
            title="가까운 응급실 찾기"
            desc="현재 위치 기준"
            onClick={() => handleNearbySearch("응급실")}
          />
        </div>

        <DisclaimerBanner />
      </div>
    </div>
  );
}
