import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { dietApi } from "../../api/dietApi";
import { healthInfoApi } from "../../api/healthInfoApi";
import type { DietRecentResult, DietTodayResult, FoodSearchResultItem } from "../../api/types";
import { pinkTheme as t } from "../../theme/pinkTheme";
import ReasonFeedback from "../common/ReasonFeedback";

const SERVING_MULTIPLIERS = [0.5, 1, 1.5, 2];
// 백엔드 DietLogCreateRequest.serving_multiplier의 상한(Field(gt=0, le=5))과 맞춘다.
const MAX_CUSTOM_MULTIPLIER = 5;

function parseCustomMultiplier(raw: string): number | null {
  const value = Number(raw);
  if (!raw.trim() || Number.isNaN(value) || value <= 0 || value > MAX_CUSTOM_MULTIPLIER)
    return null;
  return value;
}

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

/** 마이다이어리 > "오늘의 식단 기록" 모달 본문(F-DIET-1/2). 텍스트 검색으로 음식을 찾아 인분
 * 배율을 고르고 기록하면, 상단 오늘 총 섭취 요약(칼로리 바 + 단백질/탄수/지방)과 하단 최근 7일
 * 미니 리스트가 즉시 갱신된다. 사진인식은 이번 범위에서 제외(텍스트 검색만). */
export default function DietLogContent() {
  const navigate = useNavigate();
  const [today, setToday] = useState<DietTodayResult | null>(null);
  const [recent, setRecent] = useState<DietRecentResult | null>(null);
  const [loadingInitial, setLoadingInitial] = useState(true);
  // 식단 기록은 칼로리 목표치 계산에 키/몸무게가 필요해서 필수로 요구한다 - 둘 중 하나라도
  // 없으면 기록 UI 자체를 안 보여주고 개인건강정보 입력을 유도한다.
  const [missingBodyInfo, setMissingBodyInfo] = useState(false);

  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<FoodSearchResultItem[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  // 검색 결과 중 지금 "선택된" 음식 하나만 골라서 인분을 정하고 기록한다(2026-08-03 피드백:
  // 결과마다 인분 선택+기록 버튼이 다 붙어있으면 여러 개일 때 보기 힘들다 - 목록에서 하나 고르고
  // 그 아래에서만 인분/기록을 다루는 흐름으로 변경).
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [multiplier, setMultiplier] = useState(1);
  const [customMode, setCustomMode] = useState(false);
  const [customText, setCustomText] = useState("");
  const [logging, setLogging] = useState(false);

  useEffect(() => {
    Promise.all([dietApi.getToday(), dietApi.getRecent(), healthInfoApi.get()])
      .then(([todayResult, recentResult, healthInfo]) => {
        setToday(todayResult);
        setRecent(recentResult);
        setMissingBodyInfo(healthInfo.height_cm === null || healthInfo.weight_kg === null);
      })
      .finally(() => setLoadingInitial(false));
  }, []);

  async function refreshAfterMutation(todayResult: DietTodayResult) {
    setToday(todayResult);
    try {
      setRecent(await dietApi.getRecent());
    } catch {
      // 최근 7일은 부가 정보라 실패해도 오늘 기록 자체는 이미 반영됐다.
    }
  }

  function resetSelection() {
    setSelectedIndex(null);
    setMultiplier(1);
    setCustomMode(false);
    setCustomText("");
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearchLoading(true);
    setSearchError(null);
    resetSelection();
    try {
      const result = await dietApi.searchFood(query.trim());
      setSearchResults(result.results);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "검색 중 오류가 발생했습니다.");
      setSearchResults([]);
    } finally {
      setHasSearched(true);
      setSearchLoading(false);
    }
  }

  function handleSelect(index: number) {
    setSelectedIndex(index);
    setMultiplier(1);
    setCustomMode(false);
    setCustomText("");
  }

  async function handleLog() {
    if (selectedIndex === null) return;
    const item = searchResults[selectedIndex];
    setLogging(true);
    try {
      const todayResult = await dietApi.logFood({
        food_name: item.food_name,
        serving_size_g: item.serving_size_g,
        serving_multiplier: multiplier,
        calorie_kcal_per_100g: item.calorie_kcal_per_100g,
        protein_g_per_100g: item.protein_g_per_100g,
        carb_g_per_100g: item.carb_g_per_100g,
        fat_g_per_100g: item.fat_g_per_100g,
      });
      await refreshAfterMutation(todayResult);
      resetSelection();
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "기록 중 오류가 발생했습니다.");
    } finally {
      setLogging(false);
    }
  }

  async function handleDelete(logId: number) {
    try {
      const todayResult = await dietApi.deleteLog(logId);
      await refreshAfterMutation(todayResult);
    } catch {
      // 삭제 실패는 부가 동작이라 조용히 무시 - 목록이 그대로 남으니 다시 시도할 수 있다.
    }
  }

  const totalKcal = today?.total_kcal ?? 0;
  const referenceKcal = today?.reference_kcal ?? 2000;
  const kcalRatio = Math.min(totalKcal / referenceKcal, 1);
  const maxRecentKcal = Math.max(1, ...(recent?.days.map((d) => d.total_kcal) ?? [1]));

  return (
    <div style={cardStyle}>
      <p style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 700, color: t.primary }}>
        🍽 오늘의 식단 기록
      </p>

      {loadingInitial && <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>}

      {!loadingInitial && missingBodyInfo && (
        <div style={{ textAlign: "center", padding: "24px 8px" }}>
          <p style={{ fontSize: 32, margin: "0 0 10px" }}>📏</p>
          <p style={{ margin: "0 0 6px", fontSize: 14, fontWeight: 700, color: t.text }}>
            키/몸무게를 먼저 입력해주세요
          </p>
          <p style={{ margin: "0 0 18px", fontSize: 12.5, color: t.textMuted, lineHeight: 1.6 }}>
            섭취 칼로리 목표치를 정확히 계산하려면
            <br />
            키와 몸무게가 필요해요.
          </p>
          <button
            type="button"
            onClick={() => navigate("/health-info")}
            style={{
              padding: "10px 20px",
              border: "none",
              borderRadius: 10,
              background: t.primary,
              color: "#fff",
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            개인건강정보 입력하러 가기
          </button>
        </div>
      )}

      {!loadingInitial && !missingBodyInfo && (
        <>
          {/* 오늘 총 섭취 요약 */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>오늘 섭취 칼로리</span>
              <span style={{ fontSize: 12, color: t.textMuted }}>
                {Math.round(totalKcal)} / {referenceKcal} kcal
              </span>
            </div>
            <div
              style={{
                height: 10,
                borderRadius: 999,
                background: t.primarySoft,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${kcalRatio * 100}%`,
                  borderRadius: 999,
                  background: t.primary,
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            <div
              style={{ display: "flex", gap: 12, marginTop: 8, fontSize: 12, color: t.textMuted }}
            >
              <span>단백질 {Math.round(today?.total_protein_g ?? 0)}g</span>
              <span>탄수화물 {Math.round(today?.total_carb_g ?? 0)}g</span>
              <span>지방 {Math.round(today?.total_fat_g ?? 0)}g</span>
            </div>
            {today?.reference_kcal_reason && (
              <>
                <p
                  style={{ margin: "8px 0 0", fontSize: 11.5, color: t.textMuted, lineHeight: 1.5 }}
                >
                  ✨ {today.reference_kcal_reason}
                </p>
                <ReasonFeedback onSubmit={(value) => dietApi.submitKcalReasonFeedback(value)} />
              </>
            )}
          </div>

          {/* 음식 검색 */}
          <form onSubmit={handleSearch} style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="음식 이름 입력 (예: 흰쌀밥, 김치찌개)"
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
              검색 결과가 없어요. 다른 이름으로 검색해보세요(예: 흰쌀밥, 김치찌개).
            </p>
          )}

          {searchResults.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              {/* 결과 목록 - 하나만 골라서 아래에서 인분/기록을 다룬다 */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  marginBottom: selectedIndex !== null ? 10 : 0,
                }}
              >
                {searchResults.map((item, index) => {
                  const selected = selectedIndex === index;
                  const previewKcal = (item.calorie_kcal_per_100g * item.serving_size_g) / 100;
                  return (
                    <button
                      key={`${item.food_name}-${index}`}
                      type="button"
                      onClick={() => handleSelect(index)}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: 10,
                        border: `1.5px solid ${selected ? t.primary : t.border}`,
                        background: selected ? t.primarySoft : t.pageBg,
                        textAlign: "left",
                        cursor: "pointer",
                      }}
                    >
                      <strong style={{ fontSize: 13, color: t.text }}>{item.food_name}</strong>
                      <span style={{ fontSize: 12, color: t.textMuted }}>
                        1인분 {Math.round(item.serving_size_g)}g · {Math.round(previewKcal)}kcal
                      </span>
                    </button>
                  );
                })}
              </div>

              {selectedIndex !== null &&
                (() => {
                  const item = searchResults[selectedIndex];
                  const servingGrams = item.serving_size_g * multiplier;
                  const kcal = (item.calorie_kcal_per_100g * servingGrams) / 100;
                  const customValue = parseCustomMultiplier(customText);
                  const customInvalid = customMode && customValue === null;
                  return (
                    <div
                      style={{
                        border: `1.5px solid ${t.primary}`,
                        borderRadius: 12,
                        padding: 12,
                        background: t.pageBg,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          marginBottom: 8,
                        }}
                      >
                        <strong style={{ fontSize: 14, color: t.text }}>{item.food_name}</strong>
                        <span style={{ fontSize: 12, color: t.textMuted }}>
                          {Math.round(servingGrams)}g · {Math.round(kcal)}kcal
                        </span>
                      </div>
                      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                        {SERVING_MULTIPLIERS.map((m) => (
                          <button
                            key={m}
                            type="button"
                            onClick={() => {
                              setMultiplier(m);
                              setCustomMode(false);
                            }}
                            style={{
                              flex: 1,
                              padding: "6px 0",
                              borderRadius: 10,
                              border: `1.5px solid ${!customMode && m === multiplier ? t.primary : t.border}`,
                              background: !customMode && m === multiplier ? t.primarySoft : "#fff",
                              color: t.text,
                              fontSize: 12,
                              fontWeight: 600,
                              cursor: "pointer",
                            }}
                          >
                            {m}인분
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
                          min={0.1}
                          max={MAX_CUSTOM_MULTIPLIER}
                          step={0.1}
                          value={customText}
                          onChange={(e) => {
                            const raw = e.target.value;
                            setCustomText(raw);
                            const parsed = parseCustomMultiplier(raw);
                            if (parsed !== null) {
                              setMultiplier(parsed);
                            }
                          }}
                          placeholder={`인분 수 직접 입력 (0.1~${MAX_CUSTOM_MULTIPLIER})`}
                          style={{
                            width: "100%",
                            boxSizing: "border-box",
                            padding: "8px 10px",
                            marginBottom: 8,
                            border: `1.5px solid ${customInvalid ? t.danger : t.border}`,
                            borderRadius: 10,
                            fontSize: 13,
                            outline: "none",
                          }}
                        />
                      )}
                      <button
                        type="button"
                        onClick={handleLog}
                        disabled={logging || customInvalid}
                        style={{
                          width: "100%",
                          padding: "8px 0",
                          borderRadius: 10,
                          border: "none",
                          background: t.primary,
                          color: "#fff",
                          fontSize: 13,
                          fontWeight: 700,
                          cursor: logging || customInvalid ? "default" : "pointer",
                          opacity: customInvalid ? 0.5 : 1,
                        }}
                      >
                        {logging ? "기록하는 중..." : "기록하기"}
                      </button>
                    </div>
                  );
                })()}
            </div>
          )}

          {/* 오늘 기록한 목록 */}
          <p style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 700, color: t.text }}>
            오늘 기록한 식사
          </p>
          {!today || today.logs.length === 0 ? (
            <p style={{ margin: "0 0 16px", fontSize: 13, color: t.textMuted }}>
              아직 기록한 식사가 없어요.
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
                    <strong style={{ fontSize: 13, color: t.text }}>{log.food_name}</strong>
                    <div style={{ fontSize: 12, color: t.textMuted }}>
                      {Math.round(log.serving_grams)}g · {Math.round(log.calorie_kcal)}kcal
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
