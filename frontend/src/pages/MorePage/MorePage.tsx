import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiFetch } from "../../api/client";
import { pinkTheme } from "../../theme/pinkTheme";

interface SearchResultItem {
  item_name: string;
  entp_name: string;
  efficacy: string;
  precautions: string;
}

interface SearchDurResponse {
  elapsed_ms: number;
  results: SearchResultItem[];
  not_found_reason: string | null;
}

const DUR_SOURCE_LABEL = "출처: 식약처 의약품안전나라(DUR·의약품 개요정보)";

const menuCardStyle: React.CSSProperties = {
  background: pinkTheme.cardBg,
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: 16,
  padding: "14px 16px",
  textDecoration: "none",
  color: pinkTheme.text,
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
};

const menuDescStyle: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  color: pinkTheme.textMuted,
  marginTop: 2,
};

export default function MorePage() {
  const navigate = useNavigate();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [notFoundReason, setNotFoundReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<SearchDurResponse>(
        `/medications/search-dur?query=${encodeURIComponent(query.trim())}`,
      );
      setElapsedMs(data.elapsed_ms);
      setResults(data.results);
      setNotFoundReason(data.not_found_reason);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "검색 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenModal = () => {
    setIsModalOpen(true);
    setQuery("");
    setResults([]);
    setNotFoundReason(null);
    setElapsedMs(null);
    setError(null);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  // 검색 결과 약을 바로 복약알림 등록 화면으로 넘긴다 — 약 이름을 미리 채운 채 폼이 열린다.
  const handleRegisterReminder = (itemName: string) => {
    setIsModalOpen(false);
    navigate("/alarms", { state: { prefillMedicationName: itemName } });
  };

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: "0 0 20px" }}>
          🗂️ 더보기
        </h1>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {/* 약품검색 바로가기 버튼 */}
          <button onClick={handleOpenModal} style={{ ...menuCardStyle, cursor: "pointer" }}>
            <span style={{ textAlign: "left" }}>
              <strong>🔍 약품검색</strong>
              <span style={menuDescStyle}>
                의약품의 효능 및 식약처 DUR 임부금기/노인주의 규칙을 검색합니다.
              </span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </button>

          <Link to="/schedule" style={menuCardStyle}>
            <span>
              ⏰ 복약 스케줄
              <span style={menuDescStyle}>오늘 먹을 약을 시간순으로 확인하고 복용 체크해요</span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/health-info" style={menuCardStyle}>
            <span>
              🩺 개인건강정보
              <span style={menuDescStyle}>키/체중/BMI, 진단병력·가족력, 특이사항을 관리해요</span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/family" style={menuCardStyle}>
            <span>
              👨‍👩‍👧 가족관리
              <span style={menuDescStyle}>
                부모님 등 가족을 연결하고, 그분 몫으로 약을 등록해요
              </span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/lifestyle-info" style={menuCardStyle}>
            <span>
              🌙 생활습관 정보
              <span style={menuDescStyle}>기상·식사·취침 시간을 설정해 복약 리듬을 맞춰요</span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/habit-selection" style={menuCardStyle}>
            <span>
              🌿 오늘의 추천 습관
              <span style={menuDescStyle}>
                매일 추천되는 습관 중 최대 5개를 골라 홈에서 실천해요
              </span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/emergency-guide" style={menuCardStyle}>
            <span>
              🚨 응급안내
              <span style={menuDescStyle}>119·가까운 병원·약국·응급실을 빠르게 찾아요</span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/notification-settings" style={menuCardStyle}>
            <span>
              🔔 알림설정
              <span style={menuDescStyle}>푸시·무음 시간대·알림 강도를 설정해요</span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/data-consent" style={menuCardStyle}>
            <span>
              📋 데이터 활용 동의
              <span style={menuDescStyle}>건강정보·AI상담·위치정보·마케팅 동의를 관리해요</span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/content-generation" style={menuCardStyle}>
            <span>
              🛠️ 관리자 컨텐츠생성
              <span style={menuDescStyle}>
                실제 LLM으로 건강 콘텐츠 카드를 즉시 생성해 "정보" 탭에 반영해요
              </span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>
        </div>

        {/* 의약품 DUR/효능 검색 모달 */}
        {isModalOpen && (
          <div
            onClick={handleCloseModal}
            style={{
              position: "fixed",
              inset: 0,
              backgroundColor: "rgba(90, 74, 78, 0.45)",
              zIndex: 1000,
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              padding: 16,
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                backgroundColor: pinkTheme.cardBg,
                padding: 20,
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: 16,
                width: "100%",
                maxWidth: 500,
                maxHeight: "80vh",
                overflowY: "auto",
                position: "relative",
                color: pinkTheme.text,
              }}
            >
              {/* 닫기 버튼 */}
              <button
                onClick={handleCloseModal}
                style={{
                  position: "absolute",
                  top: 12,
                  right: 12,
                  border: `1px solid ${pinkTheme.border}`,
                  borderRadius: 8,
                  background: pinkTheme.cardBg,
                  color: pinkTheme.textMuted,
                  cursor: "pointer",
                  padding: "4px 10px",
                  fontSize: 12,
                }}
              >
                닫기
              </button>

              <h3 style={{ margin: "0 0 14px", fontSize: 16, color: pinkTheme.primary }}>
                🔍 의약품 DUR 및 효능 검색
              </h3>

              {/* 검색 폼 */}
              <form onSubmit={handleSearch} style={{ display: "flex", gap: 6, marginBottom: 14 }}>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="의약품명 입력 (예: 콘서타, 디아제팜)"
                  style={{
                    flex: 1,
                    padding: "10px 12px",
                    border: `1px solid ${pinkTheme.border}`,
                    borderRadius: 10,
                    fontSize: 14,
                    outline: "none",
                  }}
                />
                <button
                  type="submit"
                  style={{
                    padding: "10px 16px",
                    border: "none",
                    borderRadius: 10,
                    background: pinkTheme.primary,
                    color: "#fff",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  검색
                </button>
              </form>

              {loading && <p style={{ color: pinkTheme.textMuted, fontSize: 13 }}>검색 중...</p>}
              {error && <p style={{ color: pinkTheme.danger, fontSize: 13 }}>에러: {error}</p>}

              {elapsedMs !== null && (
                <p style={{ color: pinkTheme.success, fontSize: 11, margin: "0 0 10px" }}>
                  소요 시간: {elapsedMs} ms
                </p>
              )}

              {/* 결과 리스트 */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {results.length > 0
                  ? results.map((item, index) => (
                      <div
                        key={index}
                        style={{
                          border: `1px solid ${pinkTheme.border}`,
                          borderRadius: 12,
                          padding: 12,
                          background: pinkTheme.pageBg,
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            borderBottom: `1px solid ${pinkTheme.border}`,
                            paddingBottom: 6,
                            marginBottom: 6,
                          }}
                        >
                          <div style={{ fontWeight: 700, fontSize: 14 }}>
                            {item.item_name} ({item.entp_name})
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRegisterReminder(item.item_name)}
                            style={{
                              flexShrink: 0,
                              marginLeft: 8,
                              padding: "5px 10px",
                              borderRadius: 999,
                              border: "none",
                              background: pinkTheme.primary,
                              color: "#fff",
                              fontSize: 11.5,
                              fontWeight: 600,
                              cursor: "pointer",
                              whiteSpace: "nowrap",
                            }}
                          >
                            🔔 복약알림 등록
                          </button>
                        </div>
                        <p style={{ margin: "5px 0", fontSize: 13 }}>
                          <strong>효능:</strong> {item.efficacy}
                        </p>
                        <p
                          style={{
                            margin: "5px 0",
                            fontSize: 13,
                            color: item.precautions.includes("특이사항 없음")
                              ? pinkTheme.text
                              : pinkTheme.danger,
                          }}
                        >
                          <strong>주의사항:</strong> {item.precautions}
                        </p>
                        <p style={{ margin: "5px 0 0", fontSize: 11, color: pinkTheme.textMuted }}>
                          {DUR_SOURCE_LABEL}
                        </p>
                      </div>
                    ))
                  : !loading &&
                    elapsedMs !== null && (
                      <p style={{ fontSize: 13, color: pinkTheme.textMuted }}>
                        {notFoundReason ?? "검색 결과가 없습니다."}
                      </p>
                    )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
