import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { apiFetch } from "../../api/client";
import { notificationApi } from "../../api/notificationApi";
import type { NotificationScheduleResult } from "../../api/types";
import type { MedicationSchedule } from "../../hooks/useMedication";
import { pinkTheme } from "../../theme/pinkTheme";
import { toDateString } from "../AlarmPage/dateUtils";

import { buildGroups, loadChecked, saveChecked, type TimeGroup } from "./scheduleData";

/** 공용 pinkTheme 별칭 — 팁 박스(노란 안내)만 이 화면 전용 색으로 유지한다. */
const c = {
  pageBg: pinkTheme.pageBg,
  cardBg: pinkTheme.cardBg,
  cardBorder: pinkTheme.border,
  text: pinkTheme.text,
  textMuted: pinkTheme.textMuted,
  pink: pinkTheme.primary,
  pinkSoft: pinkTheme.primarySoft,
  tipBg: "#FFFBEA",
  tipText: "#8A7B4F",
  line: pinkTheme.border,
};

interface DurSearchResultItem {
  item_name: string;
  entp_name: string;
  efficacy: string;
  precautions: string;
}

const DUR_SOURCE_LABEL = "출처: 식약처 의약품안전나라(DUR·의약품 개요정보)";

/** 약 이름별 DUR 조회 결과 캐시 상태 — 아직 조회 전이면 키가 없고, 조회 중/완료/실패를 구분한다. */
type DurLookup =
  | { status: "loading" }
  | { status: "error" }
  | { status: "done"; results: DurSearchResultItem[]; notFoundReason: string | null };

function getCurrentHHMM(): string {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
}

interface Props {
  /** 모달 등에 임베드할 때 URL 쿼리 대신 직접 넘기는 날짜 ("YYYY-MM-DD") */
  dateStr?: string;
  /** true면 전체 페이지 배경/최소높이 없이 카드처럼 렌더링 (복약알림 달력 모달용) */
  embedded?: boolean;
}

export default function SchedulePage({ dateStr: dateStrProp, embedded = false }: Props = {}) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const todayStr = toDateString(new Date());
  const dateStr = dateStrProp ?? searchParams.get("date") ?? todayStr;
  const date = new Date(`${dateStr}T00:00:00`);
  const isToday = dateStr === todayStr;

  const [meds, setMeds] = useState<MedicationSchedule[]>([]);
  const [alarms, setAlarms] = useState<NotificationScheduleResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(() => loadChecked(dateStr));
  // 약 이름별 DUR 조회 결과 캐시 — 펼침 버튼을 누른 약만 조회하고, 같은 이름은 재조회하지 않는다.
  const [durByName, setDurByName] = useState<Map<string, DurLookup>>(new Map());
  const [expandedNames, setExpandedNames] = useState<Set<string>>(new Set());

  useEffect(() => {
    Promise.all([apiFetch<MedicationSchedule[]>("/medications"), notificationApi.list()])
      .then(([m, a]) => {
        setMeds(m);
        setAlarms(a);
      })
      .catch(() => setError("복약 스케줄을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setChecked(loadChecked(dateStr));
  }, [dateStr]);

  const groups = useMemo(
    () => buildGroups(meds, alarms, new Date(`${dateStr}T00:00:00`)),
    [meds, alarms, dateStr],
  );

  const totalCount = groups.reduce((n, g) => n + g.items.length, 0);
  const remaining = groups.reduce(
    (n, g) => n + g.items.filter((i) => !checked.has(i.key)).length,
    0,
  );

  // 다음 복용: 오늘 화면에서, 아직 안 지난 시간대 중 가장 이른 그룹
  const nowHHMM = getCurrentHHMM();
  const nextTime = isToday ? groups.find((g) => g.time >= nowHHMM)?.time : undefined;

  const toggle = (key: string) => {
    const next = new Set(checked);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setChecked(next);
    saveChecked(dateStr, next);
  };

  const checkAll = (group: TimeGroup) => {
    const next = new Set(checked);
    const allChecked = group.items.every((i) => next.has(i.key));
    for (const i of group.items) {
      if (allChecked) next.delete(i.key);
      else next.add(i.key);
    }
    setChecked(next);
    saveChecked(dateStr, next);
  };

  const toggleDurExpand = (name: string) => {
    setExpandedNames((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });

    if (durByName.has(name)) return; // 이미 조회했거나 조회 중 — 재조회하지 않음

    setDurByName((prev) => new Map(prev).set(name, { status: "loading" }));
    apiFetch<{
      elapsed_ms: number;
      results: DurSearchResultItem[];
      not_found_reason: string | null;
    }>(`/medications/search-dur?query=${encodeURIComponent(name)}`)
      .then((res) => {
        setDurByName((prev) =>
          new Map(prev).set(name, {
            status: "done",
            results: res.results,
            notFoundReason: res.not_found_reason,
          }),
        );
      })
      .catch(() => {
        setDurByName((prev) => new Map(prev).set(name, { status: "error" }));
      });
  };

  const title = isToday
    ? "오늘의 복약 시간표"
    : `${date.getMonth() + 1}월 ${date.getDate()}일 복약 시간표`;

  return (
    <div
      style={
        embedded
          ? { background: c.pageBg, borderRadius: 16, padding: "20px 16px" }
          : { background: c.pageBg, minHeight: "100vh", padding: "24px 16px" }
      }
    >
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        {!embedded && (
          <button
            type="button"
            onClick={() => navigate("/more")}
            style={{
              background: "none",
              border: "none",
              color: c.textMuted,
              padding: 0,
              marginBottom: 12,
              cursor: "pointer",
            }}
          >
            ← 뒤로가기
          </button>
        )}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 18,
          }}
        >
          <h1 style={{ fontSize: 19, fontWeight: 700, color: c.text, margin: 0 }}>⏰ {title}</h1>
          {totalCount > 0 && (
            <span
              style={{
                background: c.pinkSoft,
                color: c.pink,
                borderRadius: 999,
                padding: "5px 12px",
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {remaining > 0 ? `${remaining}개 남음` : "오늘 복용 완료!"}
            </span>
          )}
        </div>

        {loading && <p style={{ color: c.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: "#D9534F", fontSize: 14 }}>{error}</p>}

        {!loading && !error && groups.length === 0 && (
          <div
            style={{
              background: c.cardBg,
              border: `1px dashed ${c.cardBorder}`,
              borderRadius: 16,
              padding: 32,
              textAlign: "center",
              color: c.textMuted,
            }}
          >
            <p style={{ fontSize: 30, margin: 0 }}>🌿</p>
            <p style={{ fontSize: 14, margin: "8px 0 0" }}>이 날짜에 복용할 약이 없어요.</p>
            <p style={{ fontSize: 13, margin: "4px 0 0" }}>
              <Link to="/medication" style={{ color: c.pink }}>
                약 등록하러 가기 →
              </Link>
            </p>
          </div>
        )}

        {/* 타임라인 */}
        <div style={{ position: "relative", paddingLeft: 30 }}>
          {/* 세로 라인 */}
          {groups.length > 0 && (
            <div
              style={{
                position: "absolute",
                left: 9,
                top: 8,
                bottom: 8,
                width: 2,
                background: c.line,
              }}
            />
          )}

          {groups.map((group) => {
            const isNext = group.time === nextTime;
            const groupAllChecked = group.items.every((i) => checked.has(i.key));
            const tips = [...new Set(group.items.map((i) => i.tip).filter(Boolean))] as string[];
            return (
              <div key={group.time} style={{ position: "relative", marginBottom: 22 }}>
                {/* 타임라인 점 */}
                <span
                  style={{
                    position: "absolute",
                    left: -30,
                    top: 4,
                    width: 18,
                    height: 18,
                    borderRadius: "50%",
                    background: isNext ? c.pink : groupAllChecked ? "#FFB3C4" : "#E0D0D6",
                    border: `4px solid ${c.pageBg}`,
                    boxSizing: "border-box",
                  }}
                />

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 8,
                  }}
                >
                  <span style={{ fontSize: 18, fontWeight: 800, color: c.text }}>{group.time}</span>
                  {isNext && (
                    <span
                      style={{
                        background: c.pink,
                        color: "white",
                        borderRadius: 999,
                        padding: "3px 10px",
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      다음 복용
                    </span>
                  )}
                </div>

                <div
                  style={{
                    background: isNext ? c.pinkSoft : c.cardBg,
                    border: `1.5px solid ${isNext ? c.pink : c.cardBorder}`,
                    borderRadius: 16,
                    padding: 14,
                    boxShadow: "0 2px 10px rgba(120, 100, 60, 0.06)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: 10,
                    }}
                  >
                    <span style={{ color: c.pink, fontSize: 13, fontWeight: 700 }}>
                      ▼ {group.isPrescription ? "처방약" : "복용약"} {group.items.length}종
                    </span>
                    {isToday && (
                      <button
                        type="button"
                        onClick={() => checkAll(group)}
                        style={{
                          border: "none",
                          background: groupAllChecked ? c.pink : c.pinkSoft,
                          color: groupAllChecked ? "white" : c.pink,
                          borderRadius: 8,
                          padding: "5px 10px",
                          fontSize: 12,
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        ☑ 모두 복용
                      </button>
                    )}
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {group.items.map((item) => {
                      const done = checked.has(item.key);
                      const isExpanded = expandedNames.has(item.name);
                      const durState = durByName.get(item.name);
                      return (
                        <div
                          key={item.key}
                          style={{
                            background: "#FDFCF9",
                            border: `1px solid ${c.cardBorder}`,
                            borderRadius: 12,
                            padding: "10px 12px",
                            opacity: done ? 0.55 : 1,
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            {isToday ? (
                              <button
                                type="button"
                                aria-label={
                                  done ? `${item.name} 복용 취소` : `${item.name} 복용 체크`
                                }
                                onClick={() => toggle(item.key)}
                                style={{
                                  width: 22,
                                  height: 22,
                                  borderRadius: "50%",
                                  flexShrink: 0,
                                  border: done ? "none" : `2px solid ${c.line}`,
                                  background: done ? c.pink : "white",
                                  color: "white",
                                  fontSize: 13,
                                  lineHeight: 1,
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                }}
                              >
                                {done ? "✓" : ""}
                              </button>
                            ) : (
                              <span style={{ fontSize: 15 }}>💊</span>
                            )}
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <p
                                style={{
                                  margin: 0,
                                  fontSize: 14,
                                  fontWeight: 700,
                                  color: c.text,
                                  textDecoration: done ? "line-through" : "none",
                                }}
                              >
                                {isToday && "💊 "}
                                {item.name}{" "}
                                <span style={{ fontSize: 12, fontWeight: 400, color: c.textMuted }}>
                                  하루 {item.doseCount}회
                                </span>
                              </p>
                              {item.subLabel && (
                                <p style={{ margin: "2px 0 0", fontSize: 12, color: c.textMuted }}>
                                  {item.hospitalName ? `🏥 ${item.subLabel}` : item.subLabel}
                                </p>
                              )}
                            </div>
                            <button
                              type="button"
                              onClick={() => toggleDurExpand(item.name)}
                              aria-expanded={isExpanded}
                              style={{
                                flexShrink: 0,
                                border: "none",
                                background: "none",
                                color: c.pink,
                                fontSize: 11,
                                fontWeight: 700,
                                cursor: "pointer",
                                padding: "4px 6px",
                              }}
                            >
                              주의사항 {isExpanded ? "닫기 ▲" : "보기 ▼"}
                            </button>
                          </div>

                          {isExpanded && (
                            <div
                              style={{
                                marginTop: 8,
                                background: c.tipBg,
                                borderRadius: 10,
                                padding: "8px 12px",
                                fontSize: 12,
                                color: c.tipText,
                                lineHeight: 1.5,
                              }}
                            >
                              {(!durState || durState.status === "loading") && "조회 중..."}
                              {durState?.status === "error" && "주의사항을 불러오지 못했습니다."}
                              {durState?.status === "done" && durState.results.length === 0 && (
                                <span>
                                  {durState.notFoundReason ?? "등록된 DUR/효능 정보가 없습니다."}
                                </span>
                              )}
                              {durState?.status === "done" && durState.results.length > 0 && (
                                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                  {durState.results.length > 1 && (
                                    <span style={{ color: c.textMuted }}>
                                      "{item.name}" 이름으로 매칭된 {durState.results.length}건 —
                                      같은 이름의 다른 약이 섞여 있을 수 있어요.
                                    </span>
                                  )}
                                  {durState.results.map((r, idx) => (
                                    <div key={idx}>
                                      <strong>
                                        {r.item_name} ({r.entp_name})
                                      </strong>
                                      <p style={{ margin: "2px 0" }}>💊 효능: {r.efficacy}</p>
                                      <p style={{ margin: "2px 0" }}>
                                        ⚠️ 주의사항: {r.precautions}
                                      </p>
                                      <p
                                        style={{
                                          margin: "2px 0 0",
                                          fontSize: 11,
                                          color: c.textMuted,
                                        }}
                                      >
                                        {DUR_SOURCE_LABEL}
                                      </p>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {tips.length > 0 && (
                    <div
                      style={{
                        background: c.tipBg,
                        borderRadius: 10,
                        padding: "8px 12px",
                        marginTop: 10,
                        fontSize: 12,
                        color: c.tipText,
                        lineHeight: 1.5,
                      }}
                    >
                      💡 {tips.join(" · ")}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
