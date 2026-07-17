import type { CSSProperties } from "react";

// 연핑크 + 화이트, 사랑스러운 톤 (조원 요청 스타일). AlarmPage/theme.ts에서 시작된 팔레트를
// 이번에 로그인/홈/개인건강정보 등 여러 화면이 같이 쓰게 되어 공용(common)으로 승격했다.
// 값 자체는 AlarmPage의 것과 동일 - 나중에 AlarmPage도 이걸 참조하도록 정리해도 됨.
export const pinkTheme = {
  pageBg: "#FFF5F8",
  cardBg: "#FFFFFF",
  border: "#FFD6E4",
  primary: "#FF6F91",
  primaryHover: "#FF4F79",
  primarySoft: "#FFE3EC",
  text: "#5A4A4E",
  textMuted: "#B98A9A",
  danger: "#E85D75",
  success: "#7BC69A",
};

/**
 * 버튼 크기/색상 + 글씨 크기 통일(2026-07-18) — pinkTheme 인라인 스타일을 쓰는 화면들이
 * 각자 padding/borderRadius/fontSize를 따로 정해서 페이지마다 조금씩 달랐다. 여기 값만
 * 기준으로 삼고, 레이아웃 전용 속성(width/margin/flex 등)은 각 화면에서 계속 따로 준다.
 * (Tailwind+shadcn 마이그레이션 대상 화면 — InfoPage/InfoDetailPage/DurScreeningPage/
 * ChatPage — 은 스타일 체계가 달라 이 통일 범위에서 제외한다. docs/FRONTEND_UI_GUIDE.md 참고.)
 */
export const primaryButtonStyle: CSSProperties = {
  padding: "13px 0",
  border: "none",
  borderRadius: 10,
  background: pinkTheme.primary,
  color: "#fff",
  fontWeight: 700,
  fontSize: 15,
  cursor: "pointer",
};

// 위험(삭제/탈퇴 등) 확정 버튼 — primaryButtonStyle과 크기/글씨는 같고 색만 danger.
export const dangerButtonStyle: CSSProperties = {
  ...primaryButtonStyle,
  background: pinkTheme.danger,
};

// "← 뒤로가기" 등 텍스트만 있는 보조 버튼.
export const backButtonStyle: CSSProperties = {
  background: "none",
  border: "none",
  color: pinkTheme.textMuted,
  padding: 0,
  cursor: "pointer",
  fontSize: 13,
};

// ✏️/🗑️ 같은 인라인 아이콘 버튼.
export const iconButtonStyle: CSSProperties = {
  background: "none",
  border: "none",
  color: pinkTheme.textMuted,
  cursor: "pointer",
  fontSize: 14,
};

// 페이지 제목(<h1>). margin은 화면마다 다르니 각자 지정.
export const pageTitleStyle: CSSProperties = {
  fontSize: 20,
  fontWeight: 700,
  color: pinkTheme.text,
};

// 본문 텍스트.
export const bodyTextStyle: CSSProperties = {
  fontSize: 14,
  color: pinkTheme.text,
};

// 안내문/타임스탬프 등 흐린 보조 텍스트.
export const captionTextStyle: CSSProperties = {
  fontSize: 12,
  color: pinkTheme.textMuted,
};
