import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { diaryApi } from "../../api/diaryApi";
import type { DiaryEntryItemResult } from "../../api/types";
import { pinkTheme } from "../../theme/pinkTheme";

const PAGE_SIZE = 10;
const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return `${d.getMonth() + 1}/${d.getDate()} (${WEEKDAY_LABELS[d.getDay()]})`;
}

function yearOf(iso: string): number {
  return new Date(`${iso}T00:00:00`).getFullYear();
}

/** 마이다이어리 > "오늘의 한 줄" 모달 하단 "지난 기록 모아보기"에서 들어오는 보관함 화면.
 * `WeeklyReportsPage.tsx`와 같은 방식(최근 1년치는 10개씩 더보기, 1년 지난 건 연도별
 * 보관함)으로 프론트에서만 나눈다 - 다만 이건 매일 쌓일 수 있어(최대 365개/년) 최근 1년치가
 * 주간 리포트보다 "더보기"를 훨씬 많이 눌러야 할 수 있다는 점은 감안할 것. */
export default function DiaryEntriesPage() {
  const navigate = useNavigate();

  const [entries, setEntries] = useState<DiaryEntryItemResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [expandedYears, setExpandedYears] = useState<Set<number>>(new Set());
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    diaryApi
      .list()
      .then((result) => {
        setEntries(result.entries);
        setOpenId(result.entries[0]?.id ?? null);
      })
      .catch(() => setError("기록을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  const { recent, archivedByYear, years } = useMemo(() => {
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    const cutoff = oneYearAgo.toISOString().slice(0, 10);

    const recentList = entries.filter((e) => e.entry_date >= cutoff);
    const archivedList = entries.filter((e) => e.entry_date < cutoff);

    const byYear = new Map<number, DiaryEntryItemResult[]>();
    for (const entry of archivedList) {
      const year = yearOf(entry.entry_date);
      const bucket = byYear.get(year) ?? [];
      bucket.push(entry);
      byYear.set(year, bucket);
    }
    const sortedYears = Array.from(byYear.keys()).sort((a, b) => b - a);
    return { recent: recentList, archivedByYear: byYear, years: sortedYears };
  }, [entries]);

  function handleDelete(entry: DiaryEntryItemResult) {
    if (!window.confirm(`${formatDate(entry.entry_date)} 기록을 삭제할까요?`)) return;
    setDeletingId(entry.id);
    diaryApi
      .deleteEntry(entry.id)
      .then((result) => {
        setEntries(result.entries);
        setOpenId((prev) => (prev === entry.id ? null : prev));
      })
      .catch(() => setError("기록을 삭제하지 못했습니다."))
      .finally(() => setDeletingId(null));
  }

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

  function renderCard(entry: DiaryEntryItemResult) {
    const isOpen = openId === entry.id;
    return (
      <div
        key={entry.id}
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
          onClick={() => setOpenId(isOpen ? null : entry.id)}
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
            {formatDate(entry.entry_date)}
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
          <div style={{ padding: "0 16px 16px" }}>
            <p
              style={{
                margin: "0 0 10px",
                fontSize: 13.5,
                color: pinkTheme.text,
                lineHeight: 1.7,
                whiteSpace: "pre-line",
              }}
            >
              {entry.content}
            </p>
            {entry.image_base64 && (
              <img
                src={entry.image_base64}
                alt={`${entry.entry_date} 기록에 첨부된 사진`}
                style={{ width: "100%", borderRadius: 12, display: "block", marginBottom: 10 }}
              />
            )}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                aria-label={`${formatDate(entry.entry_date)} 기록 삭제`}
                onClick={() => handleDelete(entry)}
                disabled={deletingId === entry.id}
                style={{
                  border: "none",
                  background: "none",
                  color: pinkTheme.textMuted,
                  cursor: deletingId === entry.id ? "not-allowed" : "pointer",
                  fontSize: 13,
                  padding: "4px 0",
                }}
              >
                {deletingId === entry.id ? "삭제 중..." : "🗑️ 삭제"}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate(-1)}
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

        <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: "0 0 20px" }}>
          📝 오늘의 한 줄 모아보기
        </h1>

        {loading && <p style={{ color: pinkTheme.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: pinkTheme.danger, fontSize: 14 }}>{error}</p>}

        {!loading && !error && entries.length === 0 && (
          <p
            style={{ color: pinkTheme.textMuted, fontSize: 14, textAlign: "center", marginTop: 20 }}
          >
            아직 남긴 기록이 없어요. 오늘 하루를 한 줄로 남겨보세요.
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
              borderRadius: 12,
              border: `1px solid ${pinkTheme.border}`,
              background: pinkTheme.cardBg,
              color: pinkTheme.text,
              fontSize: 13,
              fontWeight: 600,
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
              지난 기록 보관함
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {years.map((year) => {
                const isExpanded = expandedYears.has(year);
                const yearEntries = archivedByYear.get(year) ?? [];
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
                        {year}년 ({yearEntries.length}건)
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
                        {yearEntries.map(renderCard)}
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
