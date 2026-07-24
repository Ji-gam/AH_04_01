import { useEffect, useState } from "react";

import { exerciseApi } from "../../api/exerciseApi";
import type { ExerciseLogCreateRequest, ExerciseRecentResult, ExerciseSearchResultItem, ExerciseTodayResult } from "../../api/types";
import { pinkTheme as t } from "../../theme/pinkTheme";

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
  borderRadius: 8,
  fontSize: 13,
  outline: "none",
});

function formatDay(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00`);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

/** 마이다이어리 > "오늘의 운동 기록" 모달 본문. `DietLogContent.tsx`와 같은 구조(검색→선택→
 * 기록→오늘 요약→최근 7일)를 따르되, 운동 종류(input_mode)에 따라 입력 방식이 갈린다:
 * - duration(대부분의 운동): 시간(분)만 입력, MET은 검색 결과의 고정값 사용
 * - speed(달리기/걷기): 속도(km/h) + 시간(분) 입력 → 거리는 자동계산, MET은 속도로 실시간 계산
 * - count(줄넘기): 횟수만 입력 → 분당 100회 가정으로 시간 환산
 * 목표 대비 게이지는 없음 - 오늘 총 시간/소모 칼로리만 보여준다. */
export default function ExerciseLogContent() {
  const [today, setToday] = useState<ExerciseTodayResult | null>(null);
  const [recent, setRecent] = useState<ExerciseRecentResult | null>(null);
  const [loadingInitial, setLoadingInitial] = useState(true);

  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ExerciseSearchResultItem[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [durations, setDurations] = useState<Record<string, number>>({});
  const [customMode, setCustomMode] = useState<Record<string, boolean>>({});
  const [customText, setCustomText] = useState<Record<string, string>>({});
  const [speedText, setSpeedText] = useState<Record<string, string>>({});
  const [countText, setCountText] = useState<Record<string, string>>({});
  const [loggingExerciseName, setLoggingExerciseName] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([exerciseApi.getToday(), exerciseApi.getRecent()])
      .then(([todayResult, recentResult]) => {
        setToday(todayResult);
        setRecent(recentResult);
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

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearchLoading(true);
    setSearchError(null);
    try {
      const result = await exerciseApi.searchExercise(query.trim());
      setSearchResults(result.results);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "검색 중 오류가 발생했습니다.");
      setSearchResults([]);
    } finally {
      setHasSearched(true);
      setSearchLoading(false);
    }
  }

  async function handleLog(item: ExerciseSearchResultItem) {
    let payload: ExerciseLogCreateRequest;
    if (item.input_mode === "count") {
      const count = parsePositiveNumber(countText[item.exercise_name] ?? "", MAX_COUNT);
      if (count === null) return;
      payload = { exercise_name: item.exercise_name, input_mode: "count", count };
    } else if (item.input_mode === "speed") {
      const speedKmh = parsePositiveNumber(speedText[item.exercise_name] ?? "", MAX_SPEED_KMH);
      if (speedKmh === null) return;
      const duration = durations[item.exercise_name] ?? 30;
      payload = { exercise_name: item.exercise_name, input_mode: "speed", speed_kmh: speedKmh, duration_minutes: duration };
    } else {
      const duration = durations[item.exercise_name] ?? 30;
      payload = {
        exercise_name: item.exercise_name,
        input_mode: "duration",
        met_value: item.met_value ?? undefined,
        duration_minutes: duration,
      };
    }

    setLoggingExerciseName(item.exercise_name);
    try {
      const todayResult = await exerciseApi.logExercise(payload);
      await refreshAfterMutation(todayResult);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "기록 중 오류가 발생했습니다.");
    } finally {
      setLoggingExerciseName(null);
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
      <p style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 700, color: t.primary }}>🏃 오늘의 운동 기록</p>

      {loadingInitial && <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>}

      {!loadingInitial && (
        <>
          {/* 오늘 총 운동 요약 - 식단과 달리 게이지 없이 숫자만 */}
          <div style={{ marginBottom: 16, fontSize: 13, color: t.text }}>
            <strong>오늘 총 운동 시간 {Math.round(today?.total_duration_minutes ?? 0)}분</strong>
            <span style={{ color: t.textMuted }}> · 소모 칼로리 {Math.round(today?.total_kcal ?? 0)}kcal</span>
          </div>

          {/* 운동 검색 */}
          <form onSubmit={handleSearch} style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="운동 이름 입력 (예: 달리기, 걷기, 줄넘기)"
              style={{
                flex: 1,
                padding: "10px 12px",
                border: `1px solid ${t.border}`,
                borderRadius: 10,
                fontSize: 14,
                outline: "none",
              }}
            />
            <button
              type="submit"
              disabled={searchLoading}
              style={{
                padding: "10px 16px",
                border: "none",
                borderRadius: 10,
                background: t.primary,
                color: "#fff",
                fontWeight: 600,
                cursor: searchLoading ? "default" : "pointer",
              }}
            >
              검색
            </button>
          </form>

          {searchLoading && <p style={{ color: t.textMuted, fontSize: 13 }}>검색 중...</p>}
          {searchError && <p style={{ color: t.danger, fontSize: 13 }}>{searchError}</p>}
          {!searchLoading && !searchError && hasSearched && searchResults.length === 0 && (
            <p style={{ color: t.textMuted, fontSize: 13, marginBottom: 16 }}>
              검색 결과가 없어요. 다른 이름으로 검색해보세요(예: 달리기, 걷기, 줄넘기).
            </p>
          )}

          {searchResults.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
              {searchResults.map((item) => {
                // count 모드(줄넘기): 횟수 입력만 있고 시간/속도 개념이 없다.
                if (item.input_mode === "count") {
                  const countValue = parsePositiveNumber(countText[item.exercise_name] ?? "", MAX_COUNT);
                  const invalid = countValue === null;
                  const impliedMinutes = countValue !== null ? countValue / JUMP_ROPE_REPS_PER_MINUTE : 0;
                  const kcal = ((item.met_value ?? 0) * PREVIEW_WEIGHT_KG * impliedMinutes) / 60;
                  return (
                    <div
                      key={item.exercise_name}
                      style={{ border: `1px solid ${t.border}`, borderRadius: 12, padding: 12, background: t.pageBg }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                        <strong style={{ fontSize: 14, color: t.text }}>{item.exercise_name}</strong>
                        <span style={{ fontSize: 12, color: t.textMuted }}>
                          {countValue !== null ? `${Math.round(countValue)}회 · 예상 소모 ${Math.round(kcal)}kcal` : "횟수를 입력하세요"}
                        </span>
                      </div>
                      <input
                        type="number"
                        min={1}
                        max={MAX_COUNT}
                        step={1}
                        value={countText[item.exercise_name] ?? ""}
                        onChange={(e) => setCountText((prev) => ({ ...prev, [item.exercise_name]: e.target.value }))}
                        placeholder="횟수 입력 (예: 300)"
                        style={inputStyle(countText[item.exercise_name] !== undefined && invalid)}
                      />
                      <button
                        type="button"
                        onClick={() => handleLog(item)}
                        disabled={loggingExerciseName === item.exercise_name || invalid}
                        style={{
                          width: "100%",
                          padding: "8px 0",
                          borderRadius: 8,
                          border: "none",
                          background: t.primary,
                          color: "#fff",
                          fontSize: 13,
                          fontWeight: 700,
                          cursor: loggingExerciseName === item.exercise_name || invalid ? "default" : "pointer",
                          opacity: invalid ? 0.5 : 1,
                        }}
                      >
                        {loggingExerciseName === item.exercise_name ? "기록하는 중..." : "기록하기"}
                      </button>
                    </div>
                  );
                }

                const isSpeedMode = item.input_mode === "speed";
                const duration = durations[item.exercise_name] ?? 30;
                const isOther = customMode[item.exercise_name] ?? false;
                const customValue = parseCustomMinutes(customText[item.exercise_name] ?? "");
                const customInvalid = isOther && customValue === null;

                const speedValue = isSpeedMode ? parsePositiveNumber(speedText[item.exercise_name] ?? "", MAX_SPEED_KMH) : null;
                const speedInvalid = isSpeedMode && speedValue === null;

                const met = isSpeedMode ? (speedValue !== null ? computeSpeedMet(item.exercise_name, speedValue) : 0) : item.met_value ?? 0;
                const kcal = (met * PREVIEW_WEIGHT_KG * duration) / 60;
                const distanceKm = isSpeedMode && speedValue !== null ? (speedValue * duration) / 60 : null;
                const disabled = customInvalid || speedInvalid;

                return (
                  <div
                    key={item.exercise_name}
                    style={{ border: `1px solid ${t.border}`, borderRadius: 12, padding: 12, background: t.pageBg }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                      <strong style={{ fontSize: 14, color: t.text }}>{item.exercise_name}</strong>
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
                        value={speedText[item.exercise_name] ?? ""}
                        onChange={(e) => setSpeedText((prev) => ({ ...prev, [item.exercise_name]: e.target.value }))}
                        placeholder="속도(km/h) 입력 (예: 6.0)"
                        style={inputStyle(speedText[item.exercise_name] !== undefined && speedInvalid)}
                      />
                    )}

                    <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                      {DURATION_PRESETS.map((m) => (
                        <button
                          key={m}
                          type="button"
                          onClick={() => {
                            setDurations((prev) => ({ ...prev, [item.exercise_name]: m }));
                            setCustomMode((prev) => ({ ...prev, [item.exercise_name]: false }));
                          }}
                          style={{
                            flex: 1,
                            padding: "6px 0",
                            borderRadius: 8,
                            border: `1.5px solid ${!isOther && m === duration ? t.primary : t.border}`,
                            background: !isOther && m === duration ? t.primarySoft : "#fff",
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
                        onClick={() => setCustomMode((prev) => ({ ...prev, [item.exercise_name]: true }))}
                        style={{
                          flex: 1,
                          padding: "6px 0",
                          borderRadius: 8,
                          border: `1.5px solid ${isOther ? t.primary : t.border}`,
                          background: isOther ? t.primarySoft : "#fff",
                          color: t.text,
                          fontSize: 12,
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        기타
                      </button>
                    </div>
                    {isOther && (
                      <input
                        type="number"
                        min={1}
                        max={MAX_CUSTOM_MINUTES}
                        step={1}
                        value={customText[item.exercise_name] ?? ""}
                        onChange={(e) => {
                          const raw = e.target.value;
                          setCustomText((prev) => ({ ...prev, [item.exercise_name]: raw }));
                          const parsed = parseCustomMinutes(raw);
                          if (parsed !== null) {
                            setDurations((prev) => ({ ...prev, [item.exercise_name]: parsed }));
                          }
                        }}
                        placeholder={`운동 시간(분) 직접 입력 (1~${MAX_CUSTOM_MINUTES})`}
                        style={inputStyle(customInvalid)}
                      />
                    )}
                    <button
                      type="button"
                      onClick={() => handleLog(item)}
                      disabled={loggingExerciseName === item.exercise_name || disabled}
                      style={{
                        width: "100%",
                        padding: "8px 0",
                        borderRadius: 8,
                        border: "none",
                        background: t.primary,
                        color: "#fff",
                        fontSize: 13,
                        fontWeight: 700,
                        cursor: loggingExerciseName === item.exercise_name || disabled ? "default" : "pointer",
                        opacity: disabled ? 0.5 : 1,
                      }}
                    >
                      {loggingExerciseName === item.exercise_name ? "기록하는 중..." : "기록하기"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* 오늘 기록한 목록 */}
          <p style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 700, color: t.text }}>오늘 기록한 운동</p>
          {!today || today.logs.length === 0 ? (
            <p style={{ margin: "0 0 16px", fontSize: 13, color: t.textMuted }}>아직 기록한 운동이 없어요.</p>
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
          <p style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 700, color: t.text }}>최근 7일</p>
          <div style={{ display: "flex", gap: 6, alignItems: "flex-end", height: 70 }}>
            {(recent?.days ?? []).map((day) => (
              <div key={day.log_date} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
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
