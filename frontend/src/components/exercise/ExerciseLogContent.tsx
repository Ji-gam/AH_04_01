import { useEffect, useState } from "react";

import { exerciseApi } from "../../api/exerciseApi";
import type {
  ExerciseLogCreateRequest,
  ExerciseMetEstimateResult,
  ExerciseRecentResult,
  ExerciseSearchResultItem,
  ExerciseTodayResult,
} from "../../api/types";
import { pinkTheme as t } from "../../theme/pinkTheme";

// 드롭다운 23개 고정 목록에 없는 운동을 자유 입력하기 위한 특수 옵션 값(2026-08-03 피드백:
// 기타 → 입력칸 → AI 인식 → 칼로리 계산).
const CUSTOM_OPTION = "__custom__";
const MAX_CUSTOM_EXERCISE_NAME_LENGTH = 50;

const DURATION_PRESETS = [10, 20, 30, 60];
const MAX_CUSTOM_MINUTES = 600;
const MAX_SPEED_KMH = 50;
const MAX_COUNT = 100000;
const JUMP_ROPE_REPS_PER_MINUTE = 100;
// 미리보기용 가정 체중 - 백엔드 exercise_service.py의 DEFAULT_WEIGHT_KG 폴백과 동일하게 맞춘다.
// 실제 기록 시엔 서버가 프로필 체중(있으면)으로 정확히 재계산하므로, 여기 숫자는 "예상치"일 뿐이다.
const PREVIEW_WEIGHT_KG = 60;

function parseCustomMinutes(raw: string): number | null {
  const value = Number(raw);
  if (!raw.trim() || Number.isNaN(value) || value <= 0 || value > MAX_CUSTOM_MINUTES) return null;
  return value;
}

function parsePositiveNumber(raw: string, max: number): number | null {
  const value = Number(raw);
  if (!raw.trim() || Number.isNaN(value) || value <= 0 || value > max) return null;
  return value;
}

/** 백엔드 exercise_service.py의 _met_from_speed()와 같은 ACSM 근사식 - 미리보기 계산용.
 * 실제 기록 값은 서버가 다시 계산하므로, 여기 결과와 완전히 같을 필요는 없고 "대략 이 정도"만
 * 보여주면 된다. */
function computeSpeedMet(exerciseName: string, speedKmh: number): number {
  const metersPerMin = speedKmh * 16.6667;
  const vo2 = exerciseName.includes("걷기") ? 0.1 * metersPerMin + 3.5 : 0.2 * metersPerMin + 3.5;
  return vo2 / 3.5;
}

const cardStyle: React.CSSProperties = {
  background: t.cardBg,
  border: `1px solid ${t.border}`,
  borderRadius: 16,
  padding: 16,
  marginBottom: 14,
  boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
};

const inputStyle = (invalid: boolean): React.CSSProperties => ({
  width: "100%",
  boxSizing: "border-box",
  padding: "8px 10px",
  marginBottom: 8,
  border: `1.5px solid ${invalid ? t.danger : t.border}`,
  borderRadius: 10,
  fontSize: 13,
  outline: "none",
});

function formatDay(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00`);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

/** 마이다이어리 > "오늘의 운동 기록" 모달 본문. 웨이트/근력운동처럼 세부 종목별 입력까지는
 * 다루지 않는 고정된 23개 운동 목록이라(2026-08-03 피드백), 자유 검색 대신 드롭다운에서 하나를
 * 고르면 그 종류(input_mode)에 맞는 입력 UI가 바로 아래에 뜬다:
 * - duration(대부분의 운동): 시간(분)만 입력, MET은 목록의 고정값 사용
 * - speed(달리기/걷기): 속도(km/h) + 시간(분) 입력 → 거리는 자동계산, MET은 속도로 실시간 계산
 * - count(줄넘기): 횟수만 입력 → 분당 100회 가정으로 시간 환산
 * 목표 대비 게이지는 없음 - 오늘 총 시간/소모 칼로리만 보여준다. */
export default function ExerciseLogContent() {
  const [today, setToday] = useState<ExerciseTodayResult | null>(null);
  const [recent, setRecent] = useState<ExerciseRecentResult | null>(null);
  const [loadingInitial, setLoadingInitial] = useState(true);

  const [catalog, setCatalog] = useState<ExerciseSearchResultItem[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState("");
  const [duration, setDuration] = useState(30);
  const [customMode, setCustomMode] = useState(false);
  const [customText, setCustomText] = useState("");
  const [speedText, setSpeedText] = useState("");
  const [countText, setCountText] = useState("");
  const [logging, setLogging] = useState(false);
  const [logError, setLogError] = useState<string | null>(null);

  // "기타(직접 입력)" 전용 상태 - 텍스트 입력 → AI 인식(estimateMet) → 그 결과(MET)로 duration
  // 모드와 동일하게 기록한다.
  const [customExerciseName, setCustomExerciseName] = useState("");
  const [customEstimate, setCustomEstimate] = useState<ExerciseMetEstimateResult | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [estimateError, setEstimateError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([exerciseApi.getToday(), exerciseApi.getRecent(), exerciseApi.getCatalog()])
      .then(([todayResult, recentResult, catalogResult]) => {
        setToday(todayResult);
        setRecent(recentResult);
        setCatalog(catalogResult.results);
      })
      .catch((err: unknown) => {
        setCatalogError(err instanceof Error ? err.message : "운동 목록을 불러오지 못했습니다.");
      })
      .finally(() => setLoadingInitial(false));
  }, []);

  async function refreshAfterMutation(todayResult: ExerciseTodayResult) {
    setToday(todayResult);
    try {
      setRecent(await exerciseApi.getRecent());
    } catch {
      // 최근 7일은 부가 정보라 실패해도 오늘 기록 자체는 이미 반영됐다.
    }
  }

  function handleSelect(name: string) {
    setSelectedName(name);
    setDuration(30);
    setCustomMode(false);
    setCustomText("");
    setSpeedText("");
    setCountText("");
    setLogError(null);
    setCustomExerciseName("");
    setCustomEstimate(null);
    setEstimateError(null);
  }

  const selectedItem = catalog.find((item) => item.exercise_name === selectedName) ?? null;
  const isCustomOption = selectedName === CUSTOM_OPTION;
  // 추정 후 텍스트를 다시 고치면(재추정 전) 낡은 MET 값으로 기록되지 않도록 이름이 일치할 때만
  // "추정 완료" 상태로 취급한다.
  const customReady =
    customEstimate !== null && customEstimate.exercise_name === customExerciseName.trim();

  async function handleEstimate() {
    const trimmed = customExerciseName.trim();
    if (!trimmed) return;
    setEstimating(true);
    setEstimateError(null);
    try {
      const result = await exerciseApi.estimateMet(trimmed);
      setCustomEstimate(result);
      setDuration(30);
    } catch (err) {
      setEstimateError(err instanceof Error ? err.message : "AI 인식 중 오류가 발생했습니다.");
    } finally {
      setEstimating(false);
    }
  }

  async function handleLog() {
    let payload: ExerciseLogCreateRequest;
    if (isCustomOption) {
      if (!customReady || customEstimate === null) return;
      payload = {
        exercise_name: customEstimate.exercise_name,
        input_mode: "duration",
        met_value: customEstimate.met_value,
        duration_minutes: duration,
      };
    } else if (selectedItem) {
      if (selectedItem.input_mode === "count") {
        const count = parsePositiveNumber(countText, MAX_COUNT);
        if (count === null) return;
        payload = { exercise_name: selectedItem.exercise_name, input_mode: "count", count };
      } else if (selectedItem.input_mode === "speed") {
        const speedKmh = parsePositiveNumber(speedText, MAX_SPEED_KMH);
        if (speedKmh === null) return;
        payload = {
          exercise_name: selectedItem.exercise_name,
          input_mode: "speed",
          speed_kmh: speedKmh,
          duration_minutes: duration,
        };
      } else {
        payload = {
          exercise_name: selectedItem.exercise_name,
          input_mode: "duration",
          met_value: selectedItem.met_value ?? undefined,
          duration_minutes: duration,
        };
      }
    } else {
      return;
    }

    setLogging(true);
    try {
      const todayResult = await exerciseApi.logExercise(payload);
      await refreshAfterMutation(todayResult);
      handleSelect("");
    } catch (err) {
      setLogError(err instanceof Error ? err.message : "기록 중 오류가 발생했습니다.");
    } finally {
      setLogging(false);
    }
  }

  async function handleDelete(logId: number) {
    try {
      const todayResult = await exerciseApi.deleteLog(logId);
      await refreshAfterMutation(todayResult);
    } catch {
      // 삭제 실패는 부가 동작이라 조용히 무시 - 목록이 그대로 남으니 다시 시도할 수 있다.
    }
  }

  const maxRecentKcal = Math.max(1, ...(recent?.days.map((d) => d.total_kcal) ?? [1]));

  return (
    <div style={cardStyle}>
      <p style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 700, color: t.primary }}>
        🏃 오늘의 운동 기록
      </p>

      {loadingInitial && <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>}

      {!loadingInitial && (
        <>
          {/* 오늘 총 운동 요약 - 식단과 달리 게이지 없이 숫자만 */}
          <div style={{ marginBottom: 16, fontSize: 13, color: t.text }}>
            <strong>오늘 총 운동 시간 {Math.round(today?.total_duration_minutes ?? 0)}분</strong>
            <span style={{ color: t.textMuted }}>
              {" "}
              · 소모 칼로리 {Math.round(today?.total_kcal ?? 0)}kcal
            </span>
          </div>

          {catalogError && <p style={{ color: t.danger, fontSize: 13 }}>{catalogError}</p>}

          {/* 운동 종류 드롭다운 - 웨이트/근력운동처럼 세부 종목별 입력은 다루지 않으므로
              자유 검색 대신 고정 목록에서 고른다. */}
          {!catalogError && (
            <select
              value={selectedName}
              onChange={(e) => handleSelect(e.target.value)}
              style={{
                width: "100%",
                boxSizing: "border-box",
                padding: "10px 12px",
                marginBottom: 12,
                border: `1px solid ${t.border}`,
                borderRadius: 10,
                fontSize: 14,
                color: selectedName ? t.text : t.textMuted,
                background: "#fff",
              }}
            >
              <option value="">운동 종류를 선택하세요</option>
              {catalog.map((item) => (
                <option key={item.exercise_name} value={item.exercise_name}>
                  {item.exercise_name}
                </option>
              ))}
              <option value={CUSTOM_OPTION}>기타 (직접 입력)</option>
            </select>
          )}

          {logError && <p style={{ color: t.danger, fontSize: 13 }}>{logError}</p>}

          {isCustomOption && (
            <div
              style={{
                border: `1.5px solid ${t.primary}`,
                borderRadius: 12,
                padding: 12,
                marginBottom: 16,
                background: t.pageBg,
              }}
            >
              <input
                type="text"
                value={customExerciseName}
                onChange={(e) => {
                  setCustomExerciseName(e.target.value.slice(0, MAX_CUSTOM_EXERCISE_NAME_LENGTH));
                  setCustomEstimate(null);
                  setEstimateError(null);
                }}
                placeholder="운동 이름 입력 (예: 클라이밍, 필라테스 기구운동)"
                style={inputStyle(false)}
              />
              {estimateError && (
                <p style={{ color: t.danger, fontSize: 12, margin: "0 0 8px" }}>{estimateError}</p>
              )}
              {!customReady && (
                <button
                  type="button"
                  onClick={handleEstimate}
                  disabled={estimating || !customExerciseName.trim()}
                  style={{
                    width: "100%",
                    padding: "8px 0",
                    borderRadius: 10,
                    border: "none",
                    background: t.primary,
                    color: "#fff",
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: estimating || !customExerciseName.trim() ? "default" : "pointer",
                    opacity: !customExerciseName.trim() ? 0.5 : 1,
                  }}
                >
                  {estimating ? "AI가 인식하는 중..." : "✨ AI로 인식하기"}
                </button>
              )}

              {customReady && customEstimate && (
                <>
                  <p style={{ margin: "0 0 8px", fontSize: 12, color: t.textMuted }}>
                    ✨ AI 인식 결과: MET {customEstimate.met_value.toFixed(1)} · 예상 소모{" "}
                    {Math.round((customEstimate.met_value * PREVIEW_WEIGHT_KG * duration) / 60)}kcal
                  </p>
                  <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                    {DURATION_PRESETS.map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setDuration(m)}
                        style={{
                          flex: 1,
                          padding: "6px 0",
                          borderRadius: 10,
                          border: `1.5px solid ${m === duration ? t.primary : t.border}`,
                          background: m === duration ? t.primarySoft : "#fff",
                          color: t.text,
                          fontSize: 12,
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        {m}분
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={handleLog}
                    disabled={logging}
                    style={{
                      width: "100%",
                      padding: "8px 0",
                      borderRadius: 10,
                      border: "none",
                      background: t.primary,
                      color: "#fff",
                      fontSize: 13,
                      fontWeight: 700,
                      cursor: logging ? "default" : "pointer",
                    }}
                  >
                    {logging ? "기록하는 중..." : "기록하기"}
                  </button>
                </>
              )}
            </div>
          )}

          {selectedItem && (
            <div
              style={{
                border: `1.5px solid ${t.primary}`,
                borderRadius: 12,
                padding: 12,
                marginBottom: 16,
                background: t.pageBg,
              }}
            >
              {selectedItem.input_mode === "count"
                ? (() => {
                    const countValue = parsePositiveNumber(countText, MAX_COUNT);
                    const invalid = countValue === null;
                    const impliedMinutes =
                      countValue !== null ? countValue / JUMP_ROPE_REPS_PER_MINUTE : 0;
                    const kcal =
                      ((selectedItem.met_value ?? 0) * PREVIEW_WEIGHT_KG * impliedMinutes) / 60;
                    return (
                      <>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            marginBottom: 8,
                          }}
                        >
                          <strong style={{ fontSize: 14, color: t.text }}>
                            {selectedItem.exercise_name}
                          </strong>
                          <span style={{ fontSize: 12, color: t.textMuted }}>
                            {countValue !== null
                              ? `${Math.round(countValue)}회 · 예상 소모 ${Math.round(kcal)}kcal`
                              : "횟수를 입력하세요"}
                          </span>
                        </div>
                        <input
                          type="number"
                          min={1}
                          max={MAX_COUNT}
                          step={1}
                          value={countText}
                          onChange={(e) => setCountText(e.target.value)}
                          placeholder="횟수 입력 (예: 300)"
                          style={inputStyle(countText !== "" && invalid)}
                        />
                        <button
                          type="button"
                          onClick={handleLog}
                          disabled={logging || invalid}
                          style={{
                            width: "100%",
                            padding: "8px 0",
                            borderRadius: 10,
                            border: "none",
                            background: t.primary,
                            color: "#fff",
                            fontSize: 13,
                            fontWeight: 700,
                            cursor: logging || invalid ? "default" : "pointer",
                            opacity: invalid ? 0.5 : 1,
                          }}
                        >
                          {logging ? "기록하는 중..." : "기록하기"}
                        </button>
                      </>
                    );
                  })()
                : (() => {
                    const isSpeedMode = selectedItem.input_mode === "speed";
                    const customValue = parseCustomMinutes(customText);
                    const customInvalid = customMode && customValue === null;
                    const speedValue = isSpeedMode
                      ? parsePositiveNumber(speedText, MAX_SPEED_KMH)
                      : null;
                    const speedInvalid = isSpeedMode && speedValue === null;
                    const met = isSpeedMode
                      ? speedValue !== null
                        ? computeSpeedMet(selectedItem.exercise_name, speedValue)
                        : 0
                      : (selectedItem.met_value ?? 0);
                    const kcal = (met * PREVIEW_WEIGHT_KG * duration) / 60;
                    const distanceKm =
                      isSpeedMode && speedValue !== null ? (speedValue * duration) / 60 : null;
                    const disabled = customInvalid || speedInvalid;
                    return (
                      <>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            marginBottom: 8,
                          }}
                        >
                          <strong style={{ fontSize: 14, color: t.text }}>
                            {selectedItem.exercise_name}
                          </strong>
                          <span style={{ fontSize: 12, color: t.textMuted }}>
                            {Math.round(duration)}분
                            {distanceKm !== null ? ` · ${distanceKm.toFixed(1)}km` : ""}
                            {!speedInvalid ? ` · 예상 소모 ${Math.round(kcal)}kcal` : ""}
                          </span>
                        </div>

                        {isSpeedMode && (
                          <input
                            type="number"
                            min={0.1}
                            max={MAX_SPEED_KMH}
                            step={0.1}
                            value={speedText}
                            onChange={(e) => setSpeedText(e.target.value)}
                            placeholder="속도(km/h) 입력 (예: 6.0)"
                            style={inputStyle(speedText !== "" && speedInvalid)}
                          />
                        )}

                        <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                          {DURATION_PRESETS.map((m) => (
                            <button
                              key={m}
                              type="button"
                              onClick={() => {
                                setDuration(m);
                                setCustomMode(false);
                              }}
                              style={{
                                flex: 1,
                                padding: "6px 0",
                                borderRadius: 10,
                                border: `1.5px solid ${!customMode && m === duration ? t.primary : t.border}`,
                                background: !customMode && m === duration ? t.primarySoft : "#fff",
                                color: t.text,
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: "pointer",
                              }}
                            >
                              {m}분
                            </button>
                          ))}
                          <button
                            type="button"
                            onClick={() => setCustomMode(true)}
                            style={{
                              flex: 1,
                              padding: "6px 0",
                              borderRadius: 10,
                              border: `1.5px solid ${customMode ? t.primary : t.border}`,
                              background: customMode ? t.primarySoft : "#fff",
                              color: t.text,
                              fontSize: 12,
                              fontWeight: 600,
                              cursor: "pointer",
                            }}
                          >
                            기타
                          </button>
                        </div>
                        {customMode && (
                          <input
                            type="number"
                            min={1}
                            max={MAX_CUSTOM_MINUTES}
                            step={1}
                            value={customText}
                            onChange={(e) => {
                              const raw = e.target.value;
                              setCustomText(raw);
                              const parsed = parseCustomMinutes(raw);
                              if (parsed !== null) {
                                setDuration(parsed);
                              }
                            }}
                            placeholder={`운동 시간(분) 직접 입력 (1~${MAX_CUSTOM_MINUTES})`}
                            style={inputStyle(customInvalid)}
                          />
                        )}
                        <button
                          type="button"
                          onClick={handleLog}
                          disabled={logging || disabled}
                          style={{
                            width: "100%",
                            padding: "8px 0",
                            borderRadius: 10,
                            border: "none",
                            background: t.primary,
                            color: "#fff",
                            fontSize: 13,
                            fontWeight: 700,
                            cursor: logging || disabled ? "default" : "pointer",
                            opacity: disabled ? 0.5 : 1,
                          }}
                        >
                          {logging ? "기록하는 중..." : "기록하기"}
                        </button>
                      </>
                    );
                  })()}
            </div>
          )}

          {/* 오늘 기록한 목록 */}
          <p style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 700, color: t.text }}>
            오늘 기록한 운동
          </p>
          {!today || today.logs.length === 0 ? (
            <p style={{ margin: "0 0 16px", fontSize: 13, color: t.textMuted }}>
              아직 기록한 운동이 없어요.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
              {today.logs.map((log) => (
                <div
                  key={log.id}
                  style={{
                    background: t.primarySoft,
                    borderRadius: 12,
                    padding: "10px 14px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <strong style={{ fontSize: 13, color: t.text }}>{log.exercise_name}</strong>
                    <div style={{ fontSize: 12, color: t.textMuted }}>
                      {log.count !== null
                        ? `${log.count}회`
                        : `${Math.round(log.duration_minutes)}분${log.distance_km !== null ? ` · ${log.distance_km.toFixed(1)}km` : ""}`}
                      {" · "}
                      {Math.round(log.calorie_kcal)}kcal
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(log.id)}
                    aria-label="기록 삭제"
                    style={{
                      border: "none",
                      background: "transparent",
                      color: t.danger,
                      fontSize: 16,
                      cursor: "pointer",
                      padding: 4,
                    }}
                  >
                    🗑
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* 최근 7일 */}
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
                    height: Math.max(4, (day.total_kcal / maxRecentKcal) * 44),
                    borderRadius: 4,
                    background: t.primary,
                  }}
                  title={`${Math.round(day.total_kcal)}kcal`}
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
