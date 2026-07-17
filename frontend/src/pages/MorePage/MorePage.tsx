import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiFetch } from "../../api/client";
import { useAuth } from "../../hooks/useAuth";
import {
  captionTextStyle,
  pageTitleStyle,
  pinkTheme,
  primaryButtonStyle,
} from "../../theme/pinkTheme";
import Modal from "../AlarmPage/components/Modal";

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

interface GridItemSpec {
  key: string;
  label: string;
  icon: string;
  bg: string;
  onClick: () => void;
}

/** 더보기 화면. 디자인 시안 반영(2026-07-16) - 상단 프로필 카드 + 3x2 바로가기 그리드 +
 * 하단 리스트(알림설정/데이터활용동의/공지사항/관리자컨텐츠생성) 구조로 재구성했다.
 * "약품검색"은 기존처럼 페이지 이동이 아니라 모달로 뜬다(원래 동작 유지) - "내 정보"도
 * 개인건강정보/생활습관정보/복약스케줄 3개를 모아 보여주는 모달로 새로 만들었다.
 * 프로필 사진(아바타)은 이번엔 업로드 기능 없이 이름 첫 글자만 표시한다(다음 단계에서 실제
 * 업로드로 교체 예정). 로그아웃은 계정관리(개인정보수정) 페이지의 회원탈퇴 아래로 옮겼다. */
export default function MorePage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [isDurModalOpen, setIsDurModalOpen] = useState(false);
  const [isMyInfoModalOpen, setIsMyInfoModalOpen] = useState(false);
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

  const handleOpenDurModal = () => {
    setIsDurModalOpen(true);
    setQuery("");
    setResults([]);
    setNotFoundReason(null);
    setElapsedMs(null);
    setError(null);
  };

  // 검색 결과 약을 바로 복약알림 등록 화면으로 넘긴다 — 약 이름을 미리 채운 채 폼이 열린다.
  const handleRegisterReminder = (itemName: string) => {
    setIsDurModalOpen(false);
    navigate("/alarms", { state: { prefillMedicationName: itemName } });
  };

  const gridItems: GridItemSpec[] = [
    {
      key: "my-info",
      label: "내 정보",
      icon: "👤",
      bg: "#DCE7FB",
      onClick: () => setIsMyInfoModalOpen(true),
    },
    {
      key: "drug-search",
      label: "의약품 검색",
      icon: "🔍",
      bg: "#DCF3E7",
      onClick: handleOpenDurModal,
    },
    {
      key: "emergency",
      label: "응급안내",
      icon: "🚨",
      bg: "#FCE1E6",
      onClick: () => navigate("/emergency-guide"),
    },
    {
      key: "prescription",
      label: "처방전 등록",
      icon: "📝",
      bg: "#DCEEF9",
      onClick: () => navigate("/track", { state: { from: "more" } }),
    },
    {
      key: "family",
      label: "가족관리",
      icon: "👨‍👩‍👧",
      bg: "#FBE1E1",
      onClick: () => navigate("/family", { state: { from: "more" } }),
    },
    {
      key: "lifestyle",
      label: "생활습관 추천",
      icon: "🎉",
      bg: "#FCEFD1",
      onClick: () => navigate("/habit-selection"),
    },
  ];

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 20,
          }}
        >
          <h1 style={{ ...pageTitleStyle, margin: 0 }}>더보기</h1>
          <Link
            to="/account-settings"
            state={{ from: "more" }}
            style={{
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 999,
              padding: "6px 14px",
              fontSize: 13,
              fontWeight: 600,
              color: pinkTheme.text,
              background: pinkTheme.cardBg,
              textDecoration: "none",
            }}
          >
            계정관리
          </Link>
        </div>

        {/* 프로필 카드 - 아바타는 꾸밈 요소(업로드 기능은 다음 단계) */}
        <div
          style={{
            background: pinkTheme.primarySoft,
            borderRadius: 16,
            padding: 18,
            marginBottom: 20,
            display: "flex",
            alignItems: "center",
            gap: 14,
          }}
        >
          <span
            aria-hidden
            style={{
              width: 52,
              height: 52,
              borderRadius: "50%",
              flexShrink: 0,
              border: `1.5px dashed ${pinkTheme.border}`,
              background: pinkTheme.cardBg,
              color: pinkTheme.primary,
              fontSize: user ? 20 : 18,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {user ? user.name.charAt(0) : "👤"}
          </span>
          <div style={{ flex: 1 }}>
            <p style={{ margin: 0, fontWeight: 700, fontSize: 15, color: pinkTheme.text }}>
              {user ? `${user.name}님, 환영합니다` : "로그인이 필요해요"}
            </p>
            {!user && (
              <Link
                to="/login"
                style={{
                  fontSize: 12,
                  color: pinkTheme.primary,
                  textDecoration: "none",
                  fontWeight: 600,
                }}
              >
                로그인하러 가기 →
              </Link>
            )}
          </div>
        </div>

        {/* 3x2 바로가기 그리드 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 10,
            marginBottom: 20,
          }}
        >
          {gridItems.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={item.onClick}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 8,
                padding: "16px 6px",
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: 16,
                background: pinkTheme.cardBg,
                cursor: "pointer",
                boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  background: item.bg,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 19,
                }}
              >
                {item.icon}
              </span>
              <span style={{ fontSize: 12.5, fontWeight: 600, color: pinkTheme.text }}>
                {item.label}
              </span>
            </button>
          ))}
        </div>

        {/* 리스트 항목 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Link to="/notification-settings" style={menuCardStyle}>
            <span>🔔 알림 설정</span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/data-consent" style={menuCardStyle}>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              📋 데이터 활용 동의
              <span
                aria-hidden
                style={{
                  background: pinkTheme.primary,
                  color: "#fff",
                  borderRadius: 999,
                  padding: "2px 8px",
                  fontSize: 10.5,
                  fontWeight: 700,
                }}
              >
                혜택
              </span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/notices" state={{ from: "more" }} style={menuCardStyle}>
            <span>📢 공지사항</span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>

          <Link to="/content-generation" style={menuCardStyle}>
            <span>
              🛠️ 관리자 컨텐츠생성
              <span style={{ ...captionTextStyle, display: "block", marginTop: 2 }}>
                실제 LLM으로 건강 콘텐츠 카드를 즉시 생성해 "정보" 탭에 반영해요
              </span>
            </span>
            <span aria-hidden style={{ color: pinkTheme.textMuted }}>
              ›
            </span>
          </Link>
        </div>

        {/* "내 정보" 모달 - 개인건강정보/생활습관정보/복약스케줄 모아보기 */}
        {isMyInfoModalOpen && (
          <Modal onClose={() => setIsMyInfoModalOpen(false)}>
            <div
              style={{
                background: pinkTheme.cardBg,
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: 16,
                padding: 18,
                boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
              }}
            >
              <p
                style={{
                  margin: "0 0 14px",
                  fontSize: 15,
                  fontWeight: 700,
                  color: pinkTheme.primary,
                }}
              >
                👤 내 정보
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <Link
                  to="/health-info"
                  state={{ from: "more" }}
                  onClick={() => setIsMyInfoModalOpen(false)}
                  style={menuCardStyle}
                >
                  <span>
                    🩺 개인건강정보
                    <span style={{ ...captionTextStyle, display: "block", marginTop: 2 }}>
                      키/체중/BMI, 진단병력·가족력, 특이사항을 관리해요
                    </span>
                  </span>
                  <span aria-hidden style={{ color: pinkTheme.textMuted }}>
                    ›
                  </span>
                </Link>
                <Link
                  to="/lifestyle-info"
                  onClick={() => setIsMyInfoModalOpen(false)}
                  style={menuCardStyle}
                >
                  <span>
                    🌙 생활습관 정보
                    <span style={{ ...captionTextStyle, display: "block", marginTop: 2 }}>
                      기상·식사·취침 시간을 설정해 복약 리듬을 맞춰요
                    </span>
                  </span>
                  <span aria-hidden style={{ color: pinkTheme.textMuted }}>
                    ›
                  </span>
                </Link>
                <Link
                  to="/schedule"
                  onClick={() => setIsMyInfoModalOpen(false)}
                  style={menuCardStyle}
                >
                  <span>
                    ⏰ 복약 스케줄
                    <span style={{ ...captionTextStyle, display: "block", marginTop: 2 }}>
                      오늘 먹을 약을 시간순으로 확인하고 복용 체크해요
                    </span>
                  </span>
                  <span aria-hidden style={{ color: pinkTheme.textMuted }}>
                    ›
                  </span>
                </Link>
              </div>
            </div>
          </Modal>
        )}

        {/* 의약품 DUR/효능 검색 모달 (기존 동작 그대로) */}
        {isDurModalOpen && (
          <div
            onClick={() => setIsDurModalOpen(false)}
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
              <button
                onClick={() => setIsDurModalOpen(false)}
                style={{
                  position: "absolute",
                  top: 12,
                  right: 12,
                  border: "none",
                  borderRadius: 8,
                  background: pinkTheme.primarySoft,
                  color: pinkTheme.primary,
                  cursor: "pointer",
                  padding: "4px 10px",
                  fontSize: 12,
                  fontWeight: 600,
                }}
              >
                닫기
              </button>

              <h3 style={{ margin: "0 0 14px", fontSize: 16, color: pinkTheme.primary }}>
                🔍 의약품 DUR 및 효능 검색
              </h3>

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
                <button type="submit" style={{ ...primaryButtonStyle, padding: "10px 16px" }}>
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
