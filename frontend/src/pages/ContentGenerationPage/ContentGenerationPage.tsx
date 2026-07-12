import { useState } from "react";
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

/** [QA 전용] 더보기 > 컨텐츠생성.
 * 버튼을 누르면 실제로 ai_worker의 LLM 생성(/generate-structured)을 호출해 콘텐츠 카드를
 * 만든다 — 게이트웨이 생성 타임아웃 분리 수정을 수동으로 검증하기 위한 화면이다.
 * 생성 결과는 이 페이지의 메모리(state)에만 쌓인다(새로고침하면 목록이 비워진다) —
 * 영구 저장/조회는 "정보" 탭(InfoPage)의 몫이고, 이 화면은 순수 QA 스크래치 용도다. */
export default function ContentGenerationPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HealthContentResult[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setIsGenerating(true);
    setError(null);
    try {
      const item = await contentApi.generate();
      setItems((prev) => [item, ...prev]);
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

        <h1 style={{ color: pinkTheme.text, fontSize: 20 }}>컨텐츠생성 (QA)</h1>
        <p style={{ color: pinkTheme.textMuted, fontSize: 13, marginTop: 4 }}>
          버튼을 누르면 실제 LLM 생성이 호출됩니다. 5초를 넘겨도 정상 완료되는지 확인해보세요.
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
          {items.length === 0 && !isGenerating && (
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
