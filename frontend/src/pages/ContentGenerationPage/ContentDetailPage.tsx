import { Sparkles } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import type { HealthContentResult } from "../../api/types";
import PageTitle from "../../components/common/PageTitle";
import { pinkTheme } from "../../theme/pinkTheme";

const cardStyle: React.CSSProperties = {
  background: pinkTheme.cardBg,
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: 16,
  padding: 18,
  boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
};

/** 관리자 컨텐츠생성 목록 아이템의 상세화면.
 * 별도 상세조회 API 없이, 목록에서 클릭할 때 라우터 state로 넘겨받은 데이터만 그린다 —
 * 새 탭이나 URL 직접 접근처럼 state 없이 들어오면 "목록에서 다시 눌러달라"는 안내만
 * 보여준다(카드 자체는 DB에 남아있고 "정보" 탭/목록 재조회로 다시 볼 수 있다). */
export default function ContentDetailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const item = (location.state as { item?: HealthContentResult } | null)?.item;

  if (!item) {
    return (
      <div style={{ minHeight: "100%", background: pinkTheme.pageBg, padding: "20px" }}>
        <div style={{ maxWidth: 400, margin: "0 auto" }}>
          <button
            type="button"
            onClick={() => navigate("/content-generation")}
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
          <p style={{ color: pinkTheme.textMuted, fontSize: 13 }}>
            이 상세화면은 목록에서 클릭해야 볼 수 있어요. 목록에서 다시 눌러주세요.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100%", background: pinkTheme.pageBg, padding: "20px" }}>
      <div style={{ maxWidth: 400, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate("/content-generation")}
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

        <p style={{ fontSize: 13, color: pinkTheme.textMuted }}>
          {item.disease_code} · {item.category} · {item.content_date}
        </p>
        <PageTitle icon={Sparkles} style={{ margin: "4px 0 12px" }}>
          {item.title}
        </PageTitle>

        <div style={{ ...cardStyle, marginTop: 16 }}>
          <p
            style={{
              color: pinkTheme.textMuted,
              fontSize: 13,
              fontWeight: 700,
              marginBottom: 6,
            }}
          >
            요약
          </p>
          <p style={{ color: pinkTheme.text, fontSize: 14 }}>{item.summary}</p>
        </div>

        <div style={{ ...cardStyle, marginTop: 12 }}>
          <p
            style={{
              color: pinkTheme.textMuted,
              fontSize: 13,
              fontWeight: 700,
              marginBottom: 6,
            }}
          >
            본문
          </p>
          <p style={{ color: pinkTheme.text, fontSize: 14, whiteSpace: "pre-wrap" }}>{item.body}</p>
        </div>

        {item.image_prompt && (
          <div style={{ ...cardStyle, marginTop: 12 }}>
            <p
              style={{
                color: pinkTheme.textMuted,
                fontSize: 13,
                fontWeight: 700,
                marginBottom: 6,
              }}
            >
              이미지 프롬프트
            </p>
            <p style={{ color: pinkTheme.text, fontSize: 14 }}>{item.image_prompt}</p>
          </div>
        )}

        <p style={{ color: pinkTheme.textMuted, fontSize: 13, marginTop: 16 }}>{item.disclaimer}</p>
      </div>
    </div>
  );
}
