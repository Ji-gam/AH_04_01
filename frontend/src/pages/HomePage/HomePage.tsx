import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { healthInfoApi } from "../../api/healthInfoApi";
import type { HealthInfoResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";

const DISMISS_KEY_PREFIX = "healthBannerDismissed_";

/** 시작화면. 로그인 유도는 상단 네비게이션(Layout)의 "로그인" 링크가 이미 담당하므로 여기서는
 * 따로 안 만든다 - 비로그인일 때 이 영역은 비워둬서 다른 조원분이 추가하는 카드(복약스케줄/알림 등)가
 * 자연스럽게 들어올 자리로 남긴다.
 * 로그인 상태면 아직 답 안 한 사람에게 건강정보 입력 유도 배너를 띄운다(팝업 대신 화면 안 카드 형태).
 * [주의] "안 뜨게 하기" 기록은 profile_id별로 따로 저장한다 - 계정 하나로 껐다고 다른 계정까지
 * (같은 브라우저라도) 영향받으면 안 되기 때문. */
export default function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [showBanner, setShowBanner] = useState(false);
  const [healthInfo, setHealthInfo] = useState<HealthInfoResult | null>(null);

  useEffect(() => {
    if (user && localStorage.getItem(DISMISS_KEY_PREFIX + user.profile_id) !== "true") {
      setShowBanner(true);
    } else {
      setShowBanner(false);
    }
  }, [user]);

  useEffect(() => {
    // [QA 전용 디버그 카드] 테스트 중 "지금 로그인한 계정에 뭐가 입력돼 있었는지" 헷갈리지
    // 않도록, 계정+건강정보를 전부 그대로 덤프한다. 디자인 없음(barebone) 의도적.
    if (!user) {
      setHealthInfo(null);
      return;
    }
    healthInfoApi
      .get()
      .then(setHealthInfo)
      .catch(() => setHealthInfo(null));
  }, [user]);

  function handleDismiss() {
    if (user) localStorage.setItem(DISMISS_KEY_PREFIX + user.profile_id, "true");
    setShowBanner(false);
  }

  function handleConfirm() {
    if (user) localStorage.setItem(DISMISS_KEY_PREFIX + user.profile_id, "true");
    setShowBanner(false);
    navigate("/health-info/consent");
  }

  return (
    <div style={{ padding: "20px" }}>
      <h1>홈</h1>

      {user && (
        <div
          style={{
            border: "1px solid black",
            padding: "10px",
            marginTop: "10px",
            fontFamily: "monospace",
            fontSize: "12px",
            whiteSpace: "pre-wrap",
          }}
        >
          <strong>[QA 디버그] 현재 로그인 계정 전체 정보</strong>
          <br />
          --- 계정(User) ---
          <br />
          id: {user.id}
          <br />
          profile_id: {user.profile_id}
          <br />
          name: {user.name}
          <br />
          email: {user.email}
          <br />
          phone_number: {user.phone_number ?? "(없음)"}
          <br />
          gender: {user.gender ?? "(없음)"}
          <br />
          created_at: {user.created_at}
          <br />
          --- 개인건강정보(HealthInfo) ---
          <br />
          {healthInfo ? (
            <>
              age: {healthInfo.age ?? "(없음)"}
              <br />
              gender: {healthInfo.gender ?? "(없음)"}
              <br />
              height_cm: {healthInfo.height_cm ?? "(없음)"}
              <br />
              weight_kg: {healthInfo.weight_kg ?? "(없음)"}
              <br />
              bmi: {healthInfo.bmi ?? "(없음)"}
              <br />
              diagnosis_history: {JSON.stringify(healthInfo.diagnosis_history)}
              <br />
              family_history: {JSON.stringify(healthInfo.family_history)}
              <br />
              special_notes: {healthInfo.special_notes || "(없음)"}
              <br />
              other_notes: {healthInfo.other_notes || "(없음)"}
            </>
          ) : (
            "(건강정보 불러오는 중 또는 없음)"
          )}
        </div>
      )}

      {showBanner && (
        <div
          style={{
            background: pinkTheme.primarySoft,
            border: `1px solid ${pinkTheme.border}`,
            borderRadius: "12px",
            padding: "16px 20px",
            marginTop: "16px",
          }}
        >
          <p style={{ color: pinkTheme.text, fontWeight: 600, margin: "0 0 12px" }}>
            안녕하세요 건강정보를 입력해주시면 더 좋은 서비스가 가능합니다! 입력하시겠습니까?
          </p>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              onClick={handleConfirm}
              style={{
                flex: 1,
                padding: "10px",
                border: "none",
                borderRadius: "8px",
                background: pinkTheme.primary,
                color: "#fff",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              확인
            </button>
            <button
              type="button"
              onClick={handleDismiss}
              style={{
                flex: 1,
                padding: "10px",
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: "8px",
                background: pinkTheme.cardBg,
                color: pinkTheme.textMuted,
                cursor: "pointer",
              }}
            >
              아니오
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
