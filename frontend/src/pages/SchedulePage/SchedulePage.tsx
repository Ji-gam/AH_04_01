import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiFetch } from "../../api/client";
import { notificationApi } from "../../api/notificationApi";
import type { NotificationScheduleResult } from "../../api/types";
import type { MedicationSchedule } from "../../hooks/useMedication";
import { isScheduleDueOnDate, toDateString } from "../AlarmPage/dateUtils";

/** 사진 레퍼런스 팔레트 — 크림 배경 + 그린 포인트 + 다음 복용 오렌지 */
const c = {
  pageBg: "#FBF7EF",
  cardBg: "#FFFFFF",
  cardBorder: "#F0EAE0",
  text: "#3D3A34",
  textMuted: "#9B958A",
  green: "#3FA776",
  greenSoft: "#E9F6EF",
  orange: "#F59A23",
  orangeSoft: "#FFF4E3",
  tipBg: "#FFFBEA",
  tipText: "#8A7B4F",
  line: "#E5DFD3",
};

const FORM_TYPE_UNIT: Record<string, string> = {
  TABLET: "1정",
  CAPSULE: "1캡슐",
  INJECTION: "주사",
  SYRUP: "시럽",
};

interface TimelineItem {
  key: string;
  name: string;
  /** 약 이름 아래 줄 — 병원명이 있으면 병원명, 없으면 제형 단위 */
  subLabel: string | null;
  hospitalName: string | null;
  editTo: string;
  tip: string | null;
}

interface TimeGroup {
  time: string; // "HH:MM"
  items: TimelineItem[];
  isPrescription: boolean;
}

function buildGroups(
  meds: MedicationSchedule[],
  alarms: NotificationScheduleResult[],
  date: Date,
): TimeGroup[] {
  const byTime = new Map<string, TimelineItem[]>();
  const push = (time: string, item: TimelineItem) => {
    const arr = byTime.get(time) ?? [];
    arr.push(item);
    byTime.set(time, arr);
  };

  for (const m of meds) {
    for (const time of m.times) {
      push(time.slice(0, 5), {
        key: `med-${m.id}-${time}`,
        name: m.drug_name,
        subLabel:
          m.hospital_name ?? (m.form_type ? (FORM_TYPE_UNIT[m.form_type] ?? m.form_type) : null),
        hospitalName: m.hospital_name ?? null,
        editTo: "/medication",
        tip: m.dosage_guideline ?? null,
      });
    }
  }

  for (const a of alarms) {
    if (!a.is_active || !isScheduleDueOnDate(a, date)) continue;
    push(a.alarm_time.slice(0, 5), {
      key: `alarm-${a.id}`,
      name: a.medication_name,
      subLabel: "직접 등록 알림",
      hospitalName: null,
      editTo: "/alarms",
      tip: null,
    });
  }

  return [...byTime.entries()]
    .sort(([t1], [t2]) => t1.localeCompare(t2))
    .map(([time, items]) => ({
      time,
      items,
      isPrescription: items.some((i) => i.key.startsWith("med-")),
    }));
}

function getCurrentHHMM(): string {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
}

/** 복용 체크는 날짜별 localStorage에 보관한다(백엔드 복용 기록 도메인 합류 전까지의 임시 저장소). */
function loadChecked(dateStr: string): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(`intake-${dateStr}`) ?? "[]") as string[]);
  } catch {
    return new Set();
  }
}

function saveChecked(dateStr: string, checked: Set<string>) {
  localStorage.setItem(`intake-${dateStr}`, JSON.stringify([...checked]));
}

export default function SchedulePage() {
  const [searchParams] = useSearchParams();
  const todayStr = toDateString(new Date());
  const dateStr = searchParams.get("date") ?? todayStr;
  const date = new Date(`${dateStr}T00:00:00`);
  const isToday = dateStr === todayStr;

  const [meds, setMeds] = useState<MedicationSchedule[]>([]);
  const [alarms, setAlarms] = useState<NotificationScheduleResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(() => loadChecked(dateStr));

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

  const title = isToday
    ? "오늘의 복약 시간표"
    : `${date.getMonth() + 1}월 ${date.getDate()}일 복약 시간표`;

  return (
    <div style={{ background: c.pageBg, minHeight: "100vh", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
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
                background: remaining > 0 ? c.orangeSoft : c.greenSoft,
                color: remaining > 0 ? c.orange : c.green,
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
              <Link to="/medication" style={{ color: c.green }}>
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
                    background: isNext ? c.orange : groupAllChecked ? c.green : "#CFC9BC",
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
                        background: c.orange,
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
                    background: isNext ? c.orangeSoft : c.cardBg,
                    border: `1.5px solid ${isNext ? c.orange : c.cardBorder}`,
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
                    <span style={{ color: c.green, fontSize: 13, fontWeight: 700 }}>
                      ▼ {group.isPrescription ? "처방약" : "복용약"} {group.items.length}종
                    </span>
                    {isToday && (
                      <button
                        type="button"
                        onClick={() => checkAll(group)}
                        style={{
                          border: "none",
                          background: groupAllChecked ? c.green : c.greenSoft,
                          color: groupAllChecked ? "white" : c.green,
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
                      return (
                        <div
                          key={item.key}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            background: "#FDFCF9",
                            border: `1px solid ${c.cardBorder}`,
                            borderRadius: 12,
                            padding: "10px 12px",
                            opacity: done ? 0.55 : 1,
                          }}
                        >
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
                                background: done ? c.green : "white",
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
                              {item.name}
                            </p>
                            {item.subLabel && (
                              <p style={{ margin: "2px 0 0", fontSize: 12, color: c.textMuted }}>
                                {item.hospitalName ? `🏥 ${item.subLabel}` : item.subLabel}
                              </p>
                            )}
                          </div>
                          <Link
                            to={item.editTo}
                            aria-label={`${item.name} 관리로 이동`}
                            style={{ textDecoration: "none", fontSize: 14, flexShrink: 0 }}
                          >
                            ✏️
                          </Link>
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
