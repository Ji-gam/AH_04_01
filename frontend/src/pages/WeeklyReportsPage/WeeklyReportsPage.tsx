import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { WeeklyReportItemResult } from "../../api/types";
import { weeklyReportApi } from "../../api/weeklyReportApi";
import { pinkTheme } from "../../theme/pinkTheme";

function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

/** 더보기 > 주간 리포트 - 매주 일요일 오전 9시에 스케줄러(push_scheduler.py)가 습관/식단/
 * 운동/복약 데이터를 AI로 요약해 저장해둔 리포트를 목록+아코디언으로 보여준다.
 * `NoticePage.tsx`와 같은 패턴(조회 전용, 여기서 새로 만드는 기능은 없음). */
export default function WeeklyReportsPage() {
  const navigate = useNavigate();

  const [reports, setReports] = useState<WeeklyReportItemResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

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

        <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: "0 0 6px" }}>📊 주간 리포트</h1>
        <p style={{ margin: "0 0 20px", fontSize: 13, color: pinkTheme.textMuted, lineHeight: 1.5 }}>
          매주 일요일 오전 9시에 습관·식단·운동·복약 기록을 바탕으로 AI가 작성해드려요.
        </p>

        {loading && <p style={{ color: pinkTheme.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: pinkTheme.danger, fontSize: 14 }}>{error}</p>}

        {!loading && !error && reports.length === 0 && (
          <p style={{ color: pinkTheme.textMuted, fontSize: 14, textAlign: "center", marginTop: 20 }}>
            아직 생성된 주간 리포트가 없어요. 이번 주 일요일에 첫 리포트가 도착해요.
          </p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {reports.map((report) => {
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
                  <span style={{ fontSize: 14.5, fontWeight: 700, color: pinkTheme.text }}>
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
                      fontSize: 13.5,
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
          })}
        </div>
      </div>
    </div>
  );
}
