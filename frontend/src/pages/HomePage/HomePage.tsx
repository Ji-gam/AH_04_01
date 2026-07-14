import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";

const DISMISS_KEY_PREFIX = "healthBannerDismissed_";

/** 시작화면. 로그인 유도는 상단 네비게이션(Layout)의 "로그인" 링크가 이미 담당하므로 여기서는
 * 따로 안 만든다 - 비로그인일 때 이 영역은 비워둬서 다른 조원분이 추가하는 카드(복약스케줄/알림 등)가
 * 자연스럽게 들어올 자리로 남긴다.
 * 로그인 상태면 아직 답 안 한 사람에게 건강정보 입력 유도 배너를 띄운다(팝업 대신 화면 안 카드 형태).
 * [주의] "안 뜨게 하기" 기록은 이메일별로 따로 저장한다 - 계정 하나로 껐다고 다른 계정까지
 * (같은 브라우저라도) 영향받으면 안 되기 때문. */
export default function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    if (user && localStorage.getItem(DISMISS_KEY_PREFIX + user.email) !== "true") {
      setShowBanner(true);
    } else {
      setShowBanner(false);
    }
  }, [user]);

  function handleDismiss() {
    if (user) localStorage.setItem(DISMISS_KEY_PREFIX + user.email, "true");
    setShowBanner(false);
  }

  function handleConfirm() {
    if (user) localStorage.setItem(DISMISS_KEY_PREFIX + user.email, "true");
    setShowBanner(false);
    navigate("/health-info/consent");
  }

  return (
    <div style={{ padding: "20px" }}>
      <h1>홈</h1>

      {user && (
        <p>
          안녕하세요, {user.name}님 ({user.email}) — profile_id: {user.profile_id}
        </p>
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
            자세한 건강관리를 받으시려면 건강정보를 입력해주세요!
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
