import { useLocation, useNavigate } from "react-router-dom";

import type { HealthContentResult } from "../../api/types";
import {
  backButtonStyle,
  captionTextStyle,
  pageTitleStyle,
  pinkTheme,
} from "../../theme/pinkTheme";

const cardStyle: React.CSSProperties = {
  background: pinkTheme.cardBg,
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: "12px",
  padding: "16px",
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
            style={{ ...backButtonStyle, marginBottom: 12 }}
          >
            ← 뒤로가기
          </button>
          <p style={{ color: pinkTheme.textMuted }}>
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
          style={{ ...backButtonStyle, marginBottom: 12 }}
        >
          ← 뒤로가기
        </button>

        <p style={captionTextStyle}>
          {item.disease_code} · {item.category} · {item.content_date}
        </p>
        <h1 style={{ ...pageTitleStyle, marginTop: 4 }}>{item.title}</h1>

        <div style={{ ...cardStyle, marginTop: 16 }}>
          <p style={{ color: pinkTheme.textMuted, fontWeight: 600, marginBottom: 6 }}>요약</p>
          <p style={{ color: pinkTheme.text }}>{item.summary}</p>
        </div>

        <div style={{ ...cardStyle, marginTop: 12 }}>
          <p style={{ color: pinkTheme.textMuted, fontWeight: 600, marginBottom: 6 }}>본문</p>
          <p style={{ color: pinkTheme.text, whiteSpace: "pre-wrap" }}>{item.body}</p>
        </div>

        {item.image_prompt && (
          <div style={{ ...cardStyle, marginTop: 12 }}>
            <p style={{ color: pinkTheme.textMuted, fontWeight: 600, marginBottom: 6 }}>
              이미지 프롬프트
            </p>
            <p style={{ color: pinkTheme.text }}>{item.image_prompt}</p>
          </div>
        )}

        <p style={{ ...captionTextStyle, marginTop: 16 }}>{item.disclaimer}</p>
      </div>
    </div>
  );
}
