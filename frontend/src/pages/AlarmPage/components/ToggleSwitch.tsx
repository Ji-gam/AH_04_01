import { pinkTheme as t } from "../../../theme/pinkTheme";

interface Props {
  checked: boolean;
  onChange: () => void;
  ariaLabel: string;
}

/** 체크박스 대신 쓰는 on/off 스위치. 알림 켜기/끄기 전용 UI라 role="switch"로 표시한다. */
export default function ToggleSwitch({ checked, onChange, ariaLabel }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={onChange}
      style={{
        width: 36,
        height: 20,
        borderRadius: 999,
        border: "none",
        padding: 2,
        background: checked ? t.primary : t.border,
        cursor: "pointer",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: checked ? "flex-end" : "flex-start",
        transition: "background 0.15s ease",
      }}
    >
      <span
        style={{
          width: 16,
          height: 16,
          borderRadius: "50%",
          background: "white",
          boxShadow: "0 1px 3px rgba(0, 0, 0, 0.2)",
        }}
      />
    </button>
  );
}
