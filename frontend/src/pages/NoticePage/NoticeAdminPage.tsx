import { Megaphone } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { noticeApi } from "../../api/noticeApi";
import type { NoticeKind, NoticeResult } from "../../api/types";
import PageTitle from "../../components/common/PageTitle";
import { pinkTheme } from "../../theme/pinkTheme";

/** 더보기 > 관리자 공지등록(2026-07-22 신설) - ContentGenerationPage.tsx와 같은 패턴의
 * 간단한 관리 도구다. 등록하면 그 즉시 kind에 맞는 알림설정(공지사항 알림/마케팅 알림)을
 * 켜둔 사용자 전체에게 푸시가 나간다 - "공지사항"(NoticePage.tsx) 목록에도 바로 반영된다. */
export default function NoticeAdminPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<NoticeResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [kind, setKind] = useState<NoticeKind>("NOTICE");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    noticeApi
      .list()
      .then((feed) => setItems([...feed].reverse()))
      .catch(() => {
        // 목록 조회 실패는 조용히 빈 목록으로 시작한다 - 등록 자체는 계속 가능해야 하므로.
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      const created = await noticeApi.create({ kind, title, body });
      setItems((prev) => [created, ...prev]);
      setTitle("");
      setBody("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "등록 중 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
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

        <PageTitle icon={Megaphone} style={{ marginBottom: 12 }}>
          관리자 공지등록
        </PageTitle>
        <p style={{ color: pinkTheme.textMuted, fontSize: 13, marginTop: 4 }}>
          등록하면 해당 알림을 켜둔 사용자 전체에게 즉시 푸시가 발송돼요.
        </p>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 16 }}
        >
          <div style={{ display: "flex", gap: 8 }}>
            {(["NOTICE", "MARKETING"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setKind(option)}
                style={{
                  flex: 1,
                  padding: "10px 0",
                  borderRadius: 10,
                  border: `1px solid ${kind === option ? pinkTheme.primary : pinkTheme.border}`,
                  background: kind === option ? pinkTheme.primarySoft : pinkTheme.cardBg,
                  color: kind === option ? pinkTheme.primary : pinkTheme.textMuted,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                {option === "NOTICE" ? "공지사항" : "마케팅"}
              </button>
            ))}
          </div>

          <input
            type="text"
            placeholder="제목"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            style={{
              padding: "12px 14px",
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 10,
              fontSize: 14,
            }}
          />
          <textarea
            placeholder="본문"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            required
            rows={6}
            style={{
              padding: "12px 14px",
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 10,
              fontSize: 14,
              fontFamily: "inherit",
              resize: "vertical",
            }}
          />

          <button
            type="submit"
            disabled={isSaving}
            style={{
              padding: "14px 16px",
              border: "none",
              borderRadius: 10,
              background: isSaving ? pinkTheme.primarySoft : pinkTheme.primary,
              color: "#fff",
              fontWeight: 700,
              cursor: isSaving ? "not-allowed" : "pointer",
            }}
          >
            {isSaving ? "등록 중..." : "등록하기"}
          </button>
        </form>

        {error && <p style={{ color: pinkTheme.danger, fontSize: 14, marginTop: 12 }}>{error}</p>}

        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 20 }}>
          {isLoading && (
            <p style={{ color: pinkTheme.textMuted, fontSize: 13, textAlign: "center" }}>
              불러오는 중...
            </p>
          )}
          {!isLoading && items.length === 0 && (
            <p style={{ color: pinkTheme.textMuted, fontSize: 13, textAlign: "center" }}>
              아직 등록된 공지가 없어요.
            </p>
          )}
          {items.map((item) => (
            <div
              key={item.id}
              style={{
                background: pinkTheme.cardBg,
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: 16,
                padding: 18,
                boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
              }}
            >
              <span style={{ fontSize: 13, color: pinkTheme.textMuted }}>
                {item.kind === "NOTICE" ? "공지사항" : "마케팅"} · {item.created_at.slice(0, 10)}
              </span>
              <p
                style={{
                  color: pinkTheme.text,
                  fontSize: 14,
                  fontWeight: 700,
                  margin: "6px 0 4px",
                }}
              >
                {item.title}
              </p>
              <p
                style={{
                  color: pinkTheme.textMuted,
                  fontSize: 13,
                  margin: 0,
                  whiteSpace: "pre-line",
                }}
              >
                {item.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
