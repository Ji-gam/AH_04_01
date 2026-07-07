import { useState } from "react";

import type {
  DayOfWeek,
  FrequencyType,
  NotificationScheduleResult,
  NotificationScheduleUpdateRequest,
} from "../../../api/types";
import { alarmTheme as t } from "../theme";

const DAYS: DayOfWeek[] = ["일", "월", "화", "수", "목", "금", "토"];

/** "HH:MM(:SS)" 24시간 문자열 → 오전/오후 + 12시간제 시/분 */
function parseAlarmTime(alarmTime: string): {
  period: "오전" | "오후";
  hour: number;
  minute: number;
} {
  const [hh, mm] = alarmTime.split(":").map(Number);
  return { period: hh < 12 ? "오전" : "오후", hour: hh % 12 === 0 ? 12 : hh % 12, minute: mm };
}

interface Props {
  initial?: NotificationScheduleResult;
  isSaving: boolean;
  errorMessage?: string;
  onCancel: () => void;
  onSubmit: (data: NotificationScheduleUpdateRequest) => void;
}

export default function AlarmForm({ initial, isSaving, errorMessage, onCancel, onSubmit }: Props) {
  const initialTime = parseAlarmTime(initial?.alarm_time ?? "08:00");
  const [medicationName, setMedicationName] = useState(initial?.medication_name ?? "");
  const [period, setPeriod] = useState<"오전" | "오후">(initialTime.period);
  const [hour, setHour] = useState(initialTime.hour);
  const [minute, setMinute] = useState(initialTime.minute);
  const [frequencyType, setFrequencyType] = useState<FrequencyType>(
    initial?.frequency_type ?? "DAILY",
  );
  const [targetDay, setTargetDay] = useState<DayOfWeek>(initial?.target_day_of_week ?? "월");

  const canSave = medicationName.trim().length > 0;

  const handleSubmit = () => {
    if (!canSave) return;
    let h = hour % 12;
    if (period === "오후") h += 12;
    onSubmit({
      medication_name: medicationName.trim(),
      frequency_type: frequencyType,
      target_day_of_week: frequencyType === "WEEKLY" ? targetDay : null,
      alarm_time: `${String(h).padStart(2, "0")}:${String(minute).padStart(2, "0")}:00`,
    });
  };

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
      <label style={{ display: "block", fontSize: 13, color: t.textMuted, marginBottom: 4 }}>
        약 이름
      </label>
      <input
        value={medicationName}
        onChange={(e) => setMedicationName(e.target.value)}
        placeholder="예: 타이레놀"
        style={{
          width: "100%",
          boxSizing: "border-box",
          padding: "10px 12px",
          marginBottom: 14,
          borderRadius: 10,
          border: `1px solid ${t.border}`,
          outline: "none",
          fontSize: 14,
        }}
      />

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

      <label style={{ display: "block", fontSize: 13, color: t.textMuted, marginBottom: 6 }}>
        반복
      </label>
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {(["DAILY", "WEEKLY"] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFrequencyType(f)}
            style={{
              padding: "8px 14px",
              borderRadius: 999,
              border: `1px solid ${t.border}`,
              background: frequencyType === f ? t.primary : "white",
              color: frequencyType === f ? "white" : t.text,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            {f === "DAILY" ? "매일" : "특정 요일"}
          </button>
        ))}
      </div>

      {frequencyType === "WEEKLY" && (
        <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
          {DAYS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setTargetDay(d)}
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                border: `1px solid ${t.border}`,
                background: targetDay === d ? t.primary : "white",
                color: targetDay === d ? "white" : t.text,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              {d}
            </button>
          ))}
        </div>
      )}

      {errorMessage && (
        <p style={{ color: t.danger, fontSize: 13, marginBottom: 10 }}>⚠ {errorMessage}</p>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSave || isSaving}
          style={{
            flex: 1,
            padding: "12px 0",
            borderRadius: 10,
            border: "none",
            background: canSave ? t.primary : t.primarySoft,
            color: canSave ? "white" : t.textMuted,
            fontWeight: 600,
            cursor: canSave ? "pointer" : "not-allowed",
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
