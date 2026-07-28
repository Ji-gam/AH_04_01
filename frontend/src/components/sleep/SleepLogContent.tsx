import { useEffect, useState } from "react";

import { sleepApi } from "../../api/sleepApi";
import type { SleepRecentResult, SleepTodayResult } from "../../api/types";
import TimeInputField from "../../components/ui/TimeInputField";
import { pinkTheme as t } from "../../theme/pinkTheme";

const QUALITY_OPTIONS = [
  { value: 5, icon: "😴", label: "매우 잘\n잤음" },
  { value: 4, icon: "🙂", label: "잘 잤음" },
  { value: 3, icon: "😐", label: "보통" },
  { value: 2, icon: "😕", label: "잘 못\n잠" },
  { value: 1, icon: "😫", label: "1시간도\n못 잠" },
];

const DEFAULT_BED_TIME = "23:00";

const cardStyle: React.CSSProperties = {
  background: t.cardBg,
  border: `1px solid ${t.border}`,
  borderRadius: 16,
  padding: 16,
  marginBottom: 14,
  boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
};

function formatDay(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00`);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

/** 마이다이어리 > "오늘의 수면 기록" 모달 본문(REQ-TRCK-003). 하루 1건만 기록하고(다시
 * 저장하면 덮어씀), 취침 시각은 참고용으로만 받아 수면시간을 재계산하지 않는다. 수면의
 * 질이 2점 이하일 때만 "왜 못 잤는지" 입력칸이 나타난다. */
export default function SleepLogContent() {
  const [today, setToday] = useState<SleepTodayResult | null>(null);
  const [recent, setRecent] = useState<SleepRecentResult | null>(null);
  const [loadingInitial, setLoadingInitial] = useState(true);

  const [hours, setHours] = useState("7");
  const [bedTime, setBedTime] = useState(DEFAULT_BED_TIME);
  const [quality, setQuality] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([sleepApi.getToday(), sleepApi.getRecent()])
      .then(([todayResult, recentResult]) => {
        setToday(todayResult);
        setRecent(recentResult);
        if (todayResult.log) {
          setHours(String(todayResult.log.hours));
          setBedTime(todayResult.log.bed_time ?? DEFAULT_BED_TIME);
          setQuality(todayResult.log.quality);
          setReason(todayResult.log.reason ?? "");
        }
      })
      .finally(() => setLoadingInitial(false));
  }, []);

  async function handleSave() {
    const hoursValue = Number(hours);
    if (!hours.trim() || Number.isNaN(hoursValue) || hoursValue < 0 || hoursValue > 24) {
      setError("수면 시간을 0~24 사이 숫자로 입력해주세요.");
      return;
    }
    if (quality === null) {
      setError("수면의 질을 선택해주세요.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const todayResult = await sleepApi.logSleep({
        hours: hoursValue,
        bed_time: bedTime,
        quality,
        reason: quality <= 2 && reason.trim() ? reason.trim() : undefined,
      });
      setToday(todayResult);
      setSaved(true);
      try {
        setRecent(await sleepApi.getRecent());
      } catch {
        // 최근 7일은 부가 정보라 실패해도 오늘 기록 자체는 이미 반영됐다.
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  }

  const maxRecentHours = Math.max(1, ...(recent?.days.map((d) => d.hours) ?? [1]));

  return (
    <div style={cardStyle}>
      <p style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700, color: t.primary }}>
        😴 오늘의 수면 기록
      </p>
      <p style={{ margin: "0 0 14px", fontSize: 12.5, color: t.textMuted }}>
        어젯밤 얼마나, 어떻게 주무셨나요?
      </p>

      {loadingInitial && <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>}

      {!loadingInitial && (
        <>
          {today?.log && (
            <p style={{ margin: "0 0 12px", fontSize: 12, color: t.textMuted }}>
              오늘 이미 기록이 있어요 - 다시 저장하면 덮어써요.
            </p>
          )}

          <p style={{ margin: "0 0 6px", fontSize: 12, fontWeight: 700, color: t.text }}>
            수면 시간
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <input
              type="number"
              min={0}
              max={24}
              step={0.5}
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              style={{
                flex: 1,
                padding: "10px 12px",
                border: `1px solid ${t.border}`,
                borderRadius: 10,
                fontSize: 15,
                fontWeight: 700,
                textAlign: "center",
                color: t.text,
                outline: "none",
              }}
            />
            <span style={{ fontSize: 13, color: t.textMuted }}>시간</span>
          </div>

          <p style={{ margin: "0 0 6px", fontSize: 12, fontWeight: 700, color: t.text }}>
            취침 시각
          </p>
          <div style={{ marginBottom: 16 }}>
            <TimeInputField value={bedTime} onChange={setBedTime} />
          </div>

          <p style={{ margin: "0 0 8px", fontSize: 12, fontWeight: 700, color: t.text }}>
            수면의 질
          </p>
          <div
            style={{
              display: "flex",
              gap: 5,
              marginBottom: quality !== null && quality <= 2 ? 10 : 16,
            }}
          >
            {QUALITY_OPTIONS.map((opt) => {
              const isSelected = quality === opt.value;
              const isLow = isSelected && opt.value <= 2;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setQuality(opt.value)}
                  style={{
                    flex: 1,
                    padding: "8px 2px",
                    borderRadius: 10,
                    border: `1px solid ${isLow ? t.danger : isSelected ? t.primary : t.border}`,
                    background: isLow ? "#fdecee" : isSelected ? t.primarySoft : "#fff",
                    color: isLow ? t.danger : isSelected ? t.primaryHover : t.textMuted,
                    fontSize: 10.5,
                    fontWeight: 700,
                    textAlign: "center",
                    whiteSpace: "pre-line",
                    lineHeight: 1.3,
                    cursor: "pointer",
                  }}
                >
                  <span style={{ display: "block", fontSize: 15, marginBottom: 2 }}>
                    {opt.icon}
                  </span>
                  {opt.label}
                </button>
              );
            })}
          </div>

          {quality !== null && quality <= 2 && (
            <div style={{ marginBottom: 16 }}>
              <p style={{ margin: "0 0 6px", fontSize: 12, fontWeight: 700, color: t.danger }}>
                무엇 때문에 잘 못 주무셨나요? (선택)
              </p>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                placeholder="예: 스트레스, 카페인, 소음 때문에 뒤척였어요"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "10px 12px",
                  border: `1px solid ${t.border}`,
                  borderRadius: 10,
                  fontSize: 12.5,
                  color: t.text,
                  resize: "none",
                  fontFamily: "inherit",
                  outline: "none",
                }}
              />
            </div>
          )}

          {error && <p style={{ color: t.danger, fontSize: 13, marginBottom: 12 }}>{error}</p>}

          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            style={{
              width: "100%",
              padding: "11px 0",
              border: "none",
              borderRadius: 10,
              background: t.primary,
              color: "#fff",
              fontSize: 13.5,
              fontWeight: 700,
              cursor: saving ? "default" : "pointer",
              marginBottom: 20,
            }}
          >
            {saving ? "저장하는 중..." : saved ? "저장 완료 - 다시 저장하기" : "저장하기"}
          </button>

          <p style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 700, color: t.text }}>
            최근 7일
          </p>
          <div style={{ display: "flex", gap: 6, alignItems: "flex-end", height: 70 }}>
            {(recent?.days ?? []).map((day) => (
              <div
                key={day.log_date}
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <div
                  style={{
                    width: "100%",
                    height: Math.max(4, (day.hours / maxRecentHours) * 44),
                    borderRadius: 4,
                    background: t.primary,
                  }}
                  title={`${day.hours}시간`}
                />
                <span style={{ fontSize: 10, color: t.textMuted }}>{formatDay(day.log_date)}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
