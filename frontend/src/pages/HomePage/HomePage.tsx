import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiFetch } from "../../api/client";
import { contentApi } from "../../api/contentApi";
import { healthInfoApi } from "../../api/healthInfoApi";
import { notificationApi } from "../../api/notificationApi";
import type {
  HealthContentResult,
  HealthInfoResult,
  NotificationScheduleResult,
} from "../../api/types";
import { useAuth } from "../../hooks/useAuth";
import type { MedicationSchedule } from "../../hooks/useMedication";
import { pinkTheme } from "../../theme/pinkTheme";
import Modal from "../AlarmPage/components/Modal";
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
  const [healthInfo, setHealthInfo] = useState<HealthInfoResult | null>(null);
  const [showMyInfo, setShowMyInfo] = useState(false);

  const [meds, setMeds] = useState<MedicationSchedule[]>([]);
  const [alarms, setAlarms] = useState<NotificationScheduleResult[]>([]);
  const [loading, setLoading] = useState(true);

  // 질환 등록자에게만 내려오는 맞춤 라이프스타일 추천(정보 탭과 같은 소스). 없으면 카드 숨김.
  const [lifestyleTips, setLifestyleTips] = useState<HealthContentResult[]>([]);

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

  useEffect(() => {
    // personalized=false는 질환 미등록 폴백(전체 공통 콘텐츠)이므로 홈 추천 카드는 띄우지 않는다.
    if (!user) {
      setLifestyleTips([]);
      return;
    }
    contentApi
      .getContents("LIFESTYLE", 3)
      .then((feed) => setLifestyleTips(feed.personalized ? feed.items.slice(0, 3) : []))
      .catch(() => setLifestyleTips([]));
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
        <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: "0 0 10px" }}>
          👋 안녕하세요{user ? `, ${user.name}님` : ""}!
        </h1>

        {user && (
          <button
            type="button"
            onClick={() => setShowMyInfo(true)}
            style={{
              border: `1px solid ${pinkTheme.border}`,
              background: pinkTheme.cardBg,
              color: pinkTheme.primary,
              borderRadius: 999,
              padding: "7px 16px",
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
              marginBottom: 20,
              boxShadow: "0 2px 6px rgba(255, 111, 145, 0.1)",
            }}
          >
            🙋 내 정보
          </button>
        )}

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
                  gap: 16,
                  background: pinkTheme.primarySoft,
                  borderRadius: 12,
                  padding: "14px 16px",
                }}
              >
                {/* 원형 진행률 — 오늘 몇 회 중 몇 번 복용했는지 도넛 안에 크게 표시 */}
                <svg
                  width="88"
                  height="88"
                  viewBox="0 0 88 88"
                  role="img"
                  aria-label="금일 복용 진행률"
                >
                  <circle
                    cx="44"
                    cy="44"
                    r="36"
                    fill="white"
                    stroke={pinkTheme.border}
                    strokeWidth="9"
                  />
                  <circle
                    cx="44"
                    cy="44"
                    r="36"
                    fill="none"
                    stroke={pinkTheme.primary}
                    strokeWidth="9"
                    strokeLinecap="round"
                    strokeDasharray={2 * Math.PI * 36}
                    strokeDashoffset={
                      2 * Math.PI * 36 * (1 - (totalCount ? doneCount / totalCount : 0))
                    }
                    transform="rotate(-90 44 44)"
                  />
                  <text
                    x="44"
                    y="50"
                    textAnchor="middle"
                    fontSize="19"
                    fontWeight="700"
                    fill={pinkTheme.primary}
                  >
                    {doneCount}/{totalCount}
                  </text>
                </svg>
                <div>
                  <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: pinkTheme.text }}>
                    ⏰ 금일 약 복용
                  </p>
                  <p style={{ margin: "4px 0 0", fontSize: 13, color: pinkTheme.textMuted }}>
                    {totalCount}회 중 <b style={{ color: pinkTheme.primary }}>{doneCount}번</b>{" "}
                    복용했어요
                  </p>
                </div>
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

        {/* 질환 등록자 맞춤 라이프스타일 추천 — 정보 탭(라이프스타일)과 같은 콘텐츠에서 3개 */}
        {user && lifestyleTips.length > 0 && (
          <Link to="/info" style={{ textDecoration: "none" }}>
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
                  margin: 0,
                  fontSize: 14,
                  fontWeight: 700,
                  color: pinkTheme.primary,
                }}
              >
                🌿 {user.name}님을 위한 추천 라이프스타일
              </p>
              <p style={{ margin: "4px 0 12px", fontSize: 12, color: pinkTheme.textMuted }}>
                오늘의 당신, 할 수 있어요!
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {lifestyleTips.map((tip) => (
                  <div
                    key={`${tip.disease_code}-${tip.content_date}-${tip.title}`}
                    style={{
                      background: pinkTheme.primarySoft,
                      borderRadius: 12,
                      padding: "10px 14px",
                      fontSize: 13,
                      fontWeight: 600,
                      color: pinkTheme.text,
                    }}
                  >
                    🌱 {tip.title}
                  </div>
                ))}
              </div>
            </div>
          </Link>
        )}

        {showBanner && (
          <div
            style={{
              background: pinkTheme.primarySoft,
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: "12px",
              padding: "16px 20px",
              marginBottom: 16,
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

        {/* 내 정보 모달 — 상단 "🙋 내 정보" 버튼으로 연다. 수정은 개인건강정보 화면에서. */}
        {user && showMyInfo && (
          <Modal onClose={() => setShowMyInfo(false)}>
            <div
              style={{
                background: pinkTheme.cardBg,
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: 16,
                padding: 18,
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
                🙋 내 정보
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  { label: "닉네임", value: user.name },
                  {
                    label: "성별",
                    value:
                      healthInfo?.gender === "MALE"
                        ? "남성"
                        : healthInfo?.gender === "FEMALE"
                          ? "여성"
                          : "미입력",
                  },
                  {
                    label: "키 / 몸무게",
                    value:
                      healthInfo?.height_cm || healthInfo?.weight_kg
                        ? `${healthInfo?.height_cm ?? "-"} cm / ${healthInfo?.weight_kg ?? "-"} kg`
                        : "미입력",
                  },
                  {
                    label: "BMI",
                    value: healthInfo?.bmi != null ? String(healthInfo.bmi) : "미입력",
                  },
                  { label: "알레르기", value: healthInfo?.special_notes || "없음" },
                ].map((row) => (
                  <div
                    key={row.label}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 12,
                      background: pinkTheme.primarySoft,
                      borderRadius: 12,
                      padding: "10px 14px",
                    }}
                  >
                    <span style={{ fontSize: 13, color: pinkTheme.textMuted, flexShrink: 0 }}>
                      {row.label}
                    </span>
                    <span
                      style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: pinkTheme.text,
                        textAlign: "right",
                        wordBreak: "break-all",
                      }}
                    >
                      {row.value}
                    </span>
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                <button
                  type="button"
                  onClick={() => {
                    setShowMyInfo(false);
                    navigate("/health-info");
                  }}
                  style={{
                    flex: 1,
                    padding: "11px 0",
                    border: "none",
                    borderRadius: 10,
                    background: pinkTheme.primary,
                    color: "#fff",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  수정
                </button>
                <button
                  type="button"
                  onClick={() => setShowMyInfo(false)}
                  style={{
                    padding: "11px 18px",
                    borderRadius: 10,
                    border: `1px solid ${pinkTheme.border}`,
                    background: pinkTheme.cardBg,
                    color: pinkTheme.textMuted,
                    cursor: "pointer",
                  }}
                >
                  닫기
                </button>
              </div>
            </div>
          </Modal>
        )}
      </div>
    </div>
  );
}
