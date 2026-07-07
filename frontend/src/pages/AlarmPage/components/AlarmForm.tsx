import { useState } from "react";

import type {
  DayOfWeek,
  FrequencyType,
  NotificationScheduleResult,
  NotificationScheduleUpdateRequest,
} from "../../../api/types";
import { alarmTheme as t } from "../theme";

const DAYS: DayOfWeek[] = ["일", "월", "화", "수", "목", "금", "토"];

interface Props {
  initial?: NotificationScheduleResult;
  isSaving: boolean;
  errorMessage?: string;
  onCancel: () => void;
  onSubmit: (data: NotificationScheduleUpdateRequest) => void;
}

export default function AlarmForm({ initial, isSaving, errorMessage, onCancel, onSubmit }: Props) {
  const [medicationName, setMedicationName] = useState(initial?.medication_name ?? "");
  const [alarmTime, setAlarmTime] = useState(initial?.alarm_time?.slice(0, 5) ?? "08:00");
  const [frequencyType, setFrequencyType] = useState<FrequencyType>(initial?.frequency_type ?? "DAILY");
  const [targetDay, setTargetDay] = useState<DayOfWeek>(initial?.target_day_of_week ?? "월");

  const canSave = medicationName.trim().length > 0;

  const handleSubmit = () => {
    if (!canSave) return;
    onSubmit({
      medication_name: medicationName.trim(),
      frequency_type: frequencyType,
      target_day_of_week: frequencyType === "WEEKLY" ? targetDay : null,
      alarm_time: `${alarmTime}:00`,
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
      <label style={{ display: "block", fontSize: 13, color: t.textMuted, marginBottom: 4 }}>약 이름</label>
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

      <label style={{ display: "block", fontSize: 13, color: t.textMuted, marginBottom: 4 }}>복용 시각</label>
      <input
        type="time"
        value={alarmTime}
        onChange={(e) => setAlarmTime(e.target.value)}
        style={{
          padding: "10px 12px",
          marginBottom: 14,
          borderRadius: 10,
          border: `1px solid ${t.border}`,
          outline: "none",
          fontSize: 14,
        }}
      />

      <label style={{ display: "block", fontSize: 13, color: t.textMuted, marginBottom: 6 }}>반복</label>
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

      {errorMessage && <p style={{ color: t.danger, fontSize: 13, marginBottom: 10 }}>⚠ {errorMessage}</p>}

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
