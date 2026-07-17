import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  backButtonStyle,
  captionTextStyle,
  pageTitleStyle,
  pinkTheme,
} from "../../theme/pinkTheme";

interface Notice {
  id: string;
  date: string;
  isNew: boolean;
  title: string;
  body: string;
}

// 지금은 백엔드 없이 정적으로 관리한다 - 공지가 자주 안 바뀌고 개수도 적어서, API+DB까지
// 만들 필요 없이 여기 배열만 고치면 된다(더보기 > 관리자 컨텐츠생성과는 별개 - 그건 "정보"
// 탭에 실리는 건강 콘텐츠고, 이건 서비스 자체 공지다).
const NOTICES: Notice[] = [
  {
    id: "service-launch",
    date: "2026-07-01",
    isNew: false,
    title: "🎉 Re:medi 서비스를 시작합니다",
    body: "복약관리와 건강 상담을 한 곳에서 - Re:medi를 오픈했습니다.\n\n처방전/알약을 스캔해서 복약 일정을 자동으로 등록하고, 시간에 맞춰 알림을 받아보세요. 개인건강정보를 등록하면 나에게 맞는 라이프스타일 습관과 건강 콘텐츠도 추천해드려요. 부모님 등 가족 구성원을 연결하면 가족 몫의 약도 함께 챙길 수 있습니다.\n\n앞으로도 더 편한 복약관리를 위해 계속 업데이트할게요. 잘 부탁드립니다!",
  },
  {
    id: "ai-chat-paper-citation",
    date: "2026-07-15",
    isNew: true,
    title: "💬 AI 건강 상담에 논문 근거 답변이 추가됐어요",
    body: "AI 건강 상담이 더 똑똑해졌습니다. 이제 질문에 답할 때 관련 의학 논문을 함께 찾아서, 답변 아래 출처 칩으로 보여드려요. 칩을 누르면 어떤 논문을 근거로 답했는지 바로 확인할 수 있습니다.\n\n의약품 상호작용(DUR) 정보도 같은 방식으로 통합해서, 복용 중인 약과 관련된 질문에 더 정확하게 답할 수 있게 됐어요.\n\n하단에는 자주 쓰는 화면(복약스케쥴/약등록/홈/가족관리/응급안내)으로 바로 이동할 수 있는 아이콘 메뉴도 새로 생겼으니 함께 확인해보세요.",
  },
];

/** 더보기 > 공지사항(2026-07-16 신설). 지금은 백엔드 없이 정적 배열로 관리하는 간단한
 * 목록+아코디언 화면이다 - 더보기에서 열었을 때만 뒤로가기가 더보기로 돌아간다(PR #182와
 * 같은 규칙). */
export default function NoticePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const cameFromMore = (location.state as { from?: string } | null)?.from === "more";
  const [openId, setOpenId] = useState<string | null>(NOTICES.find((n) => n.isNew)?.id ?? null);

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate(cameFromMore ? "/more" : "/")}
          style={{ ...backButtonStyle, marginBottom: 10 }}
        >
          ← 뒤로가기
        </button>

        <h1 style={{ ...pageTitleStyle, margin: "0 0 20px" }}>📢 공지사항</h1>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {NOTICES.map((notice) => {
            const isOpen = openId === notice.id;
            return (
              <div
                key={notice.id}
                style={{
                  background: pinkTheme.cardBg,
                  border: `1px solid ${pinkTheme.border}`,
                  borderRadius: 16,
                  boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
                  overflow: "hidden",
                }}
              >
                <button
                  type="button"
                  onClick={() => setOpenId(isOpen ? null : notice.id)}
                  style={{
                    width: "100%",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 10,
                    padding: "16px",
                    border: "none",
                    background: "none",
                    textAlign: "left",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 14.5, fontWeight: 700, color: pinkTheme.text }}>
                        {notice.title}
                      </span>
                      {notice.isNew && (
                        <span
                          aria-hidden
                          style={{
                            background: pinkTheme.primary,
                            color: "#fff",
                            borderRadius: 999,
                            padding: "1.5px 7px",
                            fontSize: 10,
                            fontWeight: 700,
                          }}
                        >
                          NEW
                        </span>
                      )}
                    </div>
                    <p style={{ ...captionTextStyle, margin: "4px 0 0" }}>{notice.date}</p>
                  </div>
                  <span
                    aria-hidden
                    style={{
                      color: pinkTheme.textMuted,
                      fontSize: 13,
                      transform: isOpen ? "rotate(90deg)" : "none",
                      transition: "transform 0.15s",
                    }}
                  >
                    ›
                  </span>
                </button>

                {isOpen && (
                  <p
                    style={{
                      margin: 0,
                      padding: "0 16px 16px",
                      fontSize: 13.5,
                      color: pinkTheme.text,
                      lineHeight: 1.7,
                      whiteSpace: "pre-line",
                    }}
                  >
                    {notice.body}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
