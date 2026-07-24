import { useNavigate } from "react-router-dom";

import HabitSelectionContent from "../../components/habit/HabitSelectionContent";
import { pinkTheme as t } from "../../theme/pinkTheme";

/** 더보기 > 마이다이어리. 본문은 HabitSelectionContent(공용) - 홈 화면 라이프스타일
 * 카드에서는 같은 본문을 모달로 띄운다(2026-07-19). 여기서는 뒤로가기만 이 페이지가 갖는다. */
export default function HabitSelectionPage() {
  const navigate = useNavigate();

  return (
    <div style={{ background: t.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate("/more")}
          style={{
            background: "none",
            border: "none",
            color: t.textMuted,
            padding: 0,
            marginBottom: 12,
            cursor: "pointer",
          }}
        >
          ← 뒤로가기
        </button>

        <HabitSelectionContent />
      </div>
    </div>
  );
}
