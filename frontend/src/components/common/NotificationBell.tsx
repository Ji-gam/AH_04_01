import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { notificationInboxApi } from "../../api/notificationInboxApi";
import type { NotificationLogItemResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme as t } from "../../theme/pinkTheme";

function formatSentAt(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** 상단 네비 🔔 알림함(2026-07-26) - 복약알림/공지/가족알림/주간·월간 리포트/부작용안내 등
 * 발송된 모든 알림을 내용까지 눌러서 볼 수 있게 한다(NotificationLog, 홈 화면이 아니라 어느
 * 화면에서든 Layout 상단바에 항상 떠 있다). 목록은 열 때마다 새로 불러오고, 연 직후에는
 * 전체를 읽음 처리해 배지 숫자를 지운다(목록 자체는 그대로 남아 계속 볼 수 있다). */
export default function NotificationBell() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState<NotificationLogItemResult[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user) {
      setItems([]);
      setUnreadCount(0);
      return;
    }
    notificationInboxApi
      .list()
      .then((result) => {
        setItems(result.items);
        setUnreadCount(result.unread_count);
      })
      .catch(() => {
        // 알림함은 부가 기능이라 실패해도 조용히 무시한다 - 배지/목록이 그냥 비어 보인다.
      });
  }, [user]);

  function handleToggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setLoading(true);
    notificationInboxApi
      .list()
      .then((result) => {
        setItems(result.items);
        setUnreadCount(result.unread_count);
        if (result.unread_count > 0) {
          notificationInboxApi
            .markAllRead()
            .then(() => setUnreadCount(0))
            .catch(() => {
              // 읽음 처리가 실패해도 목록은 이미 보여줬으니 조용히 무시한다.
            });
        }
      })
      .catch(() => {
        // 무시 - 목록이 비어있는 채로 패널만 열린다.
      })
      .finally(() => setLoading(false));
  }

  if (!user) return null;

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        aria-label="알림함 열기"
        onClick={handleToggle}
        style={{
          position: "relative",
          border: "none",
          background: "none",
          color: t.text,
          fontSize: 19,
          lineHeight: 1,
          padding: 4,
          cursor: "pointer",
        }}
      >
        🔔
        {unreadCount > 0 && (
          <span
            aria-hidden
            style={{
              position: "absolute",
              top: -2,
              right: -2,
              minWidth: 15,
              height: 15,
              borderRadius: 999,
              background: t.primary,
              color: "#fff",
              fontSize: 9.5,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 3px",
            }}
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <>
          {/* 바깥 영역 클릭 시 닫기 - 어둡게 가리지 않는 투명 오버레이 */}
          <div
            onClick={() => setOpen(false)}
            style={{ position: "fixed", inset: 0, zIndex: 900 }}
          />
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 8px)",
              right: 0,
              width: 320,
              maxWidth: "calc(100vw - 32px)",
              maxHeight: "70vh",
              overflowY: "auto",
              background: t.cardBg,
              border: `1px solid ${t.border}`,
              borderRadius: 16,
              boxShadow: "0 8px 24px rgba(255, 111, 145, 0.18)",
              zIndex: 901,
            }}
          >
            <p
              style={{
                margin: 0,
                padding: "14px 16px 10px",
                fontSize: 14,
                fontWeight: 700,
                color: t.text,
                borderBottom: `1px solid ${t.border}`,
              }}
            >
              🔔 알림
            </p>

            {loading && (
              <p style={{ margin: 0, padding: "20px 16px", fontSize: 13, color: t.textMuted }}>
                불러오는 중...
              </p>
            )}

            {!loading && items.length === 0 && (
              <p
                style={{
                  margin: 0,
                  padding: "28px 16px",
                  fontSize: 13,
                  color: t.textMuted,
                  textAlign: "center",
                }}
              >
                아직 도착한 알림이 없어요.
              </p>
            )}

            {!loading &&
              items.map((item) => (
                <div
                  key={item.id}
                  role={item.link_url ? "button" : undefined}
                  tabIndex={item.link_url ? 0 : undefined}
                  onClick={() => {
                    if (!item.link_url) return;
                    setOpen(false);
                    navigate(item.link_url);
                  }}
                  style={{
                    padding: "12px 16px",
                    borderBottom: `1px solid ${t.border}`,
                    cursor: item.link_url ? "pointer" : "default",
                  }}
                >
                  <p style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: t.text }}>
                    {item.title}
                  </p>
                  <p
                    style={{
                      margin: "4px 0 0",
                      fontSize: 12.5,
                      color: t.textMuted,
                      lineHeight: 1.5,
                      whiteSpace: "pre-line",
                    }}
                  >
                    {item.body}
                  </p>
                  <p style={{ margin: "6px 0 0", fontSize: 11, color: t.textMuted }}>
                    {formatSentAt(item.created_at)}
                  </p>
                </div>
              ))}
          </div>
        </>
      )}
    </div>
  );
}
