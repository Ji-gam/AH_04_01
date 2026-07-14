import { useState } from "react";

import { pinkTheme } from "../../theme/pinkTheme";

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: "8px",
  fontSize: 14,
};

const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS: number[] = [];
for (let y = CURRENT_YEAR; y >= CURRENT_YEAR - 120; y--) YEAR_OPTIONS.push(y);
const MONTH_OPTIONS = Array.from({ length: 12 }, (_, i) => i + 1);
const DAY_OPTIONS = Array.from({ length: 31 }, (_, i) => i + 1);

/** 년/월/일 각각 드롭다운(select) - 아래화살표를 누르면 전체 목록이 쭉 뜨고, 그중 하나를 클릭하면
 * 바로 그 값으로 선택된다(1씩 조정하는 스텝퍼가 아니라, 원하는 값으로 바로 점프). */
function ValueSelect({
  value,
  placeholder,
  options,
  onChange,
  flex,
}: {
  value: string;
  placeholder: string;
  options: number[];
  onChange: (next: string) => void;
  flex: number;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{ ...inputStyle, flex, color: value === "" ? pinkTheme.textMuted : pinkTheme.text }}
    >
      <option value="">{placeholder}</option>
      {options.map((n) => (
        <option key={n} value={n}>
          {n}
        </option>
      ))}
    </select>
  );
}

const DAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

/** 달력 팝업. "이전달/다음달"을 눌러가는 방식 대신, 연도/월을 드롭다운으로 바로 골라 점프하는
 * 방식을 쓴다 - 옛날 생년월일을 고를 때 이게 훨씬 빠르다고 알려진 패턴(NN/g 등 UX 가이드 공통 권장). */
function CalendarPopup({
  year,
  month,
  day,
  onSelect,
}: {
  year: string;
  month: string;
  day: string;
  onSelect: (year: string, month: string, day: string) => void;
}) {
  const today = new Date();
  const [viewYear, setViewYear] = useState(Number(year) || today.getFullYear() - 30);
  const [viewMonth, setViewMonth] = useState(Number(month) || today.getMonth() + 1);

  const firstDayOfMonth = new Date(viewYear, viewMonth - 1, 1).getDay(); // 0=일요일
  const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
  const cells: (number | null)[] = [
    ...Array(firstDayOfMonth).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  const isTodayMonth = viewYear === today.getFullYear() && viewMonth === today.getMonth() + 1;

  return (
    <div
      style={{
        marginTop: 10,
        border: `1px solid ${pinkTheme.border}`,
        borderRadius: 12,
        padding: 12,
        background: pinkTheme.cardBg,
      }}
    >
      <style>{`
        .remedi-cal-day { transition: background 0.12s ease; }
        .remedi-cal-day:not(.remedi-cal-day--selected):hover { background: ${pinkTheme.primarySoft} !important; }
      `}</style>
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        <select
          value={viewYear}
          onChange={(e) => setViewYear(Number(e.target.value))}
          style={{ ...inputStyle, flex: 1.3, padding: "6px 8px", fontSize: 13 }}
        >
          {YEAR_OPTIONS.map((y) => (
            <option key={y} value={y}>
              {y}년
            </option>
          ))}
        </select>
        <select
          value={viewMonth}
          onChange={(e) => setViewMonth(Number(e.target.value))}
          style={{ ...inputStyle, flex: 1, padding: "6px 8px", fontSize: 13 }}
        >
          {MONTH_OPTIONS.map((m) => (
            <option key={m} value={m}>
              {m}월
            </option>
          ))}
        </select>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, 1fr)",
          borderBottom: `1px solid ${pinkTheme.border}`,
          paddingBottom: 6,
          marginBottom: 4,
        }}
      >
        {DAY_LABELS.map((label) => (
          <div
            key={label}
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: pinkTheme.textMuted,
              textAlign: "center",
            }}
          >
            {label}
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", rowGap: 4 }}>
        {cells.map((d, idx) => {
          if (d === null) return <div key={`blank-${idx}`} />;
          const isSelected =
            String(viewYear) === year && String(viewMonth) === month && String(d) === day;
          const isToday = isTodayMonth && d === today.getDate();
          return (
            <div key={d} style={{ display: "flex", justifyContent: "center" }}>
              <button
                type="button"
                onClick={() => onSelect(String(viewYear), String(viewMonth), String(d))}
                className={`remedi-cal-day${isSelected ? " remedi-cal-day--selected" : ""}`}
                style={{
                  width: 30,
                  height: 30,
                  border: isToday && !isSelected ? `1px solid ${pinkTheme.primary}` : "none",
                  borderRadius: "50%",
                  fontSize: 12,
                  cursor: "pointer",
                  background: isSelected ? pinkTheme.primary : "transparent",
                  color: isSelected ? "#fff" : pinkTheme.text,
                }}
              >
                {d}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface BirthDateInputProps {
  year: string;
  month: string;
  day: string;
  onChange: (year: string, month: string, day: string) => void;
}

/** 개인건강정보의 생년월일 입력. 두 방식을 지원한다:
 * 1) 년/월/일 드롭다운 3개 - 아래화살표 누르면 전체 목록이 뜨고 클릭하면 바로 선택
 * 2) 달력 버튼 -> 연/월 드롭다운으로 바로 점프 + 날짜 클릭 (달력이 익숙한 사람을 위한 대안)
 * 두 방식 다 같은 값을 공유해서 실시간으로 서로 맞춰진다. */
export default function BirthDateInput({ year, month, day, onChange }: BirthDateInputProps) {
  const [showCalendar, setShowCalendar] = useState(false);

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
        <ValueSelect
          value={year}
          placeholder="년"
          options={YEAR_OPTIONS}
          onChange={(v) => onChange(v, month, day)}
          flex={1.4}
        />
        <ValueSelect
          value={month}
          placeholder="월"
          options={MONTH_OPTIONS}
          onChange={(v) => onChange(year, v, day)}
          flex={1}
        />
        <ValueSelect
          value={day}
          placeholder="일"
          options={DAY_OPTIONS}
          onChange={(v) => onChange(year, month, v)}
          flex={1}
        />
        <button
          type="button"
          onClick={() => setShowCalendar((prev) => !prev)}
          aria-label="달력으로 선택하기"
          style={{
            border: `1px solid ${pinkTheme.border}`,
            borderRadius: 8,
            background: showCalendar ? pinkTheme.primary : pinkTheme.cardBg,
            color: showCalendar ? "#fff" : pinkTheme.text,
            width: 40,
            fontSize: 16,
            cursor: "pointer",
          }}
        >
          📅
        </button>
      </div>

      {showCalendar && (
        <CalendarPopup
          year={year}
          month={month}
          day={day}
          onSelect={(y, m, d) => {
            onChange(y, m, d);
            setShowCalendar(false);
          }}
        />
      )}
    </div>
  );
}
