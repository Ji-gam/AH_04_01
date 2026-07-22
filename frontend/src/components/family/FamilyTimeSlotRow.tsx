import { useState } from "react";

import { pinkTheme as t } from "../../theme/pinkTheme";

import AnalogClockPicker from "./AnalogClockPicker";

interface TimeParts {
  period: "오전" | "오후";
  hour: number;
  minute: number;
}

/** "HH:MM"(24시간) → 오전/오후 + 12시간제 시/분. FamilyTrackerView의 timeSlots가 이
 * 형식(초 없음)을 그대로 쓰고 있어서 맞춰준다 - AlarmForm(본인 몫)의 "HH:MM:SS"랑은
 * 다르니 그쪽 로직을 그대로 재사용하면 안 된다(2026-07-21 스코프 분리 확인). */
function parseHHMM(value: string): TimeParts {
  const [hh, mm] = value.split(":").map(Number);
  return { period: hh < 12 ? "오전" : "오후", hour: hh % 12 === 0 ? 12 : hh % 12, minute: mm || 0 };
}

function toHHMM(tp: TimeParts): string {
  let h = tp.hour % 12;
  if (tp.period === "오후") h += 12;
  return `${String(h).padStart(2, "0")}:${String(tp.minute).padStart(2, "0")}`;
}

interface Props {
  value: string; // "HH:MM"
  onChange: (value: string) => void;
}

/** [실험용] 가족관리 - 처방전 인식 후 시간대 설정에서 쓰는 시간 입력 한 줄. 기존
 * `<input type="time">`(브라우저 기본 시간선택기) 대신, 본인 몫 복약알림 화면과 비슷한
 * 스타일(오전/오후 버튼 + 시/분 숫자칸)로 통일하고, 시계 아이콘을 누르면 아날로그 시계로도
 * 고를 수 있게 추가했다. 채택 여부는 실제로 써보고 팀에서 정하기로 함. */
export default function FamilyTimeSlotRow({ value, onChange }: Props) {
  const tp = parseHHMM(value);
  const [clockOpen, setClockOpen] = useState(false);

  const update = (patch: Partial<TimeParts>) => {
    onChange(toHHMM({ ...tp, ...patch }));
  };

  return (
    <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 6 }}>
      {(["오전", "오후"] as const).map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => update({ period: p })}
          style={{
            padding: "6px 10px",
            borderRadius: 999,
            border: `1px solid ${t.border}`,
            background: tp.period === p ? t.primary : "white",
            color: tp.period === p ? "white" : t.text,
            fontSize: 12,
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
        onChange={(e) => update({ hour: Math.min(12, Math.max(1, Number(e.target.value) || 1)) })}
        aria-label="시"
        style={{
          width: 46,
          padding: "6px 6px",
          borderRadius: 8,
          border: `1px solid ${t.border}`,
          outline: "none",
          fontSize: 13,
          textAlign: "center",
        }}
      />
      <span style={{ color: t.textMuted }}>:</span>
      <input
        type="number"
        min={0}
        max={59}
        value={tp.minute}
        onChange={(e) => update({ minute: Math.min(59, Math.max(0, Number(e.target.value) || 0)) })}
        aria-label="분"
        style={{
          width: 46,
          padding: "6px 6px",
          borderRadius: 8,
          border: `1px solid ${t.border}`,
          outline: "none",
          fontSize: 13,
          textAlign: "center",
        }}
      />
      <button
        type="button"
        aria-label="시계로 시각 선택"
        onClick={() => setClockOpen((v) => !v)}
        style={{ border: "none", background: "none", cursor: "pointer", fontSize: 16, padding: 2 }}
      >
        🕐
      </button>
      {clockOpen && (
        <div style={{ position: "absolute", top: "100%", left: 0, marginTop: 6, zIndex: 20 }}>
          <AnalogClockPicker
            hour={tp.hour}
            minute={tp.minute}
            onChange={(h, m) => update({ hour: h, minute: m })}
            onClose={() => setClockOpen(false)}
          />
        </div>
      )}
    </div>
  );
}
