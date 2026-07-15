import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import DisclaimerBanner from "../../components/common/DisclaimerBanner";
import { useChatStream } from "../../hooks/useChatStream";
import { pinkTheme } from "../../theme/pinkTheme";

export default function ChatPage() {
  // 홈 화면 "AI 건강 상담" 입력창에서 넘어온 질문을 도착하자마자 자동으로 전송한다.
  const location = useLocation();
  const navigate = useNavigate();
  const autoSentRef = useRef(false);
  // 최초 마운트 시점의 location.state만 본다(전송 직후 state를 지우므로 리렌더 때는 이미 없음) -
  // 자동 전송이 예정돼 있으면 "마지막 상담 복원"을 건너뛰어야 질문이 화면에 바로 보인다.
  const hasAutoMessageRef = useRef(
    Boolean((location.state as { autoMessage?: string } | null)?.autoMessage),
  );

  const {
    messages,
    sendMessage,
    isStreaming,
    sessionList,
    currentSessionId,
    selectSession,
    startNewChat,
  } = useChatStream({ skipRestoreOnMount: hasAutoMessageRef.current });
  const [input, setInput] = useState("");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  useEffect(() => {
    const autoMessage = (location.state as { autoMessage?: string } | null)?.autoMessage;
    if (autoMessage && !autoSentRef.current) {
      autoSentRef.current = true;
      void sendMessage(autoMessage);
      navigate(location.pathname, { replace: true, state: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  async function handleSend() {
    const text = input;
    setInput("");
    await sendMessage(text);
  }

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(
        d.getMinutes(),
      ).padStart(2, "0")}`;
    } catch {
      return isoString;
    }
  };

  return (
    <div
      style={{
        display: "flex",
        height: "100%",
        overflow: "hidden",
        background: pinkTheme.pageBg,
      }}
    >
      {/* 1. 데스크톱 사이드바 */}
      <div
        className="chat-sidebar"
        style={{
          width: "250px",
          borderRight: `1px solid ${pinkTheme.border}`,
          background: pinkTheme.cardBg,
          display: "flex",
          flexDirection: "column",
          height: "100%",
          padding: "12px",
          boxSizing: "border-box",
        }}
      >
        <button
          onClick={startNewChat}
          style={{
            background: pinkTheme.primary,
            color: "#fff",
            border: "none",
            borderRadius: 10,
            padding: "11px",
            fontSize: "14px",
            fontWeight: 700,
            cursor: "pointer",
            marginBottom: "15px",
          }}
        >
          + 새로운 상담 시작
        </button>

        <h3 style={{ fontSize: "12px", marginBottom: "10px", color: pinkTheme.textMuted }}>
          이전 상담 기록
        </h3>

        <div
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "6px",
          }}
        >
          {sessionList.map((session) => {
            const isActive = String(session.id) === currentSessionId;
            return (
              <div
                key={session.id}
                onClick={() => void selectSession(String(session.id))}
                style={{
                  padding: "10px 12px",
                  borderRadius: 10,
                  border: isActive
                    ? `1.5px solid ${pinkTheme.primary}`
                    : `1px solid ${pinkTheme.border}`,
                  background: isActive ? pinkTheme.primarySoft : pinkTheme.cardBg,
                  color: pinkTheme.text,
                  fontWeight: isActive ? 700 : 400,
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  gap: "2px",
                }}
                className="session-item"
              >
                <span style={{ fontSize: "13px" }}>상담 #{session.id}</span>
                <span style={{ fontSize: "11px", color: pinkTheme.textMuted }}>
                  {formatDate(session.created_at)}
                </span>
              </div>
            );
          })}
          {sessionList.length === 0 && (
            <p style={{ fontSize: "12px", color: pinkTheme.textMuted, textAlign: "center" }}>
              이전 상담이 없습니다.
            </p>
          )}
        </div>
      </div>

      {/* 2. 모바일용 사이드바 Drawer */}
      {isMobileMenuOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100vw",
            height: "100vh",
            background: "rgba(90, 74, 78, 0.45)",
            zIndex: 1000,
            display: "flex",
          }}
          onClick={() => setIsMobileMenuOpen(false)}
        >
          <div
            style={{
              width: "250px",
              background: pinkTheme.cardBg,
              height: "100%",
              padding: "15px",
              boxSizing: "border-box",
              display: "flex",
              flexDirection: "column",
              borderRight: `1px solid ${pinkTheme.border}`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "15px" }}>
              <strong style={{ color: pinkTheme.text }}>메뉴</strong>
              <button
                onClick={() => setIsMobileMenuOpen(false)}
                style={{
                  border: `1px solid ${pinkTheme.border}`,
                  borderRadius: 8,
                  background: pinkTheme.cardBg,
                  color: pinkTheme.textMuted,
                  cursor: "pointer",
                  padding: "2px 10px",
                }}
              >
                닫기
              </button>
            </div>

            <button
              onClick={() => {
                startNewChat();
                setIsMobileMenuOpen(false);
              }}
              style={{
                background: pinkTheme.primary,
                color: "#fff",
                border: "none",
                borderRadius: 10,
                padding: "11px",
                fontWeight: 700,
                cursor: "pointer",
                marginBottom: "15px",
              }}
            >
              + 새로운 상담 시작
            </button>

            <h3 style={{ fontSize: "12px", marginBottom: "10px", color: pinkTheme.textMuted }}>
              이전 상담 기록
            </h3>
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: "6px",
              }}
            >
              {sessionList.map((session) => {
                const isActive = String(session.id) === currentSessionId;
                return (
                  <div
                    key={session.id}
                    onClick={() => {
                      void selectSession(String(session.id));
                      setIsMobileMenuOpen(false);
                    }}
                    style={{
                      padding: "10px 12px",
                      borderRadius: 10,
                      border: isActive
                        ? `1.5px solid ${pinkTheme.primary}`
                        : `1px solid ${pinkTheme.border}`,
                      background: isActive ? pinkTheme.primarySoft : pinkTheme.cardBg,
                      color: pinkTheme.text,
                      fontWeight: isActive ? 700 : 400,
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      gap: "2px",
                    }}
                  >
                    <span style={{ fontSize: "13px" }}>상담 #{session.id}</span>
                    <span style={{ fontSize: "11px", color: pinkTheme.textMuted }}>
                      {formatDate(session.created_at)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* 3. 우측 채팅 메시지 메인창 */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          height: "100%",
          background: pinkTheme.pageBg,
          position: "relative",
        }}
      >
        {/* 상단 헤더 영역 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "12px 14px",
            borderBottom: `1px solid ${pinkTheme.border}`,
            background: pinkTheme.cardBg,
          }}
        >
          <button
            className="menu-toggle-btn"
            onClick={() => setIsMobileMenuOpen(true)}
            style={{
              background: pinkTheme.cardBg,
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 8,
              color: pinkTheme.text,
              cursor: "pointer",
              display: "none",
              padding: "4px 10px",
            }}
          >
            메뉴
          </button>
          <h3 style={{ margin: 0, fontSize: 15, color: pinkTheme.primary }}>
            💬 {currentSessionId ? `상담 (#${currentSessionId})` : "신규 상담방"}
          </h3>
        </div>

        <DisclaimerBanner />

        {/* 메시지 영역 */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "14px",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}
        >
          {messages.map((m, i) => {
            const isUser = m.role === "user";
            return (
              <div
                key={i}
                style={{
                  alignSelf: isUser ? "flex-end" : "flex-start",
                  marginLeft: isUser ? "auto" : "0",
                  marginRight: isUser ? "0" : "auto",
                  maxWidth: "80%",
                  textAlign: isUser ? "right" : "left",
                }}
              >
                <div
                  style={{
                    display: "inline-block",
                    padding: "10px 14px",
                    border: isUser ? "none" : `1px solid ${pinkTheme.border}`,
                    borderRadius: isUser ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
                    background: isUser ? pinkTheme.primary : pinkTheme.cardBg,
                    color: isUser ? "#fff" : pinkTheme.text,
                    fontSize: "13px",
                    whiteSpace: "pre-wrap",
                    textAlign: "left",
                    boxShadow: "0 1px 4px rgba(255, 111, 145, 0.08)",
                  }}
                >
                  {m.content}
                </div>
                {m.disclaimer && (
                  <span
                    style={{
                      display: "block",
                      fontSize: "11px",
                      color: pinkTheme.danger,
                      marginTop: "4px",
                      maxWidth: "100%",
                      textAlign: "left",
                    }}
                  >
                    ⚠ {m.disclaimer}
                  </span>
                )}
              </div>
            );
          })}
          {isStreaming && (
            <div
              style={{
                alignSelf: "flex-start",
                color: pinkTheme.textMuted,
                fontSize: "12px",
              }}
            >
              <span>답변 작성 중...</span>
            </div>
          )}
          {messages.length === 0 && (
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                color: pinkTheme.textMuted,
                gap: "5px",
              }}
            >
              <p style={{ margin: 0, fontSize: "26px" }}>💬</p>
              <p style={{ margin: 0, fontSize: "14px" }}>
                궁금한 약 성분이나 DUR 기준을 물어보세요.
              </p>
            </div>
          )}
        </div>

        {/* 하단 입력 폼 */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void handleSend();
          }}
          style={{
            padding: "12px",
            background: pinkTheme.cardBg,
            borderTop: `1px solid ${pinkTheme.border}`,
            display: "flex",
            gap: "8px",
            boxSizing: "border-box",
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="궁금한 점을 물어보세요"
            disabled={isStreaming}
            style={{
              flex: 1,
              padding: "11px 13px",
              fontSize: "13px",
              border: `1px solid ${pinkTheme.border}`,
              borderRadius: 10,
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            style={{
              padding: "0 18px",
              fontSize: "13px",
              fontWeight: 700,
              background: isStreaming || !input.trim() ? pinkTheme.primarySoft : pinkTheme.primary,
              color: isStreaming || !input.trim() ? pinkTheme.textMuted : "#fff",
              border: "none",
              borderRadius: 10,
              cursor: isStreaming || !input.trim() ? "default" : "pointer",
            }}
          >
            전송
          </button>
        </form>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .chat-sidebar {
            display: none !important;
          }
          .menu-toggle-btn {
            display: block !important;
          }
        }
      `}</style>
    </div>
  );
}
