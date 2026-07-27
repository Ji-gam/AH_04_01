import type { LucideIcon } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { pinkTheme } from "../../theme/pinkTheme";

interface Props {
  icon: LucideIcon;
  children: ReactNode;
  /** 페이지마다 제목 아래 여백이 달라서 바깥 여백만 열어둔다. */
  style?: CSSProperties;
}

/** 모든 페이지 상단 제목. 홈 화면 인사말과 같은 모양(36px 원형 배경 + 핑크 라인아트
 * 아이콘 + 20px/700 제목)으로 통일한다 - 컬러 이모지는 쓰지 않는다. */
export default function PageTitle({ icon: Icon, children, style }: Props) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, ...style }}>
      <span
        aria-hidden
        style={{
          width: 36,
          height: 36,
          flexShrink: 0,
          borderRadius: "50%",
          background: pinkTheme.pageBg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon size={18} color={pinkTheme.primary} strokeWidth={1.75} />
      </span>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: 0 }}>
        {children}
      </h1>
    </div>
  );
}
