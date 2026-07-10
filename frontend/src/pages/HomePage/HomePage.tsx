import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiFetch } from "../../api/client";
import { notificationApi } from "../../api/notificationApi";
import type { NotificationScheduleResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";
import type { MedicationSchedule } from "../../hooks/useMedication";
import { pinkTheme } from "../../theme/pinkTheme";
import { toDateString } from "../AlarmPage/dateUtils";
import { buildGroups, loadChecked } from "../SchedulePage/scheduleData";

const DISMISS_KEY_PREFIX = "healthBannerDismissed_";

/** 시작화면. 로그인 유도는 상단 네비게이션(Layout)의 "로그인" 링크가 이미 담당하므로 여기서는
 * 따로 안 만든다 - 비로그인일 때 이 영역은 비워둔다.
 * 로그인 상태면 "오늘의 건강 카드"(금일 약 복용 현황)를 보여주고,
 * 아직 답 안 한 사람에게는 건강정보 입력 유도 배너도 같이 띄운다(팝업 대신 화면 안 카드 형태).
 * [주의] "안 뜨게 하기" 기록은 profile_id별로 따로 저장한다 - 계정 하나로 껐다고 다른 계정까지
 * (같은 브라우저라도) 영향받으면 안 되기 때문. */
export default function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [showBanner, setShowBanner] = useState(false);

  const [meds, setMeds] = useState<MedicationSchedule[]>([]);
  const [alarms, setAlarms] = useState<NotificationScheduleResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user && localStorage.getItem(DISMISS_KEY_PREFIX + user.profile_id) !== "true") {
      setShowBanner(true);
    } else {
      setShowBanner(false);
    }
  }, [user]);

  useEffect(() => {
    Promise.all([apiFetch<MedicationSchedule[]>("/medications"), notificationApi.list()])
      .then(([m, a]) => {
        setMeds(m);
        setAlarms(a);
      })
      .catch(() => {
        // 홈의 건강 카드는 참고용 요약이라, 실패해도 화면 전체를 막지 않고 카드만 조용히 숨긴다.
      })
      .finally(() => setLoading(false));
  }, []);

  function handleDismiss() {
    if (user) localStorage.setItem(DISMISS_KEY_PREFIX + user.profile_id, "true");
    setShowBanner(false);
  }

  function handleConfirm() {
    if (user) localStorage.setItem(DISMISS_KEY_PREFIX + user.profile_id, "true");
    setShowBanner(false);
    navigate("/health-info/consent");
  }

  const today = new Date();
  const groups = buildGroups(meds, alarms, today);
  const totalCount = groups.reduce((n, g) => n + g.items.length, 0);
  const checked = loadChecked(toDateString(today));
  const doneCount = groups.reduce(
    (n, g) => n + g.items.filter((i) => checked.has(i.key)).length,
    0,
  );

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100vh", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: "0 0 20px" }}>
          👋 안녕하세요{user ? `, ${user.name}님` : ""}!
        </h1>

        {user && !loading && totalCount > 0 && (
          <Link to="/schedule" style={{ textDecoration: "none" }}>
            <div
              style={{
                background: pinkTheme.cardBg,
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: 16,
                padding: 18,
                marginBottom: 16,
                boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
              }}
            >
              <p
                style={{
                  margin: "0 0 12px",
                  fontSize: 14,
                  fontWeight: 700,
                  color: pinkTheme.primary,
                }}
              >
                💗 오늘의 건강 카드
              </p>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: pinkTheme.primarySoft,
                  borderRadius: 12,
                  padding: "12px 14px",
                }}
              >
                <span style={{ fontSize: 14, color: pinkTheme.text }}>⏰ 금일 약 복용</span>
                <span style={{ fontSize: 15, fontWeight: 700, color: pinkTheme.primary }}>
                  {doneCount} / {totalCount} 완료
                </span>
              </div>
            </div>
          </Link>
        )}

        {user && !loading && totalCount === 0 && (
          <div
            style={{
              background: pinkTheme.cardBg,
              border: `1px dashed ${pinkTheme.border}`,
              borderRadius: 16,
              padding: 24,
              marginBottom: 16,
              textAlign: "center",
              color: pinkTheme.textMuted,
            }}
          >
            <p style={{ fontSize: 26, margin: 0 }}>🌸</p>
            <p style={{ fontSize: 13, margin: "8px 0 0" }}>
              오늘 등록된 약이 없어요.{" "}
              <Link to="/alarms" style={{ color: pinkTheme.primary }}>
                복약알림 등록하러 가기
              </Link>
            </p>
          </div>
        )}

        {showBanner && (
          <div
            style={{
              background: pinkTheme.primarySoft,
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: "12px",
              padding: "16px 20px",
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
    </div>
  );
}
