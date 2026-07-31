import { useState } from "react";

import { pushApi, type PushSourceType } from "../../../api/pushApi";
import { pinkTheme as t } from "../../../theme/pinkTheme";

export interface SnoozeItem {
  source_type: PushSourceType;
  source_id: number;
  alarm_time: string;
  name: string;
}

interface Props {
  profileId: number;
  items: SnoozeItem[];
  onClose: () => void;
}

type DoneState = "taken" | "snoozed" | "reduced" | null;

const buttonBase: React.CSSProperties = {
  border: "none",
  borderRadius: 10,
  cursor: "pointer",
  fontFamily: "inherit",
};

/** 알림 본문(액션 버튼이 아닌 부분)을 탭했을 때 여는 인앱 바텀시트(F-NTFY-3). 푸시 알림
 * 자체의 액션 버튼(복용완료/빈도줄이기)은 2개로 유지하되(3개면 일부 기기에서 잘림), 화면
 * 여유가 있는 여기서만 "30분/1시간 후에" 스누즈를 추가로 제공한다. 같은 시각에 여러 약이
 * 묶여 있으면(F-NTFY-2) 버튼 하나가 items 전체에 적용된다(기존 액션 버튼과 동일한 방식). */
export default function SnoozeSheet({ profileId, items, onClose }: Props) {
  const [pending, setPending] = useState<DoneState>(null);
  const [done, setDone] = useState<DoneState>(null);
  const [error, setError] = useState<string | null>(null);

  async function runForAll(
    kind: NonNullable<DoneState>,
    fn: (item: SnoozeItem) => Promise<unknown>,
  ) {
    setPending(kind);
    setError(null);
    try {
      await Promise.all(items.map(fn));
      setDone(kind);
      setTimeout(onClose, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "처리 중 오류가 발생했습니다.");
    } finally {
      setPending(null);
    }
  }

  const names = items.map((item) => item.name).join(", ");
  const disabled = pending !== null || done !== null;

  return (
    <div style={{ background: t.cardBg, borderRadius: 16, padding: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <span
          aria-hidden
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: t.primarySoft,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 20,
            flexShrink: 0,
          }}
        >
          💊
        </span>
        <div>
          <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: t.text }}>{names}</p>
          <p style={{ margin: "2px 0 0", fontSize: 13, color: t.textMuted }}>
            {items[0]?.alarm_time} 복용할 시간이에요
          </p>
        </div>
      </div>

      {done ? (
        <p
          style={{
            textAlign: "center",
            color: t.success,
            fontWeight: 700,
            padding: "16px 0",
            margin: 0,
          }}
        >
          {done === "taken" && "복용완료로 기록했어요!"}
          {done === "snoozed" && "잠시 후 다시 알려드릴게요."}
          {done === "reduced" && "알림 빈도를 줄였어요."}
        </p>
      ) : (
        <>
          <button
            type="button"
            disabled={disabled}
            onClick={() =>
              runForAll("taken", (item) =>
                pushApi.markTaken(profileId, item.source_type, item.source_id, item.alarm_time),
              )
            }
            style={{
              ...buttonBase,
              width: "100%",
              padding: "13px 0",
              background: t.primary,
              color: "#fff",
              fontSize: 14,
              fontWeight: 700,
              marginBottom: 10,
            }}
          >
            {pending === "taken" ? "처리 중..." : "복용완료"}
          </button>

          <p style={{ margin: "0 0 8px", fontSize: 12, color: t.textMuted, textAlign: "center" }}>
            지금 먹기 어려우면 미룰 수 있어요
          </p>
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                runForAll("snoozed", (item) =>
                  pushApi.snooze(
                    profileId,
                    item.source_type,
                    item.source_id,
                    item.name,
                    item.alarm_time,
                    30,
                  ),
                )
              }
              style={{
                ...buttonBase,
                flex: 1,
                padding: "11px 0",
                border: `1px solid ${t.border}`,
                background: t.cardBg,
                color: t.text,
                fontSize: 13.5,
              }}
            >
              {pending === "snoozed" ? "처리 중..." : "30분 후에"}
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                runForAll("snoozed", (item) =>
                  pushApi.snooze(
                    profileId,
                    item.source_type,
                    item.source_id,
                    item.name,
                    item.alarm_time,
                    60,
                  ),
                )
              }
              style={{
                ...buttonBase,
                flex: 1,
                padding: "11px 0",
                border: `1px solid ${t.border}`,
                background: t.cardBg,
                color: t.text,
                fontSize: 13.5,
              }}
            >
              {pending === "snoozed" ? "처리 중..." : "1시간 후에"}
            </button>
          </div>

          <button
            type="button"
            disabled={disabled}
            onClick={() =>
              runForAll("reduced", (item) =>
                pushApi.reduceFrequency(
                  profileId,
                  item.source_type,
                  item.source_id,
                  item.alarm_time,
                ),
              )
            }
            style={{
              ...buttonBase,
              width: "100%",
              padding: "11px 0",
              background: "transparent",
              color: t.textMuted,
              fontSize: 13,
            }}
          >
            {pending === "reduced" ? "처리 중..." : "이 알림 빈도 줄이기"}
          </button>

          {error && (
            <p style={{ color: t.danger, fontSize: 12.5, textAlign: "center", marginTop: 8 }}>
              {error}
            </p>
          )}
        </>
      )}
    </div>
  );
}
