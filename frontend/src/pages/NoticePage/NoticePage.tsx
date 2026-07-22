import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { noticeApi } from "../../api/noticeApi";
import type { NoticeResult } from "../../api/types";
import { pinkTheme } from "../../theme/pinkTheme";

/** 더보기 > 공지사항(2026-07-16 신설, 2026-07-22 백엔드 연동) - 등록된 공지/마케팅 소식을
 * 목록+아코디언으로 보여준다. 더보기에서 열었을 때만 뒤로가기가 더보기로 돌아간다(PR #182와
 * 같은 규칙). 새 공지 등록은 더보기 > 관리자 공지등록(NoticeAdminPage.tsx)에서 한다. */
export default function NoticePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const cameFromMore = (location.state as { from?: string } | null)?.from === "more";

  const [notices, setNotices] = useState<NoticeResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  useEffect(() => {
    noticeApi
      .list()
      .then((items) => {
        setNotices(items);
        setOpenId(items.find((n) => n.is_new)?.id ?? null);
      })
      .catch(() => setError("공지사항을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate(cameFromMore ? "/more" : "/")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            marginBottom: 10,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          ← 뒤로가기
        </button>

        <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: "0 0 20px" }}>
          📢 공지사항
        </h1>

        {loading && <p style={{ color: pinkTheme.textMuted, fontSize: 14 }}>불러오는 중...</p>}
        {error && <p style={{ color: pinkTheme.danger, fontSize: 14 }}>{error}</p>}

        {!loading && !error && notices.length === 0 && (
          <p
            style={{ color: pinkTheme.textMuted, fontSize: 14, textAlign: "center", marginTop: 20 }}
          >
            아직 등록된 공지사항이 없어요.
          </p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {notices.map((notice) => {
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
                      {notice.is_new && (
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
                    <p style={{ margin: "4px 0 0", fontSize: 12, color: pinkTheme.textMuted }}>
                      {notice.created_at.slice(0, 10)}
                    </p>
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
