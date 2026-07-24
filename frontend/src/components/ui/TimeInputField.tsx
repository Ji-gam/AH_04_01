import { useEffect, useRef, useState } from "react";

import Modal from "../../pages/AlarmPage/components/Modal";
import { pinkTheme as t } from "../../theme/pinkTheme";

import AnalogClockPicker from "./AnalogClockPicker";

interface TimeParts {
  period: "오전" | "오후";
  hour: number;
  minute: number;
}

/** "HH:MM"(24시간, 초 없음) → 오전/오후 + 12시간제 시/분. 초가 붙은 값("HH:MM:SS")을 다루는
 * 화면은 호출부에서 초를 떼고 넣고, 저장할 때 다시 붙인다 - 이 컴포넌트는 "HH:MM"만 안다. */
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

const HOUR_OPTIONS = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTE_OPTIONS = Array.from({ length: 12 }, (_, i) => i * 5);

/** 앱 전체에서 공용으로 쓰는 시간 입력 한 줄 - 오전/오후 토글 + 시/분 칸(타이핑도, 드롭다운
 * 클릭도 가능) + 아날로그 시계 아이콘, 세 가지 입력 방식을 다 지원한다. 원래 가족관리
 * 화면(처방전 인식 후 시간대 설정) 전용으로 만들었다가(2026-07-21), 앱 안의 모든 시간
 * 입력 화면(복약알림 추가/수정, 무음시간대, 라이프스타일 설정 등)에 같은 방식을 쓰기로
 * 하면서 공용 컴포넌트로 옮겼다(2026-07-23).
 *
 * <datalist>를 써봤는데, "이미 값이 입력된 칸은 지우고 화살표를 눌러야만 목록이 뜨는"
 * 브라우저 기본 동작이 있어서(개발자가 통제 불가) 자체 제작 드롭다운으로 교체했다:
 *   - 칸에 포커스가 가면(지금 뭐가 써있든 상관없이) 항상 아래에 목록이 뜬다.
 *   - 목록 항목을 누르면 그 값으로 바로 반영되고 목록이 닫힌다.
 *   - 목록을 안 누르고 계속 타이핑도 가능하다 - 값 자체는 문자열 버퍼로 관리해서, 지우는
 *     도중(빈 문자열)엔 아직 반영 안 하고 화면에 빈 칸을 그대로 보여준다(숫자가 실제로
 *     입력됐을 때만 반영 - 예전에 "지우면 1로 튀는" 문제의 원인이었던 부분).
 *   - 목록 항목은 onMouseDown에서 처리한다 - onClick을 쓰면 그 전에 input의 onBlur가
 *     먼저 발동해서 목록이 닫혀버려 클릭이 씹히는 문제가 있다(흔한 콤보박스 구현 이슈). */
export default function TimeInputField({ value, onChange }: Props) {
  const tp = parseHHMM(value);
  const [clockOpen, setClockOpen] = useState(false);
  const [hourListOpen, setHourListOpen] = useState(false);
  const [minuteListOpen, setMinuteListOpen] = useState(false);

  const [hourText, setHourText] = useState(String(tp.hour));
  const [minuteText, setMinuteText] = useState(String(tp.minute).padStart(2, "0"));

  // "이 입력칸 자체에서 타이핑해서 생긴 변경"과 "시계 등 바깥에서 생긴 변경"을 구분해야
  // 한다 - 구분 안 하면, "3"을 입력하는 그 순간 update()가 부모 값을 바꾸고, 그걸 감지한
  // useEffect가 "03"(두 자리로 채움)으로 즉시 되돌려버려서, 그 다음 눌러야 할 두 번째
  // 숫자가 이미 두 자리라 안 들어가는 문제가 있었다(2026-07-21 확인 - "30분 넣으려고
  // 3, 0 순서로 눌러도 0이 반영 안 되는" 버그의 원인). 스스로 일으킨 변경일 때는 이
  // 플래그로 동기화를 한 번 건너뛴다.
  const skipNextHourSync = useRef(false);
  const skipNextMinuteSync = useRef(false);

  useEffect(() => {
    if (skipNextHourSync.current) {
      skipNextHourSync.current = false;
      return;
    }
    setHourText(String(tp.hour));
  }, [tp.hour]);
  useEffect(() => {
    if (skipNextMinuteSync.current) {
      skipNextMinuteSync.current = false;
      return;
    }
    setMinuteText(String(tp.minute).padStart(2, "0"));
  }, [tp.minute]);

  const update = (patch: Partial<TimeParts>) => {
    onChange(toHHMM({ ...tp, ...patch }));
  };

  function handleHourChange(raw: string) {
    const digits = raw.replace(/\D/g, "").slice(0, 2);
    setHourText(digits);
    if (digits === "") return; // 지우는 중 - 아직 반영 안 함, "1"로 안 튐
    skipNextHourSync.current = true; // 이 update()로 생기는 되돌아온 동기화는 건너뛴다
    update({ hour: Math.min(12, Math.max(1, Number(digits))) });
  }

  function handleHourBlur() {
    if (hourText === "" || Number(hourText) < 1) setHourText(String(tp.hour));
    setHourListOpen(false);
  }

  function selectHour(h: number) {
    setHourText(String(h));
    update({ hour: h });
    setHourListOpen(false);
  }

  function handleMinuteChange(raw: string) {
    const digits = raw.replace(/\D/g, "").slice(0, 2);
    setMinuteText(digits);
    if (digits === "") return;
    skipNextMinuteSync.current = true; // 이 update()로 생기는 되돌아온 동기화는 건너뛴다
    update({ minute: Math.min(59, Number(digits)) });
  }

  function handleMinuteBlur() {
    // 한 자리만 입력하고 벗어나도(예: "3"), 실제 값은 이미 반영돼있으니(3분) 표시만
    // 두 자리로 깔끔하게 정리한다.
    setMinuteText(String(tp.minute).padStart(2, "0"));
    setMinuteListOpen(false);
  }

  function selectMinute(m: number) {
    setMinuteText(String(m).padStart(2, "0"));
    update({ minute: m });
    setMinuteListOpen(false);
  }

  const dropdownStyle: React.CSSProperties = {
    position: "absolute",
    top: "100%",
    left: 0,
    marginTop: 4,
    zIndex: 30,
    background: t.cardBg,
    border: `1px solid ${t.border}`,
    borderRadius: 8,
    boxShadow: "0 6px 16px rgba(255, 111, 145, 0.2)",
    maxHeight: 160,
    overflowY: "auto",
    minWidth: 56,
  };

  const optionStyle = (isSelected: boolean): React.CSSProperties => ({
    padding: "7px 12px",
    cursor: "pointer",
    fontSize: 13,
    color: isSelected ? "#fff" : t.text,
    background: isSelected ? t.primary : "transparent",
    whiteSpace: "nowrap",
  });

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

      <div style={{ position: "relative" }}>
        <input
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          value={hourText}
          onChange={(e) => handleHourChange(e.target.value)}
          onFocus={() => setHourListOpen(true)}
          onBlur={handleHourBlur}
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
        {hourListOpen && (
          <div style={dropdownStyle}>
            {HOUR_OPTIONS.map((h) => (
              <div
                key={h}
                onMouseDown={(e) => {
                  e.preventDefault(); // input의 onBlur보다 먼저 실행되게 - 안 그러면 목록이 먼저 닫혀 클릭이 씹힌다.
                  selectHour(h);
                }}
                style={optionStyle(tp.hour === h)}
              >
                {h}시
              </div>
            ))}
          </div>
        )}
      </div>

      <span style={{ color: t.textMuted }}>:</span>

      <div style={{ position: "relative" }}>
        <input
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          value={minuteText}
          onChange={(e) => handleMinuteChange(e.target.value)}
          onFocus={() => setMinuteListOpen(true)}
          onBlur={handleMinuteBlur}
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
        {minuteListOpen && (
          <div style={dropdownStyle}>
            {MINUTE_OPTIONS.map((m) => (
              <div
                key={m}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectMinute(m);
                }}
                style={optionStyle(tp.minute === m)}
              >
                {String(m).padStart(2, "0")}분
              </div>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        aria-label="시계로 시각 선택"
        onClick={() => setClockOpen((v) => !v)}
        style={{ border: "none", background: "none", cursor: "pointer", fontSize: 16, padding: 2 }}
      >
        🕐
      </button>
      {clockOpen && (
        <Modal onClose={() => setClockOpen(false)}>
          <AnalogClockPicker
            hour={tp.hour}
            minute={tp.minute}
            period={tp.period}
            onChange={(h, m) => update({ hour: h, minute: m })}
            onPeriodChange={(p) => update({ period: p })}
            onClose={() => setClockOpen(false)}
          />
        </Modal>
      )}
    </div>
  );
}
