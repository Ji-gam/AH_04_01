import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiFetch } from "../../api/client";
import { familyApi, type FamilyLinkItem } from "../../api/familyApi";
import { habitApi } from "../../api/habitApi";
import { healthInfoApi } from "../../api/healthInfoApi";
import { notificationApi } from "../../api/notificationApi";
import type {
  HabitsTodayResult,
  HealthInfoResult,
  NotificationScheduleResult,
} from "../../api/types";
import HabitSelectionContent from "../../components/habit/HabitSelectionContent";
import SelectedHabitsModal from "../../components/habit/SelectedHabitsModal";
import { useAuth } from "../../hooks/useAuth";
import type { MedicationSchedule } from "../../hooks/useMedication";
import { useNearbyRegionLabel } from "../../hooks/useNearbyRegionLabel";
import { pinkTheme } from "../../theme/pinkTheme";
import { dismissForSession, isDismissedThisSession } from "../../utils/healthBannerDismiss";
import { DEFAULT_REGION_LABEL, openNearbySearch } from "../../utils/kakaoMapSearch";
import Modal from "../AlarmPage/components/Modal";
import { toDateString } from "../AlarmPage/dateUtils";
import { buildGroups, loadChecked } from "../SchedulePage/scheduleData";
import SchedulePage from "../SchedulePage/SchedulePage";

/** 홈 화면 2x2 바로가기 그리드 항목. */
const QUICK_LINKS: { to: string; icon: string; label: string }[] = [
  { to: "/alarms", icon: "🔔", label: "복약알림" },
  { to: "/chat", icon: "💬", label: "AI 상담" },
  { to: "/info", icon: "📖", label: "건강정보" },
  { to: "/medication", icon: "➕", label: "약 등록" },
];

/** 건강정보 중 하나라도 채워져 있으면 "입력했다"고 본다 - 항목 전부를 다 채울 필요는 없다.
 * 백엔드에 별도의 "입력 완료" 플래그가 없고 전부 nullable 필드라, 이렇게 판단한다. */
function hasEnteredHealthInfo(info: HealthInfoResult | null): boolean {
  if (!info) return false;
  return (
    info.gender !== null ||
    info.birth_date !== null ||
    info.height_cm !== null ||
    info.weight_kg !== null ||
    info.is_pregnant !== null ||
    info.diagnosis_history.length > 0 ||
    info.family_history.length > 0 ||
    !!info.special_notes ||
    !!info.other_notes
  );
}

/** 시작화면. 로그인 유도는 상단 네비게이션(Layout)의 "로그인" 링크가 이미 담당하므로 여기서는
 * 따로 안 만든다 - 비로그인일 때 이 영역은 비워둔다.
 * 화면 맨 위(인사말 바로 아래)엔 건강정보 입력 유도 배너를 먼저 두고, 그 아래에 가족 연결
 * 요청 알림을 둔다(둘 다 화면 최상단 근처 - 다른 카드들보다 우선).
 * 로그인 상태면 "오늘의 건강 카드"(금일 약 복용 현황)도 보여준다.
 * [주의] "안 뜨게 하기"는 이번 로그인 세션 동안만 유지된다(sessionStorage) - 앱을 껐다 켜거나
 * 다시 로그인하면 매번 새로 물어본다. healthBannerDismiss.ts 참고.
 * [주의2] 건강정보를 이미 하나라도 입력했으면(hasEnteredHealthInfo) 세션 dismiss 여부와
 * 무관하게 배너 자체를 안 띄운다 - 이미 입력한 사람한테 계속 "입력하시겠습니까"를 물어보는
 * 건 UX상 맞지 않다(2026-07-20 수정). */
export default function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [showBanner, setShowBanner] = useState(false);
  const [healthInfo, setHealthInfo] = useState<HealthInfoResult | null>(null);
  const [showMyInfo, setShowMyInfo] = useState(false);

  // 가족관리 - 내가 받은, 아직 응답 안 한 연결 요청. 더보기 > 가족관리 화면 안에서만 보이면
  // 못 보고 지나치기 쉬워서, 홈 화면 맨 위에도 같이 띄운다(실시간 푸시는 아니고, 홈 화면을
  // 열 때/새로고침할 때 보이는 방식 - 웹푸시 인프라는 다음 단계 작업).
  const [pendingFamilyRequests, setPendingFamilyRequests] = useState<FamilyLinkItem[]>([]);

  const [meds, setMeds] = useState<MedicationSchedule[]>([]);
  const [alarms, setAlarms] = useState<NotificationScheduleResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkedToday, setCheckedToday] = useState<Set<string>>(new Set());

  // 오늘의 습관 트래커 — 기본 세트(물/산책) + 등록 질환별 맞춤 습관(날짜 기준 하루 3개 로테이션).
  // 홈에는 미리보기 카드만 두고, 클릭하면 모달에서 실제로 체크한다.
  const [habitsToday, setHabitsToday] = useState<HabitsTodayResult | null>(null);
  const [showCongrats, setShowCongrats] = useState(false);
  const [showLifestyleModal, setShowLifestyleModal] = useState(false);
  // 아직 하나도 선택 안 했을 때 누르면(예전엔 /habit-selection으로 이동) 모달로 바로 고를 수 있게 한다.
  const [showHabitSelectionModal, setShowHabitSelectionModal] = useState(false);
  const [showScheduleModal, setShowScheduleModal] = useState(false);

  const [chatInput, setChatInput] = useState("");

  // 가까운 병원/약국 찾기 카드 — 위치를 허용하면 그 지역 기준으로, 아니면 서울 기준으로 검색한다.
  const nearbyLocation = useNearbyRegionLabel();

  useEffect(() => {
    if (user && !isDismissedThisSession(user.profile_id) && !hasEnteredHealthInfo(healthInfo)) {
      setShowBanner(true);
    } else {
      setShowBanner(false);
    }
  }, [user, healthInfo]);

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
    loadChecked(toDateString(new Date())).then(setCheckedToday);
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
    if (!user) {
      setHabitsToday(null);
      return;
    }
    habitApi
      .getToday()
      .then(setHabitsToday)
      .catch(() => setHabitsToday(null));
  }, [user]);

  async function loadPendingFamilyRequests() {
    if (!user) {
      setPendingFamilyRequests([]);
      return;
    }
    try {
      const result = await familyApi.list();
      setPendingFamilyRequests(result.as_member_pending);
    } catch {
      // 가족 요청 카드는 부가 정보라, 실패해도 홈 화면 전체를 막지 않고 조용히 숨긴다.
      setPendingFamilyRequests([]);
    }
  }

  useEffect(() => {
    loadPendingFamilyRequests();
  }, [user]);

  async function handleAcceptFamilyRequest(linkId: number) {
    try {
      await familyApi.accept(linkId);
      await loadPendingFamilyRequests();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "수락에 실패했습니다.");
    }
  }

  async function handleRejectFamilyRequest(linkId: number) {
    if (!window.confirm("이 연결 요청을 거절할까요?")) return;
    try {
      await familyApi.reject(linkId);
      await loadPendingFamilyRequests();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "거절에 실패했습니다.");
    }
  }

  function handleAskAi() {
    const text = chatInput.trim();
    if (!text) return;
    setChatInput("");
    navigate("/chat", { state: { autoMessage: text } });
  }

  function handleCheckHabit(habitKey: string) {
    const wasAllDone = habitsToday?.all_completed ?? false;
    habitApi
      .check(habitKey)
      .then((res) => {
        setHabitsToday(res);
        if (!wasAllDone && res.all_completed) setShowCongrats(true);
      })
      .catch(() => {
        // 습관 체크는 부가 기능이라 실패해도 조용히 무시 - 다음 클릭에서 다시 시도하면 된다.
      });
  }

  function handleDismiss() {
    if (user) dismissForSession(user.profile_id);
    setShowBanner(false);
  }

  function handleConfirm() {
    if (user) dismissForSession(user.profile_id);
    setShowBanner(false);
    navigate("/health-info/consent");
  }

  const today = new Date();
  const groups = buildGroups(meds, alarms, today);
  const totalCount = groups.reduce((n, g) => n + g.items.length, 0);
  const doneCount = groups.reduce(
    (n, g) => n + g.items.filter((i) => checkedToday.has(i.key)).length,
    0,
  );

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100vh", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: "0 0 10px" }}>
          👋 안녕하세요{user ? `, ${user.name}님` : ""}!
        </h1>

        {/* 건강정보 입력 유도 배너를 먼저 두고, 가족 연결 요청은 그 아래에 둔다. */}
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

        {pendingFamilyRequests.length > 0 && (
          <div
            style={{
              background: pinkTheme.primarySoft,
              border: `1.5px solid ${pinkTheme.primary}`,
              borderRadius: "12px",
              padding: "16px 20px",
              marginBottom: 16,
            }}
          >
            <p style={{ color: pinkTheme.primary, fontWeight: 700, margin: "0 0 10px" }}>
              🔔 받은 가족 연결 요청
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {pendingFamilyRequests.map((req) => (
                <div
                  key={req.link_id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    background: pinkTheme.cardBg,
                    borderRadius: 10,
                    padding: "10px 12px",
                    gap: 8,
                  }}
                >
                  <span style={{ fontSize: 14, color: pinkTheme.text }}>
                    {req.name}님이 나를 "{req.relation_label}"(으)로 등록하고 싶어해요
                  </span>
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                    <button
                      type="button"
                      onClick={() => handleAcceptFamilyRequest(req.link_id)}
                      style={{
                        border: "none",
                        borderRadius: 8,
                        background: pinkTheme.primary,
                        color: "#fff",
                        fontSize: 12,
                        fontWeight: 600,
                        padding: "6px 12px",
                        cursor: "pointer",
                      }}
                    >
                      수락
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRejectFamilyRequest(req.link_id)}
                      style={{
                        border: `1px solid ${pinkTheme.border}`,
                        borderRadius: 8,
                        background: pinkTheme.cardBg,
                        color: pinkTheme.textMuted,
                        fontSize: 12,
                        padding: "6px 12px",
                        cursor: "pointer",
                      }}
                    >
                      거절
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {user && (
          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
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
                boxShadow: "0 2px 6px rgba(255, 111, 145, 0.1)",
              }}
            >
              🙋 내 정보
            </button>
            <button
              type="button"
              onClick={() => setShowHabitSelectionModal(true)}
              style={{
                border: `1px solid ${pinkTheme.border}`,
                background: pinkTheme.cardBg,
                color: pinkTheme.primary,
                borderRadius: 999,
                padding: "7px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 2px 6px rgba(255, 111, 145, 0.1)",
              }}
            >
              📖 마이다이어리
            </button>
          </div>
        )}

        {user && !loading && totalCount > 0 && (
          <button
            type="button"
            onClick={() => setShowScheduleModal(true)}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              border: "none",
              padding: 0,
              cursor: "pointer",
              background: "transparent",
            }}
          >
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
          </button>
        )}

        {/* 오늘의 건강 카드를 누르면 페이지 이동 대신 복약 시간표를 모달로 띄운다. 모달
        안에서 체크한 게 서버에 반영되므로, 닫을 때 다시 불러와야 도넛 위젯 숫자가
        최신으로 갱신된다(안 하면 모달에서 체크해도 뒤 카드 숫자가 그대로 남는다). */}
        {showScheduleModal && (
          <Modal
            onClose={() => {
              setShowScheduleModal(false);
              loadChecked(toDateString(new Date())).then(setCheckedToday);
            }}
          >
            <SchedulePage embedded />
          </Modal>
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

        {/* 오늘의 습관 트래커 미리보기 — 선택한 게 있으면 모달로 체크 화면이 뜨고, 아직 하나도
            선택 안 했으면(카드 자체는 계속 보여준다 - 사라지면 습관 기능이 있다는 걸 아예
            모를 수 있다) 눌렀을 때 바로 습관 선택 페이지로 보낸다. */}
        {user && habitsToday && (
          <button
            type="button"
            onClick={() => {
              if (habitsToday.habits.length > 0) {
                setShowLifestyleModal(true);
              } else {
                setShowHabitSelectionModal(true);
              }
            }}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              background: pinkTheme.cardBg,
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 16,
              padding: 18,
              marginBottom: 16,
              boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: pinkTheme.primary }}>
                  🌿 {user.name}님을 위한 추천 라이프스타일
                </p>
                <p style={{ margin: "4px 0 0", fontSize: 12, color: pinkTheme.textMuted }}>
                  {habitsToday.habits.length > 0
                    ? `오늘의 당신, 할 수 있어요! · ${habitsToday.habits.filter((h) => h.completed).length}/${habitsToday.habits.length}개 완료`
                    : "아직 선택한 습관이 없어요 · 눌러서 오늘의 습관을 골라보세요"}
                </p>
              </div>
              <span style={{ color: pinkTheme.primary, fontSize: 18 }} aria-hidden>
                →
              </span>
            </div>
          </button>
        )}

        {/* 라이프스타일 습관 체크 모달 — 실제 아이콘 채우기/완료 체크는 여기서 한다 */}
        {user && habitsToday && showLifestyleModal && (
          <SelectedHabitsModal
            userName={user.name}
            habitsToday={habitsToday}
            onCheck={handleCheckHabit}
            onClose={() => setShowLifestyleModal(false)}
          />
        )}

        {/* 아직 습관을 하나도 안 골랐을 때 — 예전엔 /habit-selection으로 페이지 이동했는데,
            홈에서 바로 고르고 저장까지 할 수 있게 모달로 띄운다. 저장되면 이 카드의
            habitsToday도 같이 갱신되어 모달을 닫으면 바로 "n/n개 완료"로 보인다. */}
        {showHabitSelectionModal && (
          <Modal onClose={() => setShowHabitSelectionModal(false)}>
            <div
              style={{
                background: pinkTheme.cardBg,
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: 16,
                padding: 18,
                boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
              }}
            >
              <HabitSelectionContent onSaved={setHabitsToday} />
            </div>
          </Modal>
        )}

        {/* 빠른 메뉴 2x2 + AI 건강 상담 질문창 + 건강 정보 미리보기 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 10,
            marginBottom: 16,
          }}
        >
          {QUICK_LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              style={{
                background: pinkTheme.cardBg,
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: 16,
                padding: "16px 14px",
                textDecoration: "none",
                boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
              }}
            >
              <p style={{ margin: "0 0 8px", fontSize: 20 }}>{link.icon}</p>
              <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: pinkTheme.text }}>
                {link.label}
              </p>
            </Link>
          ))}
        </div>

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
          <p style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 700, color: pinkTheme.text }}>
            AI 건강 상담
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleAskAi();
              }}
              placeholder="복약 시간을 놓쳤을 때는 어떻게 하나요?"
              style={{
                flex: 1,
                padding: "11px 14px",
                borderRadius: 999,
                border: `1px solid ${pinkTheme.border}`,
                fontSize: 13,
                outline: "none",
                color: pinkTheme.text,
              }}
            />
            <button
              type="button"
              onClick={handleAskAi}
              aria-label="AI 건강 상담에 질문 보내기"
              style={{
                flexShrink: 0,
                width: 38,
                height: 38,
                borderRadius: "50%",
                border: "none",
                background: pinkTheme.primary,
                color: "#fff",
                fontSize: 15,
                cursor: "pointer",
              }}
            >
              →
            </button>
          </div>
        </div>

        {/* 가까운 병원/약국 찾기 — 위치를 허용하면 그 지역 기준으로, 아니면 서울 기준으로 검색한다
            (자세한 위치 기반 안내는 더보기 > 응급안내 참고). */}
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
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 10,
            }}
          >
            <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: pinkTheme.text }}>
              🏥 가까운 병원·약국 찾기
            </p>
            {nearbyLocation.status === "granted" ? (
              <span style={{ fontSize: 11, color: pinkTheme.textMuted }}>
                📍 {nearbyLocation.addressLabel ?? "현재 위치"}
              </span>
            ) : (
              <button
                type="button"
                onClick={nearbyLocation.requestLocation}
                disabled={nearbyLocation.status === "requesting"}
                style={{
                  border: "none",
                  background: "none",
                  color: pinkTheme.primary,
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                {nearbyLocation.status === "requesting" ? "위치 확인 중..." : "📍 내 위치로 찾기"}
              </button>
            )}
          </div>
          {(nearbyLocation.status === "denied" || nearbyLocation.status === "unsupported") && (
            <p style={{ margin: "0 0 10px", fontSize: 11, color: pinkTheme.textMuted }}>
              위치를 확인할 수 없어 서울 기준으로 안내해요.
            </p>
          )}
          <div style={{ display: "flex", gap: 10 }}>
            <button
              type="button"
              onClick={() =>
                openNearbySearch("병원", nearbyLocation.addressLabel ?? DEFAULT_REGION_LABEL)
              }
              style={{
                flex: 1,
                padding: "11px 0",
                borderRadius: 10,
                border: `1px solid ${pinkTheme.border}`,
                background: pinkTheme.primarySoft,
                color: pinkTheme.text,
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              🏥 병원 찾기
            </button>
            <button
              type="button"
              onClick={() =>
                openNearbySearch("약국", nearbyLocation.addressLabel ?? DEFAULT_REGION_LABEL)
              }
              style={{
                flex: 1,
                padding: "11px 0",
                borderRadius: 10,
                border: `1px solid ${pinkTheme.border}`,
                background: pinkTheme.primarySoft,
                color: pinkTheme.text,
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              💊 약국 찾기
            </button>
          </div>
        </div>

        {/* 오늘의 습관을 전부 목표치까지 채웠을 때만 뜨는 칭찬 화면 */}
        {showCongrats && (
          <Modal onClose={() => setShowCongrats(false)}>
            <div
              style={{
                background: pinkTheme.cardBg,
                borderRadius: 20,
                padding: "36px 24px",
                textAlign: "center",
              }}
            >
              <p style={{ fontSize: 48, margin: 0 }}>🎉</p>
              <p
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: pinkTheme.primary,
                  margin: "12px 0 4px",
                }}
              >
                오늘의 습관을 모두 해냈어요!
              </p>
              <p style={{ fontSize: 13, color: pinkTheme.textMuted, margin: "0 0 20px" }}>
                작은 실천이 쌓이면 큰 변화가 돼요. 정말 잘하고 있어요 💗
              </p>
              <button
                type="button"
                onClick={() => setShowCongrats(false)}
                style={{
                  border: "none",
                  borderRadius: 10,
                  padding: "11px 28px",
                  background: pinkTheme.primary,
                  color: "#fff",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                좋아요!
              </button>
            </div>
          </Modal>
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
