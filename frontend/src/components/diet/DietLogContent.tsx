import { useEffect, useState } from "react";

import { dietApi } from "../../api/dietApi";
import type { DietRecentResult, DietTodayResult, FoodSearchResultItem } from "../../api/types";
import { pinkTheme as t } from "../../theme/pinkTheme";

const SERVING_MULTIPLIERS = [0.5, 1, 1.5, 2];
// 백엔드 DietLogCreateRequest.serving_multiplier의 상한(Field(gt=0, le=5))과 맞춘다.
const MAX_CUSTOM_MULTIPLIER = 5;

function parseCustomMultiplier(raw: string): number | null {
  const value = Number(raw);
  if (!raw.trim() || Number.isNaN(value) || value <= 0 || value > MAX_CUSTOM_MULTIPLIER) return null;
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
  const [today, setToday] = useState<DietTodayResult | null>(null);
  const [recent, setRecent] = useState<DietRecentResult | null>(null);
  const [loadingInitial, setLoadingInitial] = useState(true);

  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<FoodSearchResultItem[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [multipliers, setMultipliers] = useState<Record<string, number>>({});
  const [customMode, setCustomMode] = useState<Record<string, boolean>>({});
  const [customText, setCustomText] = useState<Record<string, string>>({});
  const [loggingFoodName, setLoggingFoodName] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([dietApi.getToday(), dietApi.getRecent()])
      .then(([todayResult, recentResult]) => {
        setToday(todayResult);
        setRecent(recentResult);
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

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearchLoading(true);
    setSearchError(null);
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

  async function handleLog(item: FoodSearchResultItem) {
    const multiplier = multipliers[item.food_name] ?? 1;
    setLoggingFoodName(item.food_name);
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
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "기록 중 오류가 발생했습니다.");
    } finally {
      setLoggingFoodName(null);
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
      <p style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 700, color: t.primary }}>🍽 오늘의 식단 기록</p>

      {loadingInitial && <p style={{ color: t.textMuted, fontSize: 13 }}>불러오는 중...</p>}

      {!loadingInitial && (
        <>
          {/* 오늘 총 섭취 요약 */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: t.text }}>오늘 섭취 칼로리</span>
              <span style={{ fontSize: 12, color: t.textMuted }}>
                {Math.round(totalKcal)} / {referenceKcal} kcal
              </span>
            </div>
            <div style={{ height: 10, borderRadius: 999, background: t.primarySoft, overflow: "hidden" }}>
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
            <div style={{ display: "flex", gap: 12, marginTop: 8, fontSize: 12, color: t.textMuted }}>
              <span>단백질 {Math.round(today?.total_protein_g ?? 0)}g</span>
              <span>탄수화물 {Math.round(today?.total_carb_g ?? 0)}g</span>
              <span>지방 {Math.round(today?.total_fat_g ?? 0)}g</span>
            </div>
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
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
              {searchResults.map((item) => {
                const multiplier = multipliers[item.food_name] ?? 1;
                const servingGrams = item.serving_size_g * multiplier;
                const kcal = (item.calorie_kcal_per_100g * servingGrams) / 100;
                const isOther = customMode[item.food_name] ?? false;
                const customValue = parseCustomMultiplier(customText[item.food_name] ?? "");
                const customInvalid = isOther && customValue === null;
                return (
                  <div
                    key={item.food_name}
                    style={{ border: `1px solid ${t.border}`, borderRadius: 12, padding: 12, background: t.pageBg }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
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
                            setMultipliers((prev) => ({ ...prev, [item.food_name]: m }));
                            setCustomMode((prev) => ({ ...prev, [item.food_name]: false }));
                          }}
                          style={{
                            flex: 1,
                            padding: "6px 0",
                            borderRadius: 8,
                            border: `1.5px solid ${!isOther && m === multiplier ? t.primary : t.border}`,
                            background: !isOther && m === multiplier ? t.primarySoft : "#fff",
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
                        onClick={() => setCustomMode((prev) => ({ ...prev, [item.food_name]: true }))}
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
                        min={0.1}
                        max={MAX_CUSTOM_MULTIPLIER}
                        step={0.1}
                        value={customText[item.food_name] ?? ""}
                        onChange={(e) => {
                          const raw = e.target.value;
                          setCustomText((prev) => ({ ...prev, [item.food_name]: raw }));
                          const parsed = parseCustomMultiplier(raw);
                          if (parsed !== null) {
                            setMultipliers((prev) => ({ ...prev, [item.food_name]: parsed }));
                          }
                        }}
                        placeholder={`인분 수 직접 입력 (0.1~${MAX_CUSTOM_MULTIPLIER})`}
                        style={{
                          width: "100%",
                          boxSizing: "border-box",
                          padding: "8px 10px",
                          marginBottom: 8,
                          border: `1.5px solid ${customInvalid ? t.danger : t.border}`,
                          borderRadius: 8,
                          fontSize: 13,
                          outline: "none",
                        }}
                      />
                    )}
                    <button
                      type="button"
                      onClick={() => handleLog(item)}
                      disabled={loggingFoodName === item.food_name || customInvalid}
                      style={{
                        width: "100%",
                        padding: "8px 0",
                        borderRadius: 8,
                        border: "none",
                        background: t.primary,
                        color: "#fff",
                        fontSize: 13,
                        fontWeight: 700,
                        cursor: loggingFoodName === item.food_name || customInvalid ? "default" : "pointer",
                        opacity: customInvalid ? 0.5 : 1,
                      }}
                    >
                      {loggingFoodName === item.food_name ? "기록하는 중..." : "기록하기"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* 오늘 기록한 목록 */}
          <p style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 700, color: t.text }}>오늘 기록한 식사</p>
          {!today || today.logs.length === 0 ? (
            <p style={{ margin: "0 0 16px", fontSize: 13, color: t.textMuted }}>아직 기록한 식사가 없어요.</p>
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
