import React, { useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../../api/client";

interface SearchResultItem {
  item_name: string;
  entp_name: string;
  efficacy: string;
  precautions: string;
  source: "local_dur_db" | "public_data_api";
}

interface SearchDurResponse {
  elapsed_ms: number;
  results: SearchResultItem[];
  not_found_reason: string | null;
}

const DUR_SOURCE_LABEL: Record<SearchResultItem["source"], string> = {
  local_dur_db: "출처: 식약처 DUR 데이터(로컬)",
  public_data_api: "출처: 식약처 공공데이터포털 e약은요(실시간)",
};

export default function MorePage() {
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

  return (
    <div style={{ padding: "20px", fontFamily: "monospace" }}>
      <h1>더보기</h1>
      <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "15px" }}>
        {/* 약품검색 바로가기 버튼 */}
        <button
          onClick={handleOpenModal}
          style={{
            padding: "14px 16px",
            border: "1px solid #FFE3EB",
            borderRadius: "8px",
            background: "#FFF8FA",
            cursor: "pointer",
            textAlign: "left",
            display: "block",
            width: "100%",
            color: "inherit",
          }}
        >
          <strong>약품검색 🔍</strong>
          <span style={{ display: "block", fontSize: "12px", color: "#888", marginTop: "2px" }}>
            의약품의 효능 및 식약처 DUR 임부금기/노인주의 규칙을 검색합니다.
          </span>
        </button>

        <Link
          to="/schedule"
          style={{
            background: "#FFF8FA",
            border: "1px solid #FFE3EB",
            borderRadius: "8px",
            padding: "14px 16px",
            textDecoration: "none",
            color: "inherit",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>
            ⏰ 복약 스케줄
            <span style={{ display: "block", fontSize: "12px", color: "#888", marginTop: "2px" }}>
              오늘 먹을 약을 시간순으로 확인하고 복용 체크해요
            </span>
          </span>
          <span aria-hidden>›</span>
        </Link>

        <Link
          to="/health-info"
          style={{
            background: "#FFF8FA",
            border: "1px solid #FFE3EB",
            borderRadius: "8px",
            padding: "14px 16px",
            textDecoration: "none",
            color: "inherit",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>
            🩺 개인건강정보
            <span style={{ display: "block", fontSize: "12px", color: "#888", marginTop: "2px" }}>
              키/체중/BMI, 진단병력·가족력, 특이사항을 관리해요
            </span>
          </span>
          <span aria-hidden>›</span>
        </Link>
      </div>

      {/* 검색 모달 오버레이 (디자인 제거, 베어본) */}
      {isModalOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.5)",
            zIndex: 1000,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            padding: "10px",
          }}
        >
          <div
            style={{
              backgroundColor: "white",
              padding: "20px",
              border: "2px solid black",
              width: "100%",
              maxWidth: "500px",
              maxHeight: "80vh",
              overflowY: "auto",
              position: "relative",
              color: "black",
            }}
          >
            {/* 닫기 버튼 */}
            <button
              onClick={handleCloseModal}
              style={{
                position: "absolute",
                top: "10px",
                right: "10px",
                border: "1px solid black",
                background: "none",
                cursor: "pointer",
                padding: "2px 6px",
              }}
            >
              닫기
            </button>

            <h3>의약품 DUR 및 효능 검색</h3>

            {/* 검색 폼 */}
            <form
              onSubmit={handleSearch}
              style={{ display: "flex", gap: "5px", marginBottom: "15px" }}
            >
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="의약품명 입력 (예: 콘서타, 디아제팜)"
                style={{
                  flex: 1,
                  padding: "5px",
                  border: "1px solid black",
                  outline: "none",
                }}
              />
              <button
                type="submit"
                style={{
                  padding: "5px 10px",
                  border: "1px solid black",
                  background: "none",
                  cursor: "pointer",
                }}
              >
                검색
              </button>
            </form>

            {loading && <p>검색 중...</p>}
            {error && <p style={{ color: "red" }}>에러: {error}</p>}

            {elapsedMs !== null && (
              <p style={{ color: "green", fontSize: "11px", margin: "0 0 10px 0" }}>
                소요 시간: {elapsedMs} ms
              </p>
            )}

            {/* 결과 리스트 */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {results.length > 0
                ? results.map((item, index) => (
                    <div
                      key={index}
                      style={{
                        border: "1px solid black",
                        padding: "10px",
                      }}
                    >
                      <div
                        style={{
                          fontWeight: "bold",
                          borderBottom: "1px solid black",
                          paddingBottom: "5px",
                          marginBottom: "5px",
                        }}
                      >
                        {item.item_name} ({item.entp_name})
                      </div>
                      <p style={{ margin: "5px 0" }}>
                        <strong>효능:</strong> {item.efficacy}
                      </p>
                      <p
                        style={{
                          margin: "5px 0",
                          color: item.precautions.includes("특이사항 없음") ? "black" : "red",
                        }}
                      >
                        <strong>주의사항:</strong> {item.precautions}
                      </p>
                      <p style={{ margin: "5px 0 0", fontSize: "11px", color: "#666" }}>
                        {DUR_SOURCE_LABEL[item.source]}
                      </p>
                    </div>
                  ))
                : !loading &&
                  elapsedMs !== null && <p>{notFoundReason ?? "검색 결과가 없습니다."}</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
