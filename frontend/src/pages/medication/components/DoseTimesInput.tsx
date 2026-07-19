import { useState, useEffect } from "react";

/** 하루 복용 횟수 선택지 — 임상 표기(qd/bid/tid)를 같이 보여준다. AlarmForm과 동일한 패턴. */
const DOSE_OPTIONS = [
  { count: 1, label: "1회 (qd)" },
  { count: 2, label: "2회 (bid)" },
  { count: 3, label: "3회 (tid)" },
  { count: 4, label: "4회 (qid)" },
] as const;

/** 횟수를 바꿨을 때 시간칸에 채워줄 기본 시각. */
const DOSE_TIME_PRESETS: Record<number, string[]> = {
  1: ["08:00"],
  2: ["08:00", "20:00"],
  3: ["08:00", "13:00", "19:00"],
  4: ["08:00", "12:00", "17:00", "21:00"],
};

interface TimeParts {
  period: "오전" | "오후";
  hour: number;
  minute: number;
}

/** "HH:MM" 24시간 문자열 → 오전/오후 + 12시간제 시/분 */
function parseTime(time: string): TimeParts {
  const [hh, mm] = time.split(":").map(Number);
  return { period: hh < 12 ? "오전" : "오후", hour: hh % 12 === 0 ? 12 : hh % 12, minute: mm };
}

function toTimeString(tp: TimeParts): string {
  let h = tp.hour % 12;
  if (tp.period === "오후") h += 12;
  return `${String(h).padStart(2, "0")}:${String(tp.minute).padStart(2, "0")}`;
}

interface Props {
  value: string[];
  onChange: (times: string[]) => void;
}

/** 복약 시간을 "횟수 선택 + 회차별 시간 조정" 방식으로 입력받는 컴포넌트 (AlarmForm 패턴 재사용). */
export default function DoseTimesInput({ value, onChange }: Props) {
  const initialTimes = value.length > 0 ? value.map(parseTime) : [parseTime("08:00")];
  const [doseCount, setDoseCount] = useState(initialTimes.length);
  const [times, setTimes] = useState<TimeParts[]>(initialTimes);

  useEffect(() => {
    onChange([...new Set(times.map(toTimeString))]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [times]);

  const handleDoseCountChange = (count: number) => {
    setDoseCount(count);
    setTimes((prev) =>
      Array.from({ length: count }, (_, i) => prev[i] ?? parseTime(DOSE_TIME_PRESETS[count][i])),
    );
  };

  const updateTime = (index: number, patch: Partial<TimeParts>) => {
    setTimes((prev) => prev.map((tp, i) => (i === index ? { ...tp, ...patch } : tp)));
  };

  return (
    <div>
      <label style={{ display: "block", fontSize: "13px", color: "#666", marginBottom: "6px" }}>
        하루 복용 횟수
      </label>
      <div style={{ display: "flex", gap: "8px", marginBottom: "10px" }}>
        {DOSE_OPTIONS.map((opt) => (
          <button
            key={opt.count}
            type="button"
            onClick={() => handleDoseCountChange(opt.count)}
            style={{
              padding: "6px 12px",
              borderRadius: "999px",
              border: "1px solid #ccc",
              background: doseCount === opt.count ? "#4caf50" : "white",
              color: doseCount === opt.count ? "white" : "#333",
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <label style={{ display: "block", fontSize: "13px", color: "#666", marginBottom: "4px" }}>
        복용 시각
      </label>
      {times.map((tp, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
          {times.length > 1 && (
            <span style={{ fontSize: "12px", color: "#666", width: "34px", flexShrink: 0 }}>
              {i + 1}회차
            </span>
          )}
          {(["오전", "오후"] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => updateTime(i, { period: p })}
              style={{
                padding: "6px 12px",
                borderRadius: "999px",
                border: "1px solid #ccc",
                background: tp.period === p ? "#4caf50" : "white",
                color: tp.period === p ? "white" : "#333",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              {p}
            </button>
          ))}
          <input
            type="number"
            min={1}
            max={12}
            value={tp.hour}
            onChange={(e) =>
              updateTime(i, { hour: Math.min(12, Math.max(1, Number(e.target.value) || 1)) })
            }
            aria-label={`${i + 1}회차 시`}
            style={{
              width: "52px",
              padding: "8px",
              borderRadius: "6px",
              border: "1px solid #ccc",
              textAlign: "center",
              fontSize: "14px",
            }}
          />
          <span style={{ color: "#666" }}>:</span>
          <input
            type="number"
            min={0}
            max={59}
            value={tp.minute}
            onChange={(e) =>
              updateTime(i, { minute: Math.min(59, Math.max(0, Number(e.target.value) || 0)) })
            }
            aria-label={`${i + 1}회차 분`}
            style={{
              width: "52px",
              padding: "8px",
              borderRadius: "6px",
              border: "1px solid #ccc",
              textAlign: "center",
              fontSize: "14px",
            }}
          />
        </div>
      ))}
    </div>
  );
}
