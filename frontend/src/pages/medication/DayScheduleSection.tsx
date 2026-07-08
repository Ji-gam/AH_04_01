import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { notificationApi } from "../../api/notificationApi";
import type { NotificationScheduleResult } from "../../api/types";
import type { MedicationSchedule } from "../../hooks/useMedication";
import { isScheduleDueOnDate, toDateString } from "../AlarmPage/dateUtils";

/** form_type 코드 → 사용자용 한글 표기 */
const FORM_TYPE_LABELS: Record<string, string> = {
  TABLET: "정제(알약)",
  CAPSULE: "캡슐",
  INJECTION: "주사제",
  SYRUP: "시럽",
};

interface DayItem {
  key: string;
  name: string;
  doseCount: number;
  times: string[];
  /** 무슨 약인지 — 마스터 데이터(제형/복용지침) 기반. 없으면 null */
  kindLabel: string | null;
  source: "약 스케줄" | "직접 등록 알림";
}

/** 복약알림(notification)은 같은 약 이름끼리 묶어 하루 N회 하나의 항목으로 만든다. */
function buildAlarmItems(notifications: NotificationScheduleResult[], date: Date): DayItem[] {
  const grouped = new Map<string, string[]>();
  for (const n of notifications) {
    if (!n.is_active || !isScheduleDueOnDate(n, date)) continue;
    const times = grouped.get(n.medication_name) ?? [];
    times.push(n.alarm_time.slice(0, 5));
    grouped.set(n.medication_name, times);
  }
  return [...grouped.entries()].map(([name, times]) => ({
    key: `alarm-${name}`,
    name,
    doseCount: times.length,
    times: times.sort(),
    kindLabel: null,
    source: "직접 등록 알림",
  }));
}

/** 약 스케줄(medication)은 요일 개념이 없어 매일 복용으로 보고 모두 포함한다. */
function buildMedicationItems(schedules: MedicationSchedule[]): DayItem[] {
  return schedules.map((s) => ({
    key: `med-${s.id}`,
    name: s.drug_name,
    doseCount: s.times.length,
    times: [...s.times].sort(),
    kindLabel: (s.form_type && FORM_TYPE_LABELS[s.form_type]) || s.form_type || null,
    source: "약 스케줄",
  }));
}

interface Props {
  medicationSchedules: MedicationSchedule[];
}

/**
 * 복약알림 달력에서 날짜를 눌러 넘어오면(?date=YYYY-MM-DD) 그 날짜의
 * 통합 복용 목록(OCR/수동 등록 약 + 직접 등록 알림)을 보여준다. 파라미터가 없으면 오늘.
 */
export default function DayScheduleSection({ medicationSchedules }: Props) {
  const [searchParams] = useSearchParams();
  const dateStr = searchParams.get("date") ?? toDateString(new Date());
  const date = new Date(`${dateStr}T00:00:00`);
  const isToday = dateStr === toDateString(new Date());

  const [notifications, setNotifications] = useState<NotificationScheduleResult[]>([]);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  useEffect(() => {
    notificationApi
      .list()
      .then(setNotifications)
      .catch(() => setNotifications([]));
  }, []);

  const items = [
    ...buildMedicationItems(medicationSchedules),
    ...buildAlarmItems(notifications, date),
  ].sort((a, b) => (a.times[0] ?? "").localeCompare(b.times[0] ?? ""));

  const title = isToday
    ? "오늘의 복용 목록"
    : `${date.getMonth() + 1}월 ${date.getDate()}일 복용 목록`;

  return (
    <div
      style={{
        border: "1px solid #ccc",
        borderRadius: "8px",
        padding: "15px",
        marginBottom: "20px",
      }}
    >
      <h3 style={{ margin: "0 0 10px" }}>📅 {title}</h3>
      {items.length === 0 ? (
        <p style={{ color: "#888", fontSize: "14px" }}>이 날짜에 복용할 약이 없습니다.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {items.map((item) => (
            <div key={item.key} style={{ border: "1px solid #eee", borderRadius: "6px" }}>
              <button
                type="button"
                onClick={() => setExpandedKey(expandedKey === item.key ? null : item.key)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  border: "none",
                  background: "none",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: "14px",
                }}
              >
                <strong>{item.name}</strong>
                <span style={{ color: "#666", fontSize: "13px" }}>
                  하루 {item.doseCount}회 · {item.times.join(", ")}
                </span>
              </button>
              {expandedKey === item.key && (
                <div style={{ padding: "0 12px 12px", fontSize: "13px", color: "#444" }}>
                  <p style={{ margin: "4px 0" }}>
                    <strong>무슨 약:</strong>{" "}
                    {item.kindLabel ?? "정보 준비 중 (약품 마스터 데이터 연동 예정)"}
                  </p>
                  <p style={{ margin: "4px 0" }}>
                    <strong>복용 횟수:</strong> 하루 {item.doseCount}번 ({item.times.join(", ")})
                  </p>
                  <p style={{ margin: "4px 0", color: "#999" }}>출처: {item.source}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
