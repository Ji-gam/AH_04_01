import type { NotificationScheduleResult } from "../../../api/types";
import { KOREAN_DAYS, isScheduleDueOnDate, toDateString } from "../dateUtils";
import { alarmTheme as t } from "../theme";

/** month는 0부터 시작(1월=0). 1일 이전 자리는 null로 채워 그리드 정렬을 맞춘다. */
function getMonthCells(year: number, month: number): (Date | null)[] {
  const firstDay = new Date(year, month, 1);
  const lastDate = new Date(year, month + 1, 0).getDate();
  const cells: (Date | null)[] = [];
  for (let i = 0; i < firstDay.getDay(); i++) cells.push(null);
  for (let d = 1; d <= lastDate; d++) cells.push(new Date(year, month, d));
  return cells;
}

interface Props {
  year: number;
  month: number; // 0-indexed
  selectedDateStr: string;
  schedules: NotificationScheduleResult[];
  onSelectDate: (dateStr: string) => void;
  onPrevMonth: () => void;
  onNextMonth: () => void;
}

export default function AlarmCalendar({
  year,
  month,
  selectedDateStr,
  schedules,
  onSelectDate,
  onPrevMonth,
  onNextMonth,
}: Props) {
  const todayStr = toDateString(new Date());
  const cells = getMonthCells(year, month);
  const activeSchedules = schedules.filter((s) => s.is_active);

  const navBtnStyle: React.CSSProperties = {
    border: "none",
    background: "none",
    color: t.primary,
    fontSize: 16,
    fontWeight: 700,
    cursor: "pointer",
    padding: "4px 10px",
  };

  return (
    <div
      style={{
        background: t.cardBg,
        border: `1px solid ${t.border}`,
        borderRadius: 16,
        padding: 16,
        marginBottom: 20,
        boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
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
        <button type="button" onClick={onPrevMonth} aria-label="이전 달" style={navBtnStyle}>
          ‹
        </button>
        <span style={{ fontWeight: 700, color: t.text, fontSize: 15 }}>
          {year}년 {month + 1}월
        </span>
        <button type="button" onClick={onNextMonth} aria-label="다음 달" style={navBtnStyle}>
          ›
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, 1fr)",
          textAlign: "center",
          fontSize: 12,
          color: t.textMuted,
          marginBottom: 6,
        }}
      >
        {KOREAN_DAYS.map((d, i) => (
          <span key={d} style={{ color: i === 0 ? t.danger : i === 6 ? "#7B9ACC" : t.textMuted }}>
            {d}
          </span>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", rowGap: 4 }}>
        {cells.map((date, i) => {
          if (!date) return <div key={`blank-${i}`} />;
          const dateStr = toDateString(date);
          const isSelected = dateStr === selectedDateStr;
          const isToday = dateStr === todayStr;
          const hasSchedule = activeSchedules.some((s) => isScheduleDueOnDate(s, date));
          return (
            <button
              key={dateStr}
              type="button"
              onClick={() => onSelectDate(dateStr)}
              style={{
                margin: "0 auto",
                width: 38,
                height: 42,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
                borderRadius: 10,
                cursor: "pointer",
                fontSize: 13,
                color: isSelected ? "white" : t.text,
                background: isSelected ? t.primary : isToday ? t.primarySoft : "transparent",
                border: isToday && !isSelected ? `1px solid ${t.primary}` : "1px solid transparent",
                fontWeight: isToday || isSelected ? 700 : 400,
              }}
            >
              <span>{date.getDate()}</span>
              <span
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: hasSchedule ? (isSelected ? "white" : t.primary) : "transparent",
                }}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
