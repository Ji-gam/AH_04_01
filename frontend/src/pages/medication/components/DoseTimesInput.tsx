import { useState, useEffect } from "react";

import TimeInputField from "../../../components/ui/TimeInputField";
import { pinkTheme as t } from "../../../theme/pinkTheme";

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

interface Props {
  value: string[];
  onChange: (times: string[]) => void;
}

/** 복약 시간을 "횟수 선택 + 회차별 시간 조정" 방식으로 입력받는 컴포넌트 (AlarmForm 패턴 재사용). */
export default function DoseTimesInput({ value, onChange }: Props) {
  const initialTimes = value.length > 0 ? value : ["08:00"];
  const [doseCount, setDoseCount] = useState(initialTimes.length);
  const [times, setTimes] = useState<string[]>(initialTimes);

  useEffect(() => {
    onChange([...new Set(times)]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [times]);

  const handleDoseCountChange = (count: number) => {
    setDoseCount(count);
    setTimes((prev) =>
      Array.from({ length: count }, (_, i) => prev[i] ?? DOSE_TIME_PRESETS[count][i]),
    );
  };

  const updateTime = (index: number, newValue: string) => {
    setTimes((prev) => prev.map((tp, i) => (i === index ? newValue : tp)));
  };

  return (
    <div>
      <label
        style={{ display: "block", fontSize: "13px", color: t.textMuted, marginBottom: "6px" }}
      >
        하루 복용 횟수
      </label>
      <div style={{ display: "flex", gap: "8px", marginBottom: "10px" }}>
        {DOSE_OPTIONS.map((opt) => (
          <button
            key={opt.count}
            type="button"
            onClick={() => handleDoseCountChange(opt.count)}
            style={{
              padding: "8px 14px",
              borderRadius: "999px",
              border: `1px solid ${t.border}`,
              background: doseCount === opt.count ? t.primary : "white",
              color: doseCount === opt.count ? "white" : t.text,
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <label
        style={{ display: "block", fontSize: "13px", color: t.textMuted, marginBottom: "4px" }}
      >
        복용 시각
      </label>
      {times.map((time, i) => (
        <div
          key={i}
          style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}
        >
          {times.length > 1 && (
            <span style={{ fontSize: "12px", color: t.textMuted, width: "34px", flexShrink: 0 }}>
              {i + 1}회차
            </span>
          )}
          <TimeInputField value={time} onChange={(v) => updateTime(i, v)} />
        </div>
      ))}
    </div>
  );
}
