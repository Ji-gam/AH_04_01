import { useState } from "react";

import { pinkTheme as t } from "../../theme/pinkTheme";

interface AnalogClockPickerProps {
  hour: number; // 1-12
  minute: number; // 0-59
  onChange: (hour: number, minute: number) => void;
  onClose: () => void;
}

const RADIUS = 90;
const CENTER = 100;
const SIZE = 200;

/** 각도(0=12시 방향, 시계방향)에 대응하는 SVG 좌표. */
function pointOnCircle(angleDeg: number, r: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: CENTER + r * Math.cos(rad), y: CENTER + r * Math.sin(rad) };
}

/** 아날로그 시계 - Material Design 시간선택기와 비슷하게, "시"를 먼저 고르면 자동으로
 * "분" 선택으로 넘어간다. 클릭/탭만으로 고르는 방식(드래그 아님) - 손가락으로도 정확히
 * 찍기 쉽고 구현도 단순해서 이렇게 만들었다. 원래 가족관리 화면 전용으로 만들었다가
 * (2026-07-21), 시간 입력이 있는 모든 화면에서 같은 방식을 쓰기로 하면서 공용
 * 컴포넌트로 옮겼다(2026-07-23) - `TimeInputField`가 이 컴포넌트를 감싸는 조합 UI다. */
export default function AnalogClockPicker({
  hour,
  minute,
  onChange,
  onClose,
}: AnalogClockPickerProps) {
  const [mode, setMode] = useState<"hour" | "minute">("hour");

  const handleHourClick = (h: number) => {
    onChange(h, minute);
    setMode("minute");
  };

  const handleMinuteClick = (m: number) => {
    onChange(hour, m);
  };

  const hourNumbers = Array.from({ length: 12 }, (_, i) => i + 1);
  const minuteNumbers = Array.from({ length: 12 }, (_, i) => i * 5);

  const selectedAngle = mode === "hour" ? (hour % 12) * 30 : (minute / 5) * 30;
  const handEnd = pointOnCircle(selectedAngle, RADIUS - 20);

  return (
    <div
      style={{
        background: t.cardBg,
        borderRadius: 16,
        padding: 4,
        width: 240,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "baseline",
          gap: 4,
          marginBottom: 12,
        }}
      >
        <button
          type="button"
          onClick={() => setMode("hour")}
          style={{
            border: "none",
            background: "none",
            cursor: "pointer",
            fontSize: 28,
            fontWeight: 700,
            color: mode === "hour" ? t.primary : t.textMuted,
            padding: "2px 4px",
          }}
        >
          {String(hour).padStart(2, "0")}시
        </button>
        <button
          type="button"
          onClick={() => setMode("minute")}
          style={{
            border: "none",
            background: "none",
            cursor: "pointer",
            fontSize: 28,
            fontWeight: 700,
            color: mode === "minute" ? t.primary : t.textMuted,
            padding: "2px 4px",
          }}
        >
          {String(minute).padStart(2, "0")}분
        </button>
      </div>

      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label="시간 선택 시계"
      >
        <circle cx={CENTER} cy={CENTER} r={RADIUS} fill={t.primarySoft} />
        <line
          x1={CENTER}
          y1={CENTER}
          x2={handEnd.x}
          y2={handEnd.y}
          stroke={t.primary}
          strokeWidth={2}
          strokeLinecap="round"
        />
        <circle cx={CENTER} cy={CENTER} r={4} fill={t.primary} />
        <circle cx={handEnd.x} cy={handEnd.y} r={16} fill={t.primary} opacity={0.25} />

        {mode === "hour"
          ? hourNumbers.map((h) => {
              const p = pointOnCircle(h * 30, RADIUS - 20);
              const isSelected = hour === h;
              return (
                <g key={h} onClick={() => handleHourClick(h)} style={{ cursor: "pointer" }}>
                  <circle cx={p.x} cy={p.y} r={14} fill={isSelected ? t.primary : "transparent"} />
                  <text
                    x={p.x}
                    y={p.y}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={14}
                    fontWeight={isSelected ? 700 : 500}
                    fill={isSelected ? "#fff" : t.text}
                    style={{ pointerEvents: "none" }}
                  >
                    {h}
                  </text>
                </g>
              );
            })
          : minuteNumbers.map((m) => {
              const p = pointOnCircle((m / 5) * 30, RADIUS - 20);
              const isSelected = minute === m || (minute % 5 !== 0 && Math.abs(minute - m) < 3);
              return (
                <g key={m} onClick={() => handleMinuteClick(m)} style={{ cursor: "pointer" }}>
                  <circle cx={p.x} cy={p.y} r={14} fill={isSelected ? t.primary : "transparent"} />
                  <text
                    x={p.x}
                    y={p.y}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={13}
                    fontWeight={isSelected ? 700 : 500}
                    fill={isSelected ? "#fff" : t.text}
                    style={{ pointerEvents: "none" }}
                  >
                    {String(m).padStart(2, "0")}
                  </text>
                </g>
              );
            })}
      </svg>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 10 }}>
        <button
          type="button"
          onClick={onClose}
          style={{
            padding: "6px 14px",
            borderRadius: 999,
            border: "none",
            background: t.primary,
            color: "#fff",
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          확인
        </button>
      </div>
    </div>
  );
}
