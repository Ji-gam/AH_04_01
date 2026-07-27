import { BarChart3 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { WeeklyReportItemResult } from "../../api/types";
import { weeklyReportApi } from "../../api/weeklyReportApi";
import PageTitle from "../../components/common/PageTitle";
import { pinkTheme } from "../../theme/pinkTheme";

const PAGE_SIZE = 10;

function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function yearOf(iso: string): number {
  return new Date(`${iso}T00:00:00`).getFullYear();
}

/** 더보기 > 주간 리포트 - 매주 일요일 오전 9시에 스케줄러(push_scheduler.py)가 습관/식단/
 * 운동/복약 데이터를 AI로 요약해 저장해둔 리포트를 목록+아코디언으로 보여준다.
 * `NoticePage.tsx`와 같은 패턴(조회 전용, 여기서 새로 만드는 기능은 없음).
 *
 * 리포트가 주 1건씩만 쌓여(1년에 최대 52건) 서버 페이지네이션 없이 GET /weekly-reports로
 * 전체를 한 번에 받아, 최근 1년치는 10개씩 "더보기"로, 1년 넘은 건 연도별 보관함(클릭해서
 * 펼침)으로 전부 프론트에서 나눈다(2026-07-25). 리포트가 훨씬 자주 쌓이는 구조로 바뀌면
 * 이 방식은 안 맞으니 그때는 서버 페이지네이션으로 바꿔야 한다. */
export default function WeeklyReportsPage() {
  const navigate = useNavigate();

  const [reports, setReports] = useState<WeeklyReportItemResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [expandedYears, setExpandedYears] = useState<Set<number>>(new Set());

  useEffect(() => {
    weeklyReportApi
      .list()
      .then((result) => {
        setReports(result.reports);
        setOpenId(result.reports[0]?.id ?? null);
      })
      .catch(() => setError("주간 리포트를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  const { recent, archivedByYear, years } = useMemo(() => {
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    const cutoff = oneYearAgo.toISOString().slice(0, 10);

    const recentList = reports.filter((r) => r.week_start_date >= cutoff);
    const archivedList = reports.filter((r) => r.week_start_date < cutoff);

    const byYear = new Map<number, WeeklyReportItemResult[]>();
    for (const report of archivedList) {
      const year = yearOf(report.week_start_date);
      const bucket = byYear.get(year) ?? [];
      bucket.push(report);
      byYear.set(year, bucket);
    }
    const sortedYears = Array.from(byYear.keys()).sort((a, b) => b - a);
    return { recent: recentList, archivedByYear: byYear, years: sortedYears };
  }, [reports]);

  function toggleYear(year: number) {
    setExpandedYears((prev) => {
      const next = new Set(prev);
      if (next.has(year)) {
        next.delete(year);
      } else {
        next.add(year);
      }
      return next;
    });
  }

  function renderCard(report: WeeklyReportItemResult) {
    const isOpen = openId === report.id;
    return (
      <div
        key={report.id}
        style={{
          background: pinkTheme.cardBg,
          border: `1px solid ${pinkTheme.border}`,
          borderRadius: 16,
          boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
          overflow: "hidden",
        }}
      >
        <button
          type="button"
          onClick={() => setOpenId(isOpen ? null : report.id)}
          style={{
            width: "100%",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 10,
            padding: "16px",
            border: "none",
            background: "none",
            textAlign: "left",
            cursor: "pointer",
          }}
        >
          <span style={{ fontSize: 14, fontWeight: 700, color: pinkTheme.text }}>
            {formatDate(report.week_start_date)} ~ {formatDate(report.week_end_date)}
          </span>
          <span
            aria-hidden
            style={{
              color: pinkTheme.textMuted,
              fontSize: 13,
              transform: isOpen ? "rotate(90deg)" : "none",
              transition: "transform 0.15s",
            }}
          >
            ›
          </span>
        </button>

        {isOpen && (
          <p
            style={{
              margin: 0,
              padding: "0 16px 16px",
              fontSize: 14,
              color: pinkTheme.text,
              lineHeight: 1.7,
              whiteSpace: "pre-line",
            }}
          >
            {report.content}
          </p>
        )}
      </div>
    );
  }

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate("/more")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            marginBottom: 10,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          ← 뒤로가기
        </button>

        <PageTitle icon={BarChart3} style={{ marginBottom: 6 }}>
          주간 리포트
        </PageTitle>
        <p
          style={{ margin: "0 0 20px", fontSize: 13, color: pinkTheme.textMuted, lineHeight: 1.5 }}
        >
          매주 일요일 오전 9시에 습관·식단·운동·복약 기록을 바탕으로 AI가 작성해드려요.
        </p>

        {loading && <p style={{ color: pinkTheme.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: pinkTheme.danger, fontSize: 14 }}>{error}</p>}

        {!loading && !error && reports.length === 0 && (
          <p
            style={{ color: pinkTheme.textMuted, fontSize: 14, textAlign: "center", marginTop: 20 }}
          >
            아직 생성된 주간 리포트가 없어요. 이번 주 일요일에 첫 리포트가 도착해요.
          </p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {recent.slice(0, visibleCount).map(renderCard)}
        </div>

        {visibleCount < recent.length && (
          <button
            type="button"
            onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
            style={{
              width: "100%",
              marginTop: 10,
              padding: "12px 0",
              borderRadius: 10,
              border: `1px solid ${pinkTheme.border}`,
              background: pinkTheme.cardBg,
              color: pinkTheme.text,
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            더보기 ({recent.length - visibleCount}개 더 있음)
          </button>
        )}

        {years.length > 0 && (
          <div style={{ marginTop: 28 }}>
            <p
              style={{
                margin: "0 0 10px",
                fontSize: 13,
                fontWeight: 700,
                color: pinkTheme.textMuted,
              }}
            >
              지난 리포트 보관함
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {years.map((year) => {
                const isExpanded = expandedYears.has(year);
                const yearReports = archivedByYear.get(year) ?? [];
                return (
                  <div key={year}>
                    <button
                      type="button"
                      onClick={() => toggleYear(year)}
                      style={{
                        width: "100%",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "14px 16px",
                        borderRadius: 16,
                        border: `1px solid ${pinkTheme.border}`,
                        background: pinkTheme.primarySoft,
                        color: pinkTheme.text,
                        fontSize: 14,
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      <span>
                        {year}년 ({yearReports.length}건)
                      </span>
                      <span
                        aria-hidden
                        style={{
                          transform: isExpanded ? "rotate(90deg)" : "none",
                          transition: "transform 0.15s",
                        }}
                      >
                        ›
                      </span>
                    </button>
                    {isExpanded && (
                      <div
                        style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 10 }}
                      >
                        {yearReports.map(renderCard)}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
