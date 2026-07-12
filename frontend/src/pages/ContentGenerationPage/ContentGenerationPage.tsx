import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { contentApi } from "../../api/contentApi";
import type { HealthContentResult } from "../../api/types";
import { pinkTheme } from "../../theme/pinkTheme";

const cardStyle: React.CSSProperties = {
  background: pinkTheme.cardBg,
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: "12px",
  padding: "16px",
};

/** 더보기 > 관리자 컨텐츠생성.
 * 버튼을 누르면 실제로 ai_worker의 LLM 생성(/generate-structured)을 호출해 콘텐츠 카드를
 * 만들고 즉시 DB(health_contents)에 저장한다 — 오프라인 배치 생성을 보완하는 온라인 단건
 * 생성 관리 도구다. 저장된 카드는 "정보" 탭에도 그대로 반영된다.
 * 진입 시 기존 생성물을 GET /contents/me로 불러와 목록에 채우므로, 새로고침해도
 * 이전에 만든 카드들이 그대로 보인다. */
export default function ContentGenerationPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HealthContentResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    contentApi
      .getContents()
      .then((feed) => setItems(feed.items))
      .catch(() => {
        // 목록 조회 실패는 조용히 빈 목록으로 시작한다 - 생성 자체는 계속 가능해야 하므로.
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function handleGenerate() {
    setIsGenerating(true);
    setError(null);
    try {
      const item = await contentApi.generate();
      // 같은 (질환,카테고리,오늘) 카드를 다시 생성한 경우 갱신된 것이므로, 기존 항목은
      // 지우고 최신 내용을 맨 위로 올린다(중복 표시 방지).
      setItems((prev) => [item, ...prev.filter((existing) => existing.id !== item.id)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "생성 중 오류가 발생했습니다.");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <div style={{ minHeight: "100%", background: pinkTheme.pageBg, padding: "20px" }}>
      <div style={{ maxWidth: 400, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate("/more")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            marginBottom: 12,
            cursor: "pointer",
          }}
        >
          ← 뒤로가기
        </button>

        <h1 style={{ color: pinkTheme.text, fontSize: 20 }}>관리자 컨텐츠생성</h1>
        <p style={{ color: pinkTheme.textMuted, fontSize: 13, marginTop: 4 }}>
          버튼을 누르면 실제 LLM으로 건강 콘텐츠 카드를 생성해 저장합니다. "정보" 탭에 바로
          반영돼요.
        </p>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={isGenerating}
          style={{
            width: "100%",
            marginTop: 16,
            padding: "14px 16px",
            border: "none",
            borderRadius: "8px",
            background: isGenerating ? pinkTheme.primarySoft : pinkTheme.primary,
            color: "#fff",
            fontWeight: 600,
            cursor: isGenerating ? "not-allowed" : "pointer",
          }}
        >
          {isGenerating ? "생성 중..." : "컨텐츠생성"}
        </button>

        {error && <p style={{ color: pinkTheme.danger, marginTop: 12 }}>{error}</p>}

        <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "20px" }}>
          {isLoading && (
            <p
              style={{
                color: pinkTheme.textMuted,
                fontSize: 13,
                textAlign: "center",
                marginTop: 20,
              }}
            >
              불러오는 중...
            </p>
          )}
          {!isLoading && items.length === 0 && !isGenerating && (
            <p
              style={{
                color: pinkTheme.textMuted,
                fontSize: 13,
                textAlign: "center",
                marginTop: 20,
              }}
            >
              아직 생성된 콘텐츠가 없어요.
            </p>
          )}
          {items.map((item) => (
            <Link
              key={item.id}
              to={`/content-generation/${item.id}`}
              state={{ item }}
              style={{ ...cardStyle, textDecoration: "none", display: "block" }}
            >
              <div
                style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
              >
                <span style={{ fontSize: 12, color: pinkTheme.textMuted }}>
                  {item.disease_code} · {item.category}
                </span>
                <span aria-hidden style={{ color: pinkTheme.textMuted }}>
                  ›
                </span>
              </div>
              <p style={{ color: pinkTheme.text, fontWeight: 600, marginTop: 6, marginBottom: 4 }}>
                {item.title}
              </p>
              <p
                style={{
                  color: pinkTheme.textMuted,
                  fontSize: 13,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {item.summary}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
