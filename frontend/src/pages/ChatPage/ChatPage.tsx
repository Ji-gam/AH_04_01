import { useState } from "react";

import DisclaimerBanner from "../../components/common/DisclaimerBanner";
import { useChatStream } from "../../hooks/useChatStream";

export default function ChatPage() {
  const {
    messages,
    sendMessage,
    isStreaming,
    sessionList,
    currentSessionId,
    selectSession,
    startNewChat,
  } = useChatStream();
  const [input, setInput] = useState("");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

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
        fontFamily: "monospace",
      }}
    >
      {/* 1. 데스크톱 사이드바 */}
      <div
        className="chat-sidebar"
        style={{
          width: "250px",
          borderRight: "1px solid black",
          display: "flex",
          flexDirection: "column",
          height: "100%",
          padding: "10px",
          boxSizing: "border-box",
        }}
      >
        <button
          onClick={startNewChat}
          style={{
            background: "none",
            color: "black",
            border: "1px solid black",
            padding: "10px",
            fontSize: "14px",
            fontWeight: "bold",
            cursor: "pointer",
            marginBottom: "15px",
          }}
        >
          + 새로운 상담 시작
        </button>

        <h3 style={{ fontSize: "12px", marginBottom: "10px" }}>이전 상담 기록</h3>

        <div
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "5px",
          }}
        >
          {sessionList.map((session) => {
            const isActive = String(session.id) === currentSessionId;
            return (
              <div
                key={session.id}
                onClick={() => void selectSession(String(session.id))}
                style={{
                  padding: "10px",
                  border: isActive ? "2px solid black" : "1px solid gray",
                  color: "black",
                  fontWeight: isActive ? "bold" : "normal",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  gap: "2px",
                }}
                className="session-item"
              >
                <span style={{ fontSize: "13px" }}>상담 #{session.id}</span>
                <span style={{ fontSize: "11px", color: "gray" }}>
                  {formatDate(session.created_at)}
                </span>
              </div>
            );
          })}
          {sessionList.length === 0 && (
            <p style={{ fontSize: "12px", color: "gray", textAlign: "center" }}>
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
            background: "rgba(0, 0, 0, 0.5)",
            zIndex: 1000,
            display: "flex",
          }}
          onClick={() => setIsMobileMenuOpen(false)}
        >
          <div
            style={{
              width: "250px",
              background: "white",
              height: "100%",
              padding: "15px",
              boxSizing: "border-box",
              display: "flex",
              flexDirection: "column",
              borderRight: "2px solid black",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "15px" }}>
              <strong>메뉴</strong>
              <button
                onClick={() => setIsMobileMenuOpen(false)}
                style={{ border: "1px solid black", background: "none" }}
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
                background: "none",
                border: "1px solid black",
                padding: "10px",
                fontWeight: "bold",
                marginBottom: "15px",
              }}
            >
              + 새로운 상담 시작
            </button>

            <h3 style={{ fontSize: "12px", marginBottom: "10px" }}>이전 상담 기록</h3>
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: "5px",
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
                      padding: "10px",
                      border: isActive ? "2px solid black" : "1px solid gray",
                      fontWeight: isActive ? "bold" : "normal",
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      gap: "2px",
                    }}
                  >
                    <span style={{ fontSize: "13px" }}>상담 #{session.id}</span>
                    <span style={{ fontSize: "11px", color: "gray" }}>
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
          background: "white",
          position: "relative",
        }}
      >
        {/* 상단 헤더 영역 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "10px",
            borderBottom: "1px solid black",
          }}
        >
          <button
            className="menu-toggle-btn"
            onClick={() => setIsMobileMenuOpen(true)}
            style={{
              background: "none",
              border: "1px solid black",
              cursor: "pointer",
              display: "none",
            }}
          >
            메뉴
          </button>
          <h3 style={{ margin: 0 }}>
            {currentSessionId ? `상담 (#${currentSessionId})` : "신규 상담방"}
          </h3>
        </div>

        <DisclaimerBanner />

        {/* 메시지 영역 */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "10px",
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
                    padding: "8px 12px",
                    border: "1px solid black",
                    background: isUser ? "#eee" : "none",
                    color: "black",
                    fontSize: "13px",
                    whiteSpace: "pre-wrap",
                    textAlign: "left",
                  }}
                >
                  {m.content}
                </div>
                {m.disclaimer && (
                  <span
                    style={{
                      display: "block",
                      fontSize: "11px",
                      color: "red",
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
                color: "gray",
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
                color: "gray",
                gap: "5px",
              }}
            >
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
            padding: "10px",
            background: "white",
            borderTop: "1px solid black",
            display: "flex",
            gap: "5px",
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
              padding: "10px",
              fontSize: "13px",
              border: "1px solid black",
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            style={{
              padding: "0 15px",
              fontSize: "13px",
              fontWeight: "bold",
              background: "none",
              color: "black",
              border: "1px solid black",
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
