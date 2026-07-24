import { useState } from "react";

import TimeInputField from "../../components/ui/TimeInputField";
import { pinkTheme as t } from "../../theme/pinkTheme";

/** "해당없음" 을 나타내는 특수값. null(미선택)과 구분한다. */
export const NONE_VALUE = "NONE";

interface Props {
  label: string;
  help: string;
  /** 프리셋 시각 목록 ("05:00" 형태). */
  options: string[];
  /** 직접입력을 처음 켰을 때 채워줄 기본 시각 ("06:30" 형태). */
  customDefault: string;
  /** 현재 선택값: null(미선택) | "NONE" | "HH:MM". */
  value: string | null;
  onChange: (value: string | null) => void;
}

/** "05:00" → "5시" (분이 0이 아니면 "5:30") */
function labelOf(time: string): string {
  const [hh, mm] = time.split(":").map(Number);
  return mm === 0 ? `${hh}시` : `${hh}:${String(mm).padStart(2, "0")}`;
}

const chipStyle = (active: boolean): React.CSSProperties => ({
  padding: "8px 12px",
  borderRadius: 10,
  fontSize: 13,
  fontWeight: active ? 700 : 500,
  cursor: "pointer",
  border: `1px solid ${active ? "transparent" : t.border}`,
  background: active ? t.primary : "#fff",
  color: active ? "#fff" : t.text,
});

export default function TimeSelectSection({
  label,
  help,
  options,
  customDefault,
  value,
  onChange,
}: Props) {
  // 저장된 값이 프리셋에도 없고 NONE/미선택도 아니면(직접 입력한 시각) 처음부터 직접입력 모드로 연다.
  const [isCustom, setIsCustom] = useState(
    value !== null && value !== NONE_VALUE && !options.includes(value),
  );

  const customTime = isCustom && value && value !== NONE_VALUE ? value : customDefault;

  return (
    <div style={{ marginBottom: 20 }}>
      <p style={{ margin: "0 0 2px", fontSize: 14, fontWeight: 700, color: t.text }}>{label}</p>
      <p style={{ margin: "0 0 8px", fontSize: 12, color: t.textMuted }}>{help}</p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => {
              setIsCustom(false);
              onChange(opt);
            }}
            style={chipStyle(!isCustom && value === opt)}
          >
            {labelOf(opt)}
          </button>
        ))}
        <button
          type="button"
          onClick={() => {
            setIsCustom(false);
            onChange(NONE_VALUE);
          }}
          style={chipStyle(value === NONE_VALUE)}
        >
          해당없음
        </button>
        <button
          type="button"
          onClick={() => {
            setIsCustom(true);
            onChange(customTime);
          }}
          style={chipStyle(isCustom)}
        >
          직접입력
        </button>
      </div>

      {isCustom && (
        <div style={{ marginTop: 12 }}>
          <TimeInputField value={customTime} onChange={onChange} />
        </div>
      )}
    </div>
  );
}
