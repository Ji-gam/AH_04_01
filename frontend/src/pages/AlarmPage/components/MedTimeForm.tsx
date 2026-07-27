import { useState } from "react";

import TimeInputField from "../../../components/ui/TimeInputField";
import { pinkTheme as t } from "../../../theme/pinkTheme";

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
  const [time, setTime] = useState(initialTime.slice(0, 5));

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
        <TimeInputField value={time} onChange={setTime} />
      </div>

      {errorMessage && (
        <p style={{ color: t.danger, fontSize: 13, marginBottom: 10 }}>⚠ {errorMessage}</p>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button
          type="button"
          onClick={() => onSubmit(`${time}:00`)}
          disabled={isSaving}
          style={{
            flex: 1,
            padding: "12px 0",
            borderRadius: 10,
            border: "none",
            background: t.primary,
            color: "#fff",
            fontWeight: 700,
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
            background: t.cardBg,
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
