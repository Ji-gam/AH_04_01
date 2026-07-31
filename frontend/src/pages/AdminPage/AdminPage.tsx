import { Chart, registerables } from "chart.js";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  adminApi,
  type AdminActionResult,
  type AdminErrorLogResult,
  type AdminHealthNewsResult,
  type AdminNoticeResult,
  type AdminOpsStatsResult,
  type AdminStatsResult,
  type AdminUserResult,
  type CardSummaryBatchResult,
} from "../../api/adminApi";
import { noticeApi } from "../../api/noticeApi";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";

Chart.register(...registerables);

const DESKTOP_BREAKPOINT = 1024;

/** (2026-07-28) 대시보드/동의현황 전체표/버그리포트/전체 활동로그처럼 "한눈에 훑어봐야
 * 하는" 화면은 PC에서만, 사용자 검색+승격/공지 발송/뉴스 수집처럼 "짧고 단발성인"
 * 작업은 모바일에서도 가능하게 나눈다. 보안 목적이 아니라 순수 UX 편의라 창 너비만
 * 보고 가른다(실제 권한검증은 어차피 서버 get_current_admin_user가 함). */
function useIsDesktop(): boolean {
  const [isDesktop, setIsDesktop] = useState(
    typeof window !== "undefined" ? window.innerWidth >= DESKTOP_BREAKPOINT : true,
  );
  useEffect(() => {
    function handleResize() {
      setIsDesktop(window.innerWidth >= DESKTOP_BREAKPOINT);
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);
  return isDesktop;
}

const cardStyle: React.CSSProperties = {
  background: pinkTheme.cardBg,
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: 16,
  padding: "16px",
  display: "flex",
  flexDirection: "column",
  gap: 10,
};

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: 10,
  fontSize: 14,
};

const buttonStyle: React.CSSProperties = {
  padding: "8px 14px",
  border: "none",
  borderRadius: 8,
  background: pinkTheme.primary,
  color: "#fff",
  fontWeight: 600,
  fontSize: 13,
  cursor: "pointer",
};

const metricCardStyle: React.CSSProperties = {
  background: pinkTheme.pageBg,
  borderRadius: 12,
  padding: "1rem",
};

// 표(투박해도 괜찮음, PC 기준) - 동의현황/버그리포트에서 공용으로 쓴다.
const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  fontWeight: 600,
  color: pinkTheme.textMuted,
  borderBottom: `1px solid ${pinkTheme.border}`,
};
const tdStyle: React.CSSProperties = {
  padding: "6px 8px",
  borderBottom: `1px solid ${pinkTheme.border}`,
  verticalAlign: "top",
};

type Tab = "dashboard" | "users" | "consent" | "notices" | "contents" | "log" | "bugs";

/** 관리자 전용 화면(더보기 > 관리자, is_admin인 계정에게만 메뉴 노출). 실제 권한검증은
 * 서버(get_current_admin_user)가 하므로, 이 화면 자체를 프론트에서 숨기는 건 UX일 뿐 -
 * 여기서 호출하는 API들은 관리자가 아니면 어차피 403을 받는다.
 *
 * 관리자 권한은 새로운 공개 가입 경로 없이 "기존 관리자가 여기서 승격"하는 방식으로만
 * 늘어난다 - 최초 관리자 1명은 app/scripts/promote_admin.py로 서버에서 직접 지정한다.
 *
 * [2026-07-28] 예전에 더보기 메뉴에 따로 있던 "관리자 컨텐츠생성"/"관리자 공지등록"을
 * 이 화면 "공지·콘텐츠" 탭 안으로 흡수했다(더보기 메뉴에서 두 항목 제거).
 * [2026-07-30] T-LLM-6: "콘텐츠 생성"(LLM이 팁 지어내기) 자리를 "뉴스 수집"(RSS 수집)으로
 * 교체했다. 자동 수집(Celery)이 붙기 전까지 이 탭의 버튼이 유일한 수집 트리거다. "질병별 명수"는
 * 조사해보니 k-익명성(소수 인원 카테고리의 재식별 위험) 문제로 이번엔 안 넣었다 - 필요하면
 * 소수 인원 그룹을 자동으로 묶어 숨기는 로직을 먼저 만들어야 한다. */
export default function AdminPage() {
  const navigate = useNavigate();
  const { user, isLoading: authLoading } = useAuth();
  const isDesktop = useIsDesktop();
  const [tab, setTab] = useState<Tab>("dashboard");

  const [users, setUsers] = useState<AdminUserResult[]>([]);
  const [search, setSearch] = useState("");
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);

  const [noticeKind, setNoticeKind] = useState<"NOTICE" | "MARKETING">("NOTICE");
  const [noticeTitle, setNoticeTitle] = useState("");
  const [noticeBody, setNoticeBody] = useState("");
  const [noticeSending, setNoticeSending] = useState(false);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);
  const [noticeError, setNoticeError] = useState<string | null>(null);

  const [contentGenerating, setContentGenerating] = useState(false);
  const [contentMessage, setContentMessage] = useState<string | null>(null);
  const [contentError, setContentError] = useState<string | null>(null);

  const [actions, setActions] = useState<AdminActionResult[]>([]);
  const [actionsLoading, setActionsLoading] = useState(false);

  const [notices, setNotices] = useState<AdminNoticeResult[]>([]);
  const [noticesLoading, setNoticesLoading] = useState(false);
  const [expandedNoticeId, setExpandedNoticeId] = useState<number | null>(null);
  const [editingNoticeId, setEditingNoticeId] = useState<number | null>(null);
  const [editNoticeKind, setEditNoticeKind] = useState<"NOTICE" | "MARKETING">("NOTICE");
  const [editNoticeTitle, setEditNoticeTitle] = useState("");
  const [editNoticeBody, setEditNoticeBody] = useState("");

  // T-LLM-6 수집된 건강 뉴스(기존 건강 콘텐츠 목록을 대체).
  const [newsItems, setNewsItems] = useState<AdminHealthNewsResult[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [expandedNewsId, setExpandedNewsId] = useState<number | null>(null);
  const [editingNewsId, setEditingNewsId] = useState<number | null>(null);
  const [editNewsTitle, setEditNewsTitle] = useState("");

  const [errorLogs, setErrorLogs] = useState<AdminErrorLogResult[]>([]);
  const [errorLogsLoading, setErrorLogsLoading] = useState(false);

  const [stats, setStats] = useState<AdminStatsResult | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [trendDays, setTrendDays] = useState(7);
  const signupCanvasRef = useRef<HTMLCanvasElement>(null);
  const signupChartRef = useRef<Chart | null>(null);

  const [opsStats, setOpsStats] = useState<AdminOpsStatsResult | null>(null);
  const [opsStatsLoading, setOpsStatsLoading] = useState(false);
  const chatCanvasRef = useRef<HTMLCanvasElement>(null);
  const notifCanvasRef = useRef<HTMLCanvasElement>(null);
  const withdrawalCanvasRef = useRef<HTMLCanvasElement>(null);
  const chatChartRef = useRef<Chart | null>(null);
  const notifChartRef = useRef<Chart | null>(null);
  const withdrawalChartRef = useRef<Chart | null>(null);

  useEffect(() => {
    // is_admin=false인 사람이 URL로 직접 들어와도, 실제 데이터 호출은 서버가 403으로
    // 막아준다 - 여기선 그냥 헷갈리지 않게 홈으로 돌려보내는 UX 처리만 한다.
    if (!authLoading && user && !user.is_admin) {
      navigate("/", { replace: true });
    }
  }, [authLoading, user, navigate]);

  async function loadUsers(query?: string) {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const result = await adminApi.listUsers(query);
      setUsers(result);
    } catch (err) {
      setUsersError(err instanceof Error ? err.message : "사용자 목록을 불러오지 못했습니다.");
    } finally {
      setUsersLoading(false);
    }
  }

  async function loadActions() {
    setActionsLoading(true);
    try {
      const result = await adminApi.listActions();
      setActions(result);
    } catch {
      // 감사로그는 부가 정보라, 실패해도 화면 전체를 못 쓰게 막지 않는다.
    } finally {
      setActionsLoading(false);
    }
  }

  async function loadErrorLogs() {
    setErrorLogsLoading(true);
    try {
      const result = await adminApi.getErrorLogs();
      setErrorLogs(result);
    } catch {
      // 부가 정보 - 실패해도 나머지 탭은 그대로 쓸 수 있어야 한다.
    } finally {
      setErrorLogsLoading(false);
    }
  }

  async function loadStats(days: number) {
    setStatsLoading(true);
    try {
      const result = await adminApi.getStats(days);
      setStats(result);
    } catch {
      // 대시보드 통계도 부가 정보 - 실패해도 나머지 탭은 그대로 쓸 수 있어야 한다.
    } finally {
      setStatsLoading(false);
    }
  }

  async function loadOpsStats() {
    setOpsStatsLoading(true);
    try {
      const result = await adminApi.getOpsStats();
      setOpsStats(result);
    } catch {
      // 부가 정보 - 실패해도 나머지 탭은 그대로 쓸 수 있어야 한다.
    } finally {
      setOpsStatsLoading(false);
    }
  }

  async function loadNotices() {
    setNoticesLoading(true);
    try {
      setNotices(await adminApi.listNotices());
    } catch {
      // 목록도 부가 정보 - 실패해도 발송 폼은 그대로 쓸 수 있어야 한다.
    } finally {
      setNoticesLoading(false);
    }
  }

  function startEditNotice(n: AdminNoticeResult) {
    setEditingNoticeId(n.id);
    setEditNoticeKind(n.kind);
    setEditNoticeTitle(n.title);
    setEditNoticeBody(n.body);
  }

  async function handleSaveNotice(id: number) {
    try {
      await adminApi.updateNotice(id, {
        kind: editNoticeKind,
        title: editNoticeTitle,
        body: editNoticeBody,
      });
      setEditingNoticeId(null);
      await loadNotices();
      await loadActions();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "공지 수정에 실패했습니다.");
    }
  }

  async function handleDeleteNotice(id: number) {
    if (!window.confirm("이 공지를 삭제할까요?")) return;
    try {
      await adminApi.deleteNotice(id);
      await loadNotices();
      await loadActions();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "공지 삭제에 실패했습니다.");
    }
  }

  async function loadNews() {
    setNewsLoading(true);
    try {
      setNewsItems(await adminApi.listNews());
    } catch {
      // 목록도 부가 정보 - 실패해도 수집 버튼은 그대로 쓸 수 있어야 한다.
    } finally {
      setNewsLoading(false);
    }
  }

  function startEditNews(n: AdminHealthNewsResult) {
    setEditingNewsId(n.id);
    setEditNewsTitle(n.title);
  }

  async function handleSaveNews(id: number) {
    try {
      await adminApi.updateNews(id, { title: editNewsTitle });
      setEditingNewsId(null);
      await loadNews();
      await loadActions();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "기사 수정에 실패했습니다.");
    }
  }

  async function handleDeleteNews(id: number) {
    if (!window.confirm("이 기사를 내릴까요? 건강정보 화면에서 바로 사라져요.")) return;
    try {
      await adminApi.deleteNews(id);
      await loadNews();
      await loadActions();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "기사 삭제에 실패했습니다.");
    }
  }

  useEffect(() => {
    loadUsers();
    loadActions();
    if (isDesktop) {
      loadStats(trendDays);
      loadErrorLogs();
      loadOpsStats();
      loadNotices();
      loadNews();
    } else {
      // 모바일 탭바엔 "대시보드"가 없어서(기본값), 모바일로 들어오면 첫 탭(사용자 관리)으로
      // 맞춰준다. 공지/콘텐츠 목록도 모바일에서 이제 탭으로 보여주므로 같이 로드한다.
      setTab((prev) => (["users", "notices", "contents"].includes(prev) ? prev : "users"));
      loadNotices();
      loadNews();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDesktop]);

  // 대시보드 탭이 보이고 통계가 있을 때만 차트를 그린다 - 탭 전환으로 캔버스가
  // 사라졌다 다시 생기므로, 매번 이전 Chart 인스턴스를 destroy하고 새로 만든다
  // (안 그러면 "Canvas is already in use" 에러가 남).
  useEffect(() => {
    if (tab !== "dashboard" || !stats) return;

    if (signupCanvasRef.current) {
      signupChartRef.current?.destroy();
      signupChartRef.current = new Chart(signupCanvasRef.current, {
        type: "line",
        data: {
          labels: stats.signup_trend.map((p) => p.date.slice(5)),
          datasets: [
            {
              data: stats.signup_trend.map((p) => p.count),
              borderColor: "#2a78d6",
              backgroundColor: "rgba(42,120,214,0.1)",
              fill: true,
              tension: 0.3,
              pointRadius: stats.signup_trend.length > 20 ? 0 : 3,
              pointBackgroundColor: "#2a78d6",
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0 } },
            x: { grid: { display: false }, ticks: { autoSkip: true, maxTicksLimit: 10 } },
          },
        },
      });
    }

    return () => {
      signupChartRef.current?.destroy();
    };
  }, [tab, stats]);

  // "운영 현황" 탭의 3개 라인차트(챗봇 사용량/알림 발송/탈퇴 추이) - 위와 동일한 이유로
  // 탭이 보일 때만 그리고, 이전 탭 전환/재조회 시 기존 인스턴스를 destroy한다.
  useEffect(() => {
    if (tab !== "dashboard" || !opsStats) return;

    if (chatCanvasRef.current) {
      chatChartRef.current?.destroy();
      chatChartRef.current = new Chart(chatCanvasRef.current, {
        type: "line",
        data: {
          labels: opsStats.chat_message_trend.map((p) => p.date.slice(5)),
          datasets: [
            {
              data: opsStats.chat_message_trend.map((p) => p.count),
              borderColor: "#1baf7a",
              backgroundColor: "rgba(27,175,122,0.1)",
              fill: true,
              tension: 0.3,
              pointRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0 } },
            x: { grid: { display: false } },
          },
        },
      });
    }

    if (notifCanvasRef.current) {
      notifChartRef.current?.destroy();
      notifChartRef.current = new Chart(notifCanvasRef.current, {
        type: "line",
        data: {
          labels: opsStats.notification_count_trend.map((p) => p.date.slice(5)),
          datasets: [
            {
              data: opsStats.notification_count_trend.map((p) => p.count),
              borderColor: "#eda100",
              backgroundColor: "rgba(237,161,0,0.1)",
              fill: true,
              tension: 0.3,
              pointRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0 } },
            x: { grid: { display: false } },
          },
        },
      });
    }

    if (withdrawalCanvasRef.current) {
      withdrawalChartRef.current?.destroy();
      withdrawalChartRef.current = new Chart(withdrawalCanvasRef.current, {
        type: "bar",
        data: {
          labels: opsStats.withdrawal_trend.map((p) => p.date.slice(5)),
          datasets: [
            { data: opsStats.withdrawal_trend.map((p) => p.count), backgroundColor: "#e24b4a" },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0 } },
            x: { grid: { display: false }, ticks: { autoSkip: true, maxTicksLimit: 10 } },
          },
        },
      });
    }

    return () => {
      chatChartRef.current?.destroy();
      notifChartRef.current?.destroy();
      withdrawalChartRef.current?.destroy();
    };
  }, [tab, opsStats]);

  async function handleToggleAdmin(target: AdminUserResult) {
    try {
      await adminApi.setAdmin(target.id, !target.is_admin);
      await loadUsers(search || undefined);
      await loadActions();
    } catch (err) {
      setUsersError(err instanceof Error ? err.message : "권한 변경에 실패했습니다.");
    }
  }

  async function handleSendNotice() {
    if (!noticeTitle.trim() || !noticeBody.trim()) return;
    setNoticeSending(true);
    setNoticeMessage(null);
    setNoticeError(null);
    try {
      await noticeApi.create({ kind: noticeKind, title: noticeTitle, body: noticeBody });
      setNoticeMessage("공지를 발송했어요.");
      setNoticeTitle("");
      setNoticeBody("");
      await loadActions();
    } catch (err) {
      setNoticeError(err instanceof Error ? err.message : "공지 발송에 실패했습니다.");
    } finally {
      setNoticeSending(false);
    }
  }

  // T-LLM-6: [뉴스 수집] 트리거. 주기 자동 수집(Celery worker/beat)이 붙기 전까지 이 버튼이
  // 유일한 수집 경로다. 여러 번 눌러도 안전하다 - 이미 저장된 기사는 건너뛰고, 이미 요약이
  // 있으면 LLM을 다시 부르지 않는다.
  /**
   * 카드요약 배치를 남은 게 없어질 때까지 이어서 부른다.
   *
   * 왜 나눠 부르나: 요약은 기사 1건당 4~5초라 한 요청에서 다 하면 게이트웨이가 먼저 끊는다
   * (2026-07-31 실제로 504를 맞았다 - 서버는 끝까지 처리했는데 화면만 실패로 보였다).
   * 서버가 한 번에 몇 건만 처리하고 남은 수를 알려주므로, 여기서 0이 될 때까지 반복하면서
   * 진행률을 보여준다. 기사가 몇 백 건이어도 안 터진다.
   *
   * `runBatch`는 offset을 받아 배치 하나를 처리한다(요약 채우기는 offset을 쓰지 않는다).
   */
  async function runCardSummaryBatches(
    runBatch: (offset: number) => Promise<CardSummaryBatchResult>,
    describe: (done: number, total: number) => string,
  ) {
    let offset = 0;
    let generated = 0;
    let failed = 0;
    let firstError: string | null = null;
    let stalledWith = 0;

    for (;;) {
      const batch = await runBatch(offset);
      generated += batch.generated;
      failed += batch.failed;
      if (firstError === null) firstError = batch.error;
      offset = batch.next_offset;

      const done = generated + failed;
      setContentMessage(describe(done, done + batch.remaining));

      if (batch.remaining === 0) break;
      // 남았는데 한 건도 못 만들었다 - 이어 불러도 같은 기사가 계속 실패한다(무한 반복 방지).
      if (batch.generated === 0) {
        stalledWith = batch.remaining;
        break;
      }
    }
    return { generated, failed, firstError, stalledWith };
  }

  async function handleCollectNews() {
    setContentGenerating(true);
    setContentMessage(null);
    setContentError(null);
    try {
      const collected = await adminApi.collectNews();
      const collectedText =
        `기사 ${collected.created}건 새로 저장 (건강정보 아님 ${collected.excluded}건 제외, ` +
        `이미 있음 ${collected.skipped}건, 매체당 상한으로 미룸 ${collected.over_limit}건` +
        // 본문 추출 실패는 0이 정상이라 0일 때는 아예 안 보여준다 - 늘 0인 숫자가 붙어
        // 있으면 눈에 익어서, 정작 1이 됐을 때 알아채지 못한다.
        (collected.unreadable > 0 ? `, 본문 못 읽음 ${collected.unreadable}건` : "") +
        ")";
      setContentMessage(`${collectedText} · 카드요약 만드는 중...`);
      await loadNews();

      const summaries = await runCardSummaryBatches(
        () => adminApi.fillCardSummaries(),
        (done, total) => `${collectedText} · 카드요약 ${done}/${total}건 만드는 중...`,
      );
      setContentMessage(
        `${collectedText} · 카드요약 ${summaries.generated}건 생성` +
          (summaries.failed > 0 ? ` (${summaries.failed}건 실패 - 다음 수집에서 재시도돼요)` : ""),
      );

      // 실패 원인을 화면에 띄운다. 전에는 로그에만 남아서, EC2에 접속할 수 있는 사람 없이는
      // "몇 건 실패"의 이유를 알 수 없었다. 이 문구는 활동 로그에도 함께 남는다.
      // 수집 실패(매체 하나가 통째로 죽음)와 요약 실패는 원인이 전혀 다르므로 따로 보여준다.
      const reasons = [
        collected.collect_error && `수집 실패 원인: ${collected.collect_error}`,
        summaries.stalledWith > 0 &&
          `카드요약 ${summaries.stalledWith}건이 남았는데 진행이 없어 멈췄어요`,
        summaries.firstError && `카드요약 실패 원인: ${summaries.firstError}`,
      ].filter(Boolean);
      if (reasons.length > 0) {
        setContentError(reasons.join(" / "));
      }
      await loadActions();
      await loadNews();
    } catch (err) {
      setContentError(err instanceof Error ? err.message : "뉴스 수집에 실패했습니다.");
    } finally {
      setContentGenerating(false);
    }
  }

  // 카드요약 문구 기준(프롬프트·글자 수 제한)을 바꿨을 때 기존 기사에도 적용하는 버튼.
  // 수집 배치는 요약이 비어 있는 기사만 고르기 때문에 이게 없으면 옛 요약이 영원히 남는다.
  async function handleRegenerateCardSummaries() {
    setContentGenerating(true);
    setContentMessage(null);
    setContentError(null);
    try {
      const result = await runCardSummaryBatches(
        (offset) => adminApi.regenerateCardSummaries(offset),
        (done, total) => `카드요약 ${done}/${total}건 다시 만드는 중...`,
      );
      setContentMessage(
        `카드요약 ${result.generated}건 다시 만들었어요` +
          (result.failed > 0 ? ` (${result.failed}건 실패 - 기존 요약이 그대로 남아요)` : ""),
      );
      if (result.firstError) {
        setContentError(`카드요약 실패 원인: ${result.firstError}`);
      }
      await loadActions();
      await loadNews();
    } catch (err) {
      setContentError(err instanceof Error ? err.message : "카드요약 다시 만들기에 실패했습니다.");
    } finally {
      setContentGenerating(false);
    }
  }

  function handleTrendDaysChange(days: number) {
    setTrendDays(days);
    loadStats(days);
  }

  const tabButtonStyle = (active: boolean): React.CSSProperties => ({
    padding: "8px 14px",
    border: "none",
    background: "none",
    borderBottom: active ? `2px solid ${pinkTheme.text}` : "2px solid transparent",
    color: active ? pinkTheme.text : pinkTheme.textMuted,
    fontWeight: active ? 700 : 400,
    fontSize: 13,
    cursor: "pointer",
  });

  // 뉴스 수집 폼 - 모바일 "빠른 작업"에서도 쓸 수 있게 별도 컴포넌트로 안 빼고 인라인 재사용.
  const newsCollectForm = (
    <div style={cardStyle}>
      <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>건강 뉴스 수집</p>
      <p style={{ margin: 0, fontSize: 12, color: pinkTheme.textMuted }}>
        코메디닷컴 · 헬스경향 · 코리아헬스로그에서 기사를 가져와 카드요약까지 만들어요. 여러 번
        눌러도 안전해요(이미 있는 기사는 건너뛰어요). 매체당 최신 5건까지만 가져와요 — 카드요약
        비용이 기사 수만큼 들기 때문이에요. 공시·제약사 기사는 건강정보가 아니라 저장하지 않아요.
        <br />
        카드요약은 몇 건씩 나눠 만들어요(진행률이 보여요). 다 끝날 때까지 이 화면을 열어두세요.
      </p>
      {contentError && (
        <p style={{ margin: 0, color: pinkTheme.danger, fontSize: 13 }}>{contentError}</p>
      )}
      {contentMessage && (
        <p style={{ margin: 0, color: pinkTheme.primary, fontSize: 13 }}>{contentMessage}</p>
      )}
      <button
        type="button"
        onClick={handleCollectNews}
        disabled={contentGenerating}
        style={buttonStyle}
      >
        {contentGenerating ? "수집 중..." : "뉴스 수집하기"}
      </button>

      {/* 수집 배치는 요약이 비어 있는 기사만 고른다 - 프롬프트나 글자 수 제한을 손질하면
          이미 요약이 있는 기사는 옛 기준으로 남으므로 그때 이 버튼을 쓴다. */}
      <p style={{ margin: "4px 0 0", fontSize: 12, color: pinkTheme.textMuted }}>
        카드요약 문구 기준이 바뀌었을 때만 아래를 눌러주세요. 저장된 기사 전부에 LLM을 다시 부르므로
        시간과 비용이 듭니다. 실패한 기사는 기존 요약이 그대로 남아요.
      </p>
      <button
        type="button"
        onClick={handleRegenerateCardSummaries}
        disabled={contentGenerating}
        style={{ ...buttonStyle, background: pinkTheme.cardBg, color: pinkTheme.text }}
      >
        {contentGenerating ? "다시 만드는 중..." : "카드요약 다시 만들기"}
      </button>
    </div>
  );

  const noticeForm = (
    <div style={cardStyle}>
      <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>공지/마케팅 알림 발송</p>
      <div style={{ display: "flex", gap: 6 }}>
        {(["NOTICE", "MARKETING"] as const).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setNoticeKind(k)}
            style={{
              ...buttonStyle,
              flex: 1,
              background: noticeKind === k ? pinkTheme.primary : pinkTheme.cardBg,
              color: noticeKind === k ? "#fff" : pinkTheme.textMuted,
              border: `1px solid ${pinkTheme.border}`,
            }}
          >
            {k === "NOTICE" ? "공지사항" : "마케팅"}
          </button>
        ))}
      </div>
      <input
        type="text"
        placeholder="제목"
        value={noticeTitle}
        onChange={(e) => setNoticeTitle(e.target.value)}
        style={inputStyle}
      />
      <textarea
        placeholder="내용"
        value={noticeBody}
        onChange={(e) => setNoticeBody(e.target.value)}
        rows={3}
        style={{ ...inputStyle, resize: "vertical" }}
      />
      {noticeError && (
        <p style={{ margin: 0, color: pinkTheme.danger, fontSize: 13 }}>{noticeError}</p>
      )}
      {noticeMessage && (
        <p style={{ margin: 0, color: pinkTheme.primary, fontSize: 13 }}>{noticeMessage}</p>
      )}
      <button
        type="button"
        onClick={handleSendNotice}
        disabled={noticeSending || !noticeTitle.trim() || !noticeBody.trim()}
        style={buttonStyle}
      >
        {noticeSending ? "발송 중..." : "발송하기"}
      </button>
    </div>
  );

  return (
    <div style={{ minHeight: "100%", background: pinkTheme.pageBg, padding: "20px 12px" }}>
      <div
        style={{
          maxWidth: isDesktop ? 960 : "100%",
          width: "100%",
          boxSizing: "border-box",
          margin: "0 auto",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <button
          type="button"
          onClick={() => navigate("/more")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            alignSelf: "flex-start",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          ← 뒤로가기
        </button>
        <h2 style={{ margin: 0, color: pinkTheme.text }}>
          🔧 관리자{!isDesktop && " · 빠른 작업"}
        </h2>

        {isDesktop && (
          <div
            style={{
              display: "flex",
              gap: 4,
              borderBottom: `1px solid ${pinkTheme.border}`,
              flexWrap: "wrap",
            }}
          >
            {(
              [
                ["dashboard", "대시보드"],
                ["users", "사용자"],
                ["consent", "동의 현황"],
                ["notices", "공지 관리"],
                ["contents", "뉴스 관리"],
                ["bugs", "버그 리포트"],
                ["log", "활동 로그"],
              ] as [Tab, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                style={tabButtonStyle(tab === key)}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* (2026-07-28) 모바일 전용 탭바 - 대시보드/동의현황/버그리포트/활동로그처럼
          "한눈에 훑어보는" 화면은 빼고, 짧고 단발성인 작업 3개만 탭으로 나눈다.
          예전엔 이 3개를 한 화면에 전부 세로로 쌓아뒀는데, 배포 계정이 17개로
          늘면서 사용자 목록이 길어지면 아래 공지/뉴스 폼까지 스크롤이 너무
          길어지는 문제가 있었다 - 탭으로 나눠서 한 번에 하나씩만 보이게 한다. */}
        {!isDesktop && (
          <div style={{ display: "flex", gap: 4 }}>
            {(
              [
                ["users", "사용자 관리"],
                ["notices", "공지·마케팅"],
                ["contents", "뉴스 수집"],
              ] as [Tab, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                style={{
                  flex: 1,
                  padding: "8px 4px",
                  borderRadius: 10,
                  border: tab === key ? "none" : `1px solid ${pinkTheme.border}`,
                  background: tab === key ? pinkTheme.primary : pinkTheme.cardBg,
                  color: tab === key ? "#fff" : pinkTheme.textMuted,
                  fontWeight: 700,
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {/* ── 대시보드 (PC 전용) ── */}
        {isDesktop && tab === "dashboard" && (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: 12,
              }}
            >
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  전체 사용자
                </p>
                <p style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
                  {stats?.total_users ?? "-"}
                </p>
              </div>
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  관리자 수
                </p>
                <p style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
                  {stats?.total_admins ?? "-"}
                </p>
              </div>
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  건강정보 동의율
                </p>
                <p style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
                  {stats && stats.total_users > 0
                    ? `${Math.round((stats.consent_summary.health_info / stats.total_users) * 100)}%`
                    : "-"}
                </p>
              </div>
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  최근 24시간 오류
                </p>
                <p
                  style={{
                    margin: 0,
                    fontSize: 24,
                    fontWeight: 700,
                    color: stats && stats.error_count_24h > 0 ? pinkTheme.danger : pinkTheme.text,
                  }}
                >
                  {stats?.error_count_24h ?? "-"}
                </p>
              </div>
            </div>

            {statsLoading && (
              <p style={{ color: pinkTheme.textMuted, fontSize: 13 }}>불러오는 중...</p>
            )}

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)",
                gap: 12,
              }}
            >
              <div style={cardStyle}>
                <div
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
                >
                  <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>가입자 추이</p>
                  <div style={{ display: "flex", gap: 4 }}>
                    {[7, 14, 30].map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => handleTrendDaysChange(d)}
                        style={{
                          padding: "3px 9px",
                          borderRadius: 999,
                          border: `1px solid ${pinkTheme.border}`,
                          background: trendDays === d ? pinkTheme.primary : pinkTheme.cardBg,
                          color: trendDays === d ? "#fff" : pinkTheme.textMuted,
                          fontSize: 11,
                          cursor: "pointer",
                        }}
                      >
                        {d}일
                      </button>
                    ))}
                  </div>
                </div>
                <div style={{ position: "relative", width: "100%", height: 220 }}>
                  <canvas
                    ref={signupCanvasRef}
                    role="img"
                    aria-label="가입자 수 라인 차트"
                  ></canvas>
                </div>
              </div>
              <div style={cardStyle}>
                <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>
                  동의 항목별 인원
                </p>
                {/* (그래프 대신 항상 숫자가 보이는 막대 나열 - 마우스를 안 올려도 바로 읽혀야 함) */}
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {(
                    [
                      ["이용약관", stats?.consent_summary.terms_of_service, "#2a78d6"],
                      ["건강정보", stats?.consent_summary.health_info, "#1baf7a"],
                      ["AI챗봇", stats?.consent_summary.ai_chat, "#eda100"],
                      ["마케팅", stats?.consent_summary.marketing, "#e87ba4"],
                    ] as const
                  ).map(([label, count, color]) => {
                    const total = stats?.total_users ?? 0;
                    const pct = total > 0 && count != null ? Math.round((count / total) * 100) : 0;
                    return (
                      <div key={label}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: 12.5,
                            marginBottom: 4,
                          }}
                        >
                          <span style={{ color: pinkTheme.text }}>{label}</span>
                          <span style={{ color: pinkTheme.textMuted }}>
                            {count ?? "-"}명{total > 0 ? ` (${pct}%)` : ""}
                          </span>
                        </div>
                        <div
                          style={{
                            height: 8,
                            borderRadius: 999,
                            background: pinkTheme.pageBg,
                            overflow: "hidden",
                          }}
                        >
                          <div style={{ width: `${pct}%`, height: "100%", background: color }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* ── 운영 현황(2026-07-28 대시보드에 통합) ── */}
            {opsStatsLoading && (
              <p style={{ color: pinkTheme.textMuted, fontSize: 13 }}>불러오는 중...</p>
            )}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: 12,
              }}
            >
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  일간 활성 사용자(DAU)
                </p>
                <p style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>{opsStats?.dau ?? "-"}</p>
              </div>
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  주간 활성 사용자(WAU)
                </p>
                <p style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>{opsStats?.wau ?? "-"}</p>
              </div>
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  복약 순응도(근사, 7일)
                </p>
                <p style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
                  {opsStats?.adherence_rate != null
                    ? `${Math.round(opsStats.adherence_rate * 100)}%`
                    : "-"}
                </p>
              </div>
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  가족 연결 건수
                </p>
                <p style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
                  {opsStats?.family_link_count ?? "-"}
                </p>
              </div>
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  챗봇 활성 세션(7일)
                </p>
                <p style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
                  {opsStats?.active_chat_sessions_7d ?? "-"}
                </p>
              </div>
              <div style={metricCardStyle}>
                <p style={{ margin: "0 0 6px", fontSize: 13, color: pinkTheme.textMuted }}>
                  AI-worker 상태
                </p>
                <p
                  style={{
                    margin: 0,
                    fontSize: 24,
                    fontWeight: 700,
                    color:
                      opsStats?.ai_worker_status === "ok" ? pinkTheme.success : pinkTheme.danger,
                  }}
                >
                  {opsStats == null ? "-" : opsStats.ai_worker_status === "ok" ? "정상" : "다운"}
                </p>
              </div>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
                gap: 12,
              }}
            >
              <div style={cardStyle}>
                <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>
                  챗봇 메시지 수 (최근 7일)
                </p>
                <div style={{ position: "relative", width: "100%", height: 200 }}>
                  <canvas
                    ref={chatCanvasRef}
                    role="img"
                    aria-label="챗봇 메시지 수 라인 차트"
                  ></canvas>
                </div>
              </div>
              <div style={cardStyle}>
                <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>
                  알림 발송 건수 (최근 7일, 성공/실패는 미추적)
                </p>
                <div style={{ position: "relative", width: "100%", height: 200 }}>
                  <canvas
                    ref={notifCanvasRef}
                    role="img"
                    aria-label="알림 발송 건수 라인 차트"
                  ></canvas>
                </div>
              </div>
            </div>

            <div style={cardStyle}>
              <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>
                탈퇴 추이 (최근 30일, 근사치)
              </p>
              <div style={{ position: "relative", width: "100%", height: 180 }}>
                <canvas
                  ref={withdrawalCanvasRef}
                  role="img"
                  aria-label="탈퇴 관련 통계 기록 추이 막대 차트"
                ></canvas>
              </div>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
                gap: 12,
              }}
            >
              <div style={cardStyle}>
                <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>
                  자주 등록되는 약품 (3명 미만은 제외)
                </p>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={thStyle}>약품명</th>
                      <th style={thStyle}>등록 건수</th>
                    </tr>
                  </thead>
                  <tbody>
                    {opsStats?.top_drugs.map((d) => (
                      <tr key={d.name}>
                        <td style={tdStyle}>{d.name}</td>
                        <td style={tdStyle}>{d.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {opsStats && opsStats.top_drugs.length === 0 && (
                  <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>
                    조건(3명 이상 등록)을 만족하는 약품이 없어요.
                  </p>
                )}
              </div>
              <div style={cardStyle}>
                <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>
                  매체별 수집된 뉴스 수
                </p>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={thStyle}>매체</th>
                      <th style={thStyle}>건수</th>
                    </tr>
                  </thead>
                  <tbody>
                    {opsStats &&
                      Object.entries(opsStats.news_count_by_source).map(([source, count]) => (
                        <tr key={source}>
                          <td style={tdStyle}>{source}</td>
                          <td style={tdStyle}>{count}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ── 사용자 관리 (PC: 전용 탭, 모바일: 항상 표시) ── */}
        {tab === "users" && (
          <div style={cardStyle}>
            <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>사용자 관리</p>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="text"
                placeholder="이메일로 검색"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadUsers(search || undefined)}
                style={{ ...inputStyle, flex: 1 }}
              />
              <button
                type="button"
                onClick={() => loadUsers(search || undefined)}
                style={buttonStyle}
              >
                검색
              </button>
            </div>
            {usersError && (
              <p style={{ margin: 0, color: pinkTheme.danger, fontSize: 13 }}>{usersError}</p>
            )}
            {usersLoading ? (
              <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>불러오는 중...</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {users.map((u) => (
                  <div
                    key={u.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 10px",
                      background: pinkTheme.pageBg,
                      borderRadius: 8,
                      fontSize: 13,
                      gap: 8,
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ color: pinkTheme.text, wordBreak: "break-word" }}>
                        {u.email}{" "}
                        {u.is_admin && (
                          <strong style={{ color: pinkTheme.primary }}>· 관리자</strong>
                        )}
                      </div>
                      <div style={{ fontSize: 11, color: pinkTheme.textMuted, marginTop: 2 }}>
                        가입일 {new Date(u.created_at).toLocaleDateString("ko-KR")}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleToggleAdmin(u)}
                      style={{
                        ...buttonStyle,
                        flex: "none",
                        padding: "5px 10px",
                        background: u.is_admin ? pinkTheme.border : pinkTheme.primary,
                        color: u.is_admin ? pinkTheme.text : "#fff",
                      }}
                    >
                      {u.is_admin ? "권한 해제" : "관리자로 지정"}
                    </button>
                  </div>
                ))}
                {users.length === 0 && (
                  <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>
                    결과가 없어요.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── 동의 현황 (PC 전용, 투박한 표 형태) ── */}
        {isDesktop && tab === "consent" && (
          <div style={cardStyle}>
            <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>사용자별 동의 현황</p>
            {usersLoading ? (
              <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>불러오는 중...</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={thStyle}>이메일</th>
                      <th style={thStyle}>이용약관</th>
                      <th style={thStyle}>건강정보</th>
                      <th style={thStyle}>AI챗봇</th>
                      <th style={thStyle}>마케팅</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => {
                      const marketingRevoked = !!u.marketing_consent_revoked_at;
                      return (
                        <tr key={u.id}>
                          <td style={tdStyle}>{u.email}</td>
                          {(
                            [
                              u.terms_of_service_consented_at,
                              u.health_info_consented_at,
                              u.ai_chat_consented_at,
                            ] as const
                          ).map((consentedAt, i) => (
                            <td key={i} style={tdStyle}>
                              {consentedAt ? (
                                <span style={{ color: pinkTheme.success }}>
                                  ✓ {new Date(consentedAt).toLocaleDateString("ko-KR")}
                                </span>
                              ) : (
                                <span style={{ color: pinkTheme.textMuted }}>-</span>
                              )}
                            </td>
                          ))}
                          {/* (2026-07-30) 마케팅만 철회 가능해서 다른 3개 컬럼과 다르게,
                              동의일 + 철회일을 둘 다 보여준다 - "동의했다가 취소한 사람"과
                              "애초에 동의 안 한 사람"을 구분해서 볼 수 있게. */}
                          <td style={tdStyle}>
                            {marketingRevoked ? (
                              <span style={{ color: pinkTheme.danger }}>
                                ✕ 취소됨 (
                                {new Date(u.marketing_consent_revoked_at!).toLocaleDateString(
                                  "ko-KR",
                                )}
                                )
                              </span>
                            ) : u.marketing_consented_at ? (
                              <span style={{ color: pinkTheme.success }}>
                                ✓ {new Date(u.marketing_consented_at).toLocaleDateString("ko-KR")}
                              </span>
                            ) : (
                              <span style={{ color: pinkTheme.textMuted }}>-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {users.length === 0 && (
                  <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>
                    결과가 없어요.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── 공지 발송 + 뉴스 수집 (PC: 전용 탭, 모바일: 항상 표시) ── */}
        {/* ── 공지 관리 (PC: 전용 탭, 모바일: 발송 폼만) ── */}
        {tab === "notices" && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: isDesktop ? "minmax(0, 1fr) minmax(0, 1fr)" : "minmax(0, 1fr)",
              gap: 16,
            }}
          >
            {noticeForm}
            <div style={cardStyle}>
              <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>등록된 공지 목록</p>
              {noticesLoading ? (
                <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>
                  불러오는 중...
                </p>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    maxHeight: 420,
                    overflowY: "auto",
                  }}
                >
                  {notices
                    .slice()
                    .reverse()
                    .map((n) =>
                      editingNoticeId === n.id ? (
                        <div
                          key={n.id}
                          style={{
                            border: `1px solid ${pinkTheme.primary}`,
                            borderRadius: 10,
                            padding: 10,
                            display: "flex",
                            flexDirection: "column",
                            gap: 6,
                          }}
                        >
                          <div style={{ display: "flex", gap: 6 }}>
                            {(["NOTICE", "MARKETING"] as const).map((k) => (
                              <button
                                key={k}
                                type="button"
                                onClick={() => setEditNoticeKind(k)}
                                style={{
                                  ...buttonStyle,
                                  flex: 1,
                                  padding: "4px 8px",
                                  fontSize: 11,
                                  background:
                                    editNoticeKind === k ? pinkTheme.primary : pinkTheme.cardBg,
                                  color: editNoticeKind === k ? "#fff" : pinkTheme.textMuted,
                                  border: `1px solid ${pinkTheme.border}`,
                                }}
                              >
                                {k === "NOTICE" ? "공지사항" : "마케팅"}
                              </button>
                            ))}
                          </div>
                          <input
                            value={editNoticeTitle}
                            onChange={(e) => setEditNoticeTitle(e.target.value)}
                            style={inputStyle}
                          />
                          <textarea
                            value={editNoticeBody}
                            onChange={(e) => setEditNoticeBody(e.target.value)}
                            rows={3}
                            style={{ ...inputStyle, resize: "vertical" }}
                          />
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              type="button"
                              onClick={() => handleSaveNotice(n.id)}
                              style={{ ...buttonStyle, flex: 1 }}
                            >
                              저장
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingNoticeId(null)}
                              style={{
                                ...buttonStyle,
                                flex: 1,
                                background: pinkTheme.border,
                                color: pinkTheme.text,
                              }}
                            >
                              취소
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div
                          key={n.id}
                          style={{
                            border: `1px solid ${pinkTheme.border}`,
                            borderRadius: 10,
                            padding: 10,
                            display: "flex",
                            flexDirection: "column",
                            gap: 6,
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "flex-start",
                              gap: 8,
                            }}
                          >
                            <button
                              type="button"
                              onClick={() =>
                                setExpandedNoticeId(expandedNoticeId === n.id ? null : n.id)
                              }
                              style={{
                                flex: 1,
                                minWidth: 0,
                                textAlign: "left",
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                padding: 0,
                              }}
                            >
                              <span
                                style={{
                                  fontSize: 10.5,
                                  fontWeight: 700,
                                  color: pinkTheme.textMuted,
                                  border: `1px solid ${pinkTheme.border}`,
                                  borderRadius: 999,
                                  padding: "1px 7px",
                                  marginRight: 6,
                                }}
                              >
                                {n.kind === "NOTICE" ? "공지" : "마케팅"}
                              </span>
                              <span
                                style={{ fontSize: 13, fontWeight: 600, color: pinkTheme.text }}
                              >
                                {n.title}
                              </span>
                              <span
                                style={{
                                  fontSize: 11,
                                  color: pinkTheme.textMuted,
                                  marginLeft: 6,
                                }}
                              >
                                {expandedNoticeId === n.id ? "▲" : "▼"}
                              </span>
                            </button>
                            <div style={{ display: "flex", gap: 4, flex: "none" }}>
                              <button
                                type="button"
                                onClick={() => startEditNotice(n)}
                                style={{ ...buttonStyle, padding: "4px 8px", fontSize: 11 }}
                              >
                                수정
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteNotice(n.id)}
                                style={{
                                  ...buttonStyle,
                                  padding: "4px 8px",
                                  fontSize: 11,
                                  background: pinkTheme.danger,
                                }}
                              >
                                삭제
                              </button>
                            </div>
                          </div>
                          {expandedNoticeId === n.id && (
                            <p
                              style={{
                                margin: 0,
                                fontSize: 12.5,
                                color: pinkTheme.text,
                                whiteSpace: "pre-wrap",
                              }}
                            >
                              {n.body}
                            </p>
                          )}
                        </div>
                      ),
                    )}
                  {notices.length === 0 && (
                    <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>
                      등록된 공지가 없어요.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── 콘텐츠 관리 (PC: 전용 탭, 모바일: 생성 폼만) ── */}
        {tab === "contents" && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: isDesktop ? "minmax(0, 1fr) minmax(0, 1fr)" : "minmax(0, 1fr)",
              gap: 16,
            }}
          >
            {newsCollectForm}
            <div style={cardStyle}>
              <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>수집된 건강 뉴스</p>
              {newsLoading ? (
                <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>
                  불러오는 중...
                </p>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    maxHeight: 420,
                    overflowY: "auto",
                  }}
                >
                  {newsItems.map((n) =>
                    editingNewsId === n.id ? (
                      <div
                        key={n.id}
                        style={{
                          border: `1px solid ${pinkTheme.primary}`,
                          borderRadius: 10,
                          padding: 10,
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                        }}
                      >
                        <input
                          value={editNewsTitle}
                          onChange={(e) => setEditNewsTitle(e.target.value)}
                          placeholder="제목"
                          style={inputStyle}
                        />
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            type="button"
                            onClick={() => handleSaveNews(n.id)}
                            style={{ ...buttonStyle, flex: 1 }}
                          >
                            저장
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingNewsId(null)}
                            style={{
                              ...buttonStyle,
                              flex: 1,
                              background: pinkTheme.border,
                              color: pinkTheme.text,
                            }}
                          >
                            취소
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div
                        key={n.id}
                        style={{
                          border: `1px solid ${pinkTheme.border}`,
                          borderRadius: 10,
                          padding: 10,
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "flex-start",
                            gap: 8,
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setExpandedNewsId(expandedNewsId === n.id ? null : n.id)}
                            style={{
                              flex: 1,
                              minWidth: 0,
                              textAlign: "left",
                              background: "none",
                              border: "none",
                              cursor: "pointer",
                              padding: 0,
                            }}
                          >
                            <span
                              style={{
                                display: "inline-block",
                                fontSize: 10.5,
                                fontWeight: 700,
                                color: n.has_card_summary ? pinkTheme.primary : pinkTheme.textMuted,
                                border: `1px solid ${pinkTheme.border}`,
                                borderRadius: 999,
                                padding: "1px 7px",
                                marginRight: 6,
                                verticalAlign: "bottom",
                              }}
                            >
                              {n.source_name} · {n.has_card_summary ? "요약O" : "요약X"}
                            </span>
                            <span
                              style={{
                                fontSize: 13,
                                fontWeight: 600,
                                color: pinkTheme.text,
                                wordBreak: "break-word",
                              }}
                            >
                              {n.title}
                            </span>
                            <span
                              style={{ fontSize: 11, color: pinkTheme.textMuted, marginLeft: 6 }}
                            >
                              {expandedNewsId === n.id ? "▲" : "▼"}
                            </span>
                          </button>
                          <div style={{ display: "flex", gap: 4, flex: "none" }}>
                            <button
                              type="button"
                              onClick={() => startEditNews(n)}
                              style={{ ...buttonStyle, padding: "4px 8px", fontSize: 11 }}
                            >
                              수정
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteNews(n.id)}
                              style={{
                                ...buttonStyle,
                                padding: "4px 8px",
                                fontSize: 11,
                                background: pinkTheme.danger,
                              }}
                            >
                              삭제
                            </button>
                          </div>
                        </div>
                        {expandedNewsId === n.id && (
                          <div style={{ fontSize: 12.5, color: pinkTheme.text }}>
                            <p style={{ margin: "0 0 6px", color: pinkTheme.textMuted }}>
                              발행 {new Date(n.published_at).toLocaleString("ko-KR")}
                            </p>
                            {/* RSS 카테고리를 그대로 보여준다 - 수집 필터 기준을 조정할 근거다. */}
                            {n.source_categories && n.source_categories.length > 0 && (
                              <p style={{ margin: "0 0 6px", color: pinkTheme.textMuted }}>
                                카테고리: {n.source_categories.join(", ")}
                              </p>
                            )}
                            <a
                              href={n.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: pinkTheme.primary, fontSize: 12 }}
                            >
                              원문 보기
                            </a>
                          </div>
                        )}
                      </div>
                    ),
                  )}
                  {newsItems.length === 0 && (
                    <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>
                      아직 수집된 뉴스가 없어요. [뉴스 수집하기]를 눌러주세요.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── 버그 리포트 (PC 전용) ── */}
        {isDesktop && tab === "bugs" && (
          <div style={cardStyle}>
            <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>서버 오류 로그</p>
            <p style={{ margin: 0, fontSize: 12, color: pinkTheme.textMuted }}>
              AI챗봇 오류는 별도 파일 로그로 관리 중이라 여기엔 안 나와요. 여기는 그 외 API에서
              발생한 미처리 예외 목록이에요(트레이스백/요청 바디는 저장 안 함).
            </p>
            {errorLogsLoading ? (
              <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>불러오는 중...</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
                  <thead>
                    <tr>
                      <th style={thStyle}>시각</th>
                      <th style={thStyle}>요청</th>
                      <th style={thStyle}>예외 타입</th>
                      <th style={thStyle}>메시지</th>
                    </tr>
                  </thead>
                  <tbody>
                    {errorLogs.map((e) => (
                      <tr key={e.id}>
                        <td style={tdStyle}>{new Date(e.created_at).toLocaleString("ko-KR")}</td>
                        <td style={tdStyle}>
                          {e.method} {e.path}
                        </td>
                        <td style={{ ...tdStyle, color: pinkTheme.danger, fontWeight: 600 }}>
                          {e.exception_type}
                        </td>
                        <td style={tdStyle}>{e.message ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {errorLogs.length === 0 && (
                  <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>
                    기록된 오류가 없어요.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── 활동 로그 (PC 전용) ── */}
        {isDesktop && tab === "log" && (
          <div style={cardStyle}>
            <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text }}>
              최근 관리자 활동 로그
            </p>
            {actionsLoading ? (
              <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>불러오는 중...</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {actions.map((a) => (
                  <div key={a.id} style={{ fontSize: 12, color: pinkTheme.textMuted }}>
                    [{new Date(a.created_at).toLocaleString("ko-KR")}]{" "}
                    {a.detail || `${a.action} (${a.target})`}
                  </div>
                ))}
                {actions.length === 0 && (
                  <p style={{ margin: 0, color: pinkTheme.textMuted, fontSize: 13 }}>
                    아직 기록이 없어요.
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {!isDesktop && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 4px",
              color: pinkTheme.textMuted,
              fontSize: 12.5,
            }}
          >
            <span aria-hidden>🖥️</span>
            대시보드·동의현황·버그리포트·전체 활동로그는 PC에서 확인하세요.
          </div>
        )}
      </div>
    </div>
  );
}
