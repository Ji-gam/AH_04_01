import { useState } from "react";

import { alarmTheme as t } from "../theme";

interface TimeParts {
  period: "오전" | "오후";
  hour: number;
  minute: number;
}

function parseTime(time: string): TimeParts {
  const [hh, mm] = time.split(":").map(Number);
  return { period: hh < 12 ? "오전" : "오후", hour: hh % 12 === 0 ? 12 : hh % 12, minute: mm };
}

function toTimeString(tp: TimeParts): string {
  let h = tp.hour % 12;
  if (tp.period === "오후") h += 12;
  return `${String(h).padStart(2, "0")}:${String(tp.minute).padStart(2, "0")}:00`;
}

interface Props {
  medName: string;
  initialTime: string; // "HH:MM(:SS)"
  isSaving: boolean;
  errorMessage?: string;
  onCancel: () => void;
  onSubmit: (newTime: string) => void; // "HH:MM:SS"
}

/** 복약 관리에서 등록한 약의 복용 시각을 알림 추가 폼과 동일한 UI로 수정한다. */
export default function MedTimeForm({
  medName,
  initialTime,
  isSaving,
  errorMessage,
  onCancel,
  onSubmit,
}: Props) {
  const initial = parseTime(initialTime);
  const [period, setPeriod] = useState<"오전" | "오후">(initial.period);
  const [hour, setHour] = useState(initial.hour);
  const [minute, setMinute] = useState(initial.minute);

  return (
    <div
      style={{
        background: t.cardBg,
        border: `1px solid ${t.border}`,
        borderRadius: 16,
        padding: 20,
        marginBottom: 16,
        boxShadow: "0 4px 14px rgba(255, 111, 145, 0.12)",
      }}
    >
      <p style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 700, color: t.text }}>
        💊 {medName}
      </p>
      <p style={{ margin: "0 0 14px", fontSize: 12, color: t.textMuted }}>
        복약 관리에서 등록한 약이라 여기서는 복용 시각만 바꿀 수 있어요.
      </p>

      <label style={{ display: "block", fontSize: 13, color: t.textMuted, marginBottom: 4 }}>
        복용 시각
      </label>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        {(["오전", "오후"] as const).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setPeriod(p)}
            style={{
              padding: "8px 14px",
              borderRadius: 999,
              border: `1px solid ${t.border}`,
              background: period === p ? t.primary : "white",
              color: period === p ? "white" : t.text,
              fontSize: 13,
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
          value={hour}
          onChange={(e) => setHour(Math.min(12, Math.max(1, Number(e.target.value) || 1)))}
          aria-label="시"
          style={{
            width: 56,
            padding: "10px 8px",
            borderRadius: 10,
            border: `1px solid ${t.border}`,
            outline: "none",
            fontSize: 14,
            textAlign: "center",
          }}
        />
        <span style={{ color: t.textMuted }}>:</span>
        <input
          type="number"
          min={0}
          max={59}
          value={minute}
          onChange={(e) => setMinute(Math.min(59, Math.max(0, Number(e.target.value) || 0)))}
          aria-label="분"
          style={{
            width: 56,
            padding: "10px 8px",
            borderRadius: 10,
            border: `1px solid ${t.border}`,
            outline: "none",
            fontSize: 14,
            textAlign: "center",
          }}
        />
      </div>

      {errorMessage && (
        <p style={{ color: t.danger, fontSize: 13, marginBottom: 10 }}>⚠ {errorMessage}</p>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button
          type="button"
          onClick={() => onSubmit(toTimeString({ period, hour, minute }))}
          disabled={isSaving}
          style={{
            flex: 1,
            padding: "12px 0",
            borderRadius: 10,
            border: "none",
            background: t.primary,
            color: "white",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {isSaving ? "저장 중..." : "저장하기"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          style={{
            padding: "12px 18px",
            borderRadius: 10,
            border: `1px solid ${t.border}`,
            background: "white",
            color: t.textMuted,
            cursor: "pointer",
          }}
        >
          취소
        </button>
      </div>
    </div>
  );
}
