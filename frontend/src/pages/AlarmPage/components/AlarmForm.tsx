import { useState } from "react";

import type { DayOfWeek, FrequencyType, NotificationScheduleResult } from "../../../api/types";
import TimeInputField from "../../../components/ui/TimeInputField";
import { pinkTheme as t } from "../../../theme/pinkTheme";

const DAYS: DayOfWeek[] = ["일", "월", "화", "수", "목", "금", "토"];

/** 하루 복용 횟수 선택지. */
const DOSE_OPTIONS = [
  { count: 1, label: "1회" },
  { count: 2, label: "2회" },
  { count: 3, label: "3회" },
] as const;

/** 횟수를 바꿨을 때 시간칸에 채워줄 기본 시각 (아침/저녁, 아침/점심/저녁). */
const DOSE_TIME_PRESETS: Record<number, string[]> = {
  1: ["08:00"],
  2: ["08:00", "20:00"],
  3: ["08:00", "13:00", "19:00"],
};

/** 폼이 부모(AlarmPage)에 넘겨주는 값. 하루 여러 번이면 alarm_times가 여러 개다. */
export interface AlarmFormSubmit {
  medication_name: string;
  frequency_type: FrequencyType;
  target_day_of_week: DayOfWeek | null;
  alarm_times: string[];
}

interface Props {
  initial?: NotificationScheduleResult;
  // 약품검색 결과에서 "복약알림 등록"으로 넘어올 때 약 이름만 미리 채워준다 (수정 모드 아님).
  initialMedicationName?: string;
  isSaving: boolean;
  errorMessage?: string;
  onCancel: () => void;
  onSubmit: (data: AlarmFormSubmit) => void;
}

export default function AlarmForm({
  initial,
  initialMedicationName,
  isSaving,
  errorMessage,
  onCancel,
  onSubmit,
}: Props) {
  // 수정 모드는 알림(=시각) 하나를 고치는 것이므로 횟수 선택 없이 시간칸 1개만 보여준다.
  const isEdit = initial !== undefined;

  const [medicationName, setMedicationName] = useState(
    initial?.medication_name ?? initialMedicationName ?? "",
  );
  const [doseCount, setDoseCount] = useState(1);
  const [times, setTimes] = useState<string[]>([(initial?.alarm_time ?? "08:00").slice(0, 5)]);
  const [frequencyType, setFrequencyType] = useState<FrequencyType>(
    initial?.frequency_type ?? "DAILY",
  );
  const [targetDay, setTargetDay] = useState<DayOfWeek>(initial?.target_day_of_week ?? "월");

  const canSave = medicationName.trim().length > 0;

  const handleDoseCountChange = (count: number) => {
    setDoseCount(count);
    // 이미 입력한 시각은 유지하고, 늘어난 칸만 기본 시각으로 채운다.
    setTimes((prev) =>
      Array.from({ length: count }, (_, i) => prev[i] ?? DOSE_TIME_PRESETS[count][i]),
    );
  };

  const updateTime = (index: number, newValue: string) => {
    setTimes((prev) => prev.map((tp, i) => (i === index ? newValue : tp)));
  };

  const handleSubmit = () => {
    if (!canSave) return;
    // 같은 시각을 두 번 입력했으면 하나로 합친다 — 중복 알림 방지.
    const alarmTimes = [...new Set(times.map((time) => `${time}:00`))];
    onSubmit({
      medication_name: medicationName.trim(),
      frequency_type: frequencyType,
      target_day_of_week: frequencyType === "WEEKLY" ? targetDay : null,
      alarm_times: alarmTimes,
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

      {!isEdit && (
        <>
          <label style={{ display: "block", fontSize: 13, color: t.textMuted, marginBottom: 6 }}>
            하루 복용 횟수
          </label>
          <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
            {DOSE_OPTIONS.map((opt) => (
              <button
                key={opt.count}
                type="button"
                onClick={() => handleDoseCountChange(opt.count)}
                style={{
                  padding: "8px 14px",
                  borderRadius: 999,
                  border: `1px solid ${t.border}`,
                  background: doseCount === opt.count ? t.primary : "white",
                  color: doseCount === opt.count ? "white" : t.text,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </>
      )}

      <label style={{ display: "block", fontSize: 13, color: t.textMuted, marginBottom: 4 }}>
        복용 시각
      </label>
      {times.map((time, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          {times.length > 1 && (
            <span style={{ fontSize: 12, color: t.textMuted, width: 34, flexShrink: 0 }}>
              {i + 1}회차
            </span>
          )}
          <TimeInputField value={time} onChange={(v) => updateTime(i, v)} />
        </div>
      ))}

      <label style={{ display: "block", fontSize: 13, color: t.textMuted, margin: "14px 0 6px" }}>
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
