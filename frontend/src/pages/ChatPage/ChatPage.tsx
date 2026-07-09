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

  // 날짜 변환용 포맷터
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
        fontFamily: "'Outfit', 'Inter', sans-serif",
      }}
    >
      {/* 1. 데스크톱 사이드바 */}
      <div
        className="chat-sidebar"
        style={{
          width: "280px",
          background: "rgba(30, 41, 59, 0.05)",
          borderRight: "1px solid rgba(226, 232, 240, 0.8)",
          display: "flex",
          flexDirection: "column",
          height: "100%",
          padding: "16px",
          boxSizing: "border-box",
          transition: "all 0.3s ease",
        }}
      >
        <button
          onClick={startNewChat}
          style={{
            background: "linear-gradient(135deg, #4f46e5, #06b6d4)",
            color: "white",
            border: "none",
            borderRadius: "12px",
            padding: "12px 16px",
            fontSize: "15px",
            fontWeight: "600",
            cursor: "pointer",
            marginBottom: "20px",
            boxShadow: "0 4px 12px rgba(79, 70, 229, 0.3)",
            transition: "transform 0.2s ease, opacity 0.2s ease",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
          onMouseOver={(e) => (e.currentTarget.style.transform = "translateY(-1px)")}
          onMouseOut={(e) => (e.currentTarget.style.transform = "translateY(0)")}
        >
          <span>+</span> 새로운 상담 시작
        </button>

        <h3
          style={{
            fontSize: "12px",
            textTransform: "uppercase",
            color: "#64748b",
            letterSpacing: "1px",
            marginBottom: "12px",
            fontWeight: "700",
          }}
        >
          이전 상담 기록
        </h3>

        <div
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          {sessionList.map((session) => {
            const isActive = String(session.id) === currentSessionId;
            return (
              <div
                key={session.id}
                onClick={() => void selectSession(String(session.id))}
                style={{
                  padding: "12px 16px",
                  borderRadius: "10px",
                  background: isActive ? "rgba(79, 70, 229, 0.1)" : "transparent",
                  border: isActive ? "1px solid rgba(79, 70, 229, 0.3)" : "1px solid transparent",
                  color: isActive ? "#4f46e5" : "#334155",
                  fontWeight: isActive ? "600" : "500",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                }}
                className="session-item"
              >
                <span style={{ fontSize: "14px" }}>상담 #{session.id}</span>
                <span
                  style={{
                    fontSize: "11px",
                    color: isActive ? "rgba(79, 70, 229, 0.7)" : "#94a3b8",
                  }}
                >
                  {formatDate(session.created_at)}
                </span>
              </div>
            );
          })}
          {sessionList.length === 0 && (
            <p
              style={{
                fontSize: "13px",
                color: "#94a3b8",
                textAlign: "center",
                marginTop: "20px",
              }}
            >
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
            background: "rgba(15, 23, 42, 0.4)",
            backdropFilter: "blur(4px)",
            zIndex: 1000,
            display: "flex",
          }}
          onClick={() => setIsMobileMenuOpen(false)}
        >
          <div
            style={{
              width: "280px",
              background: "white",
              height: "100%",
              padding: "20px 16px",
              boxSizing: "border-box",
              display: "flex",
              flexDirection: "column",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <span style={{ fontWeight: "700", color: "#1e293b" }}>메뉴</span>
              <button
                onClick={() => setIsMobileMenuOpen(false)}
                style={{
                  background: "none",
                  border: "none",
                  fontSize: "20px",
                  cursor: "pointer",
                  color: "#64748b",
                }}
              >
                ×
              </button>
            </div>

            <button
              onClick={() => {
                startNewChat();
                setIsMobileMenuOpen(false);
              }}
              style={{
                background: "linear-gradient(135deg, #4f46e5, #06b6d4)",
                color: "white",
                border: "none",
                borderRadius: "12px",
                padding: "12px 16px",
                fontSize: "15px",
                fontWeight: "600",
                cursor: "pointer",
                marginBottom: "20px",
                boxShadow: "0 4px 12px rgba(79, 70, 229, 0.3)",
              }}
            >
              + 새로운 상담 시작
            </button>

            <h3
              style={{
                fontSize: "11px",
                textTransform: "uppercase",
                color: "#64748b",
                letterSpacing: "1px",
                marginBottom: "12px",
              }}
            >
              이전 상담 기록
            </h3>
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: "8px",
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
                      padding: "12px 16px",
                      borderRadius: "10px",
                      background: isActive ? "rgba(79, 70, 229, 0.1)" : "transparent",
                      border: isActive
                        ? "1px solid rgba(79, 70, 229, 0.3)"
                        : "1px solid transparent",
                      color: isActive ? "#4f46e5" : "#334155",
                      fontWeight: isActive ? "600" : "500",
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      gap: "4px",
                    }}
                  >
                    <span style={{ fontSize: "14px" }}>상담 #{session.id}</span>
                    <span
                      style={{
                        fontSize: "11px",
                        color: isActive ? "rgba(79, 70, 229, 0.7)" : "#94a3b8",
                      }}
                    >
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
          background: "#ffffff",
          position: "relative",
        }}
      >
        {/* 상단 헤더 영역 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            padding: "16px 20px",
            borderBottom: "1px solid rgba(226, 232, 240, 0.8)",
            background: "rgba(255, 255, 255, 0.8)",
            backdropFilter: "blur(8px)",
          }}
        >
          <button
            className="menu-toggle-btn"
            onClick={() => setIsMobileMenuOpen(true)}
            style={{
              background: "none",
              border: "none",
              fontSize: "20px",
              cursor: "pointer",
              padding: "4px",
              color: "#334155",
              display: "none",
            }}
          >
            ☰
          </button>
          <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#1e293b", margin: 0 }}>
            {currentSessionId ? `의약성분 상담 (#${currentSessionId})` : "신규 상담방"}
          </h2>
        </div>

        <DisclaimerBanner />

        {/* 메시지 영역 */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px",
            display: "flex",
            flexDirection: "column",
            gap: "16px",
          }}
        >
          {messages.map((m, i) => {
            const isUser = m.role === "user";
            return (
              <div
                key={i}
                style={{
                  alignSelf: isUser ? "flex-end" : "flex-start",
                  maxWidth: "75%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: isUser ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    padding: "12px 16px",
                    borderRadius: isUser ? "16px 16px 0 16px" : "16px 16px 16px 0",
                    background: isUser ? "#4f46e5" : "rgba(241, 245, 249, 0.9)",
                    color: isUser ? "#ffffff" : "#1e293b",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.02)",
                    lineHeight: "1.5",
                    fontSize: "15px",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {m.content}
                </div>
                {m.disclaimer && (
                  <span
                    style={{
                      fontSize: "11px",
                      color: "#ef4444",
                      marginTop: "6px",
                      maxWidth: "90%",
                      lineHeight: "1.4",
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
                display: "flex",
                alignItems: "center",
                gap: "8px",
                color: "#64748b",
                fontSize: "14px",
              }}
            >
              <span className="dot-pulse">답변 작성 중...</span>
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
                color: "#94a3b8",
                gap: "12px",
              }}
            >
              <div style={{ fontSize: "40px" }}>💬</div>
              <p style={{ margin: 0, fontSize: "14px" }}>
                궁금한 약 성분이나 DUR 기준을 편하게 여쭤보세요.
              </p>
              <p style={{ margin: 0, fontSize: "12px", opacity: 0.7 }}>
                예: "졸피뎀의 최대 투여 기간이 어떻게 되나요?"
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
            padding: "16px 20px",
            background: "#ffffff",
            borderTop: "1px solid rgba(226, 232, 240, 0.8)",
            display: "flex",
            gap: "10px",
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
              padding: "14px 18px",
              fontSize: "15px",
              border: "1px solid #cbd5e1",
              borderRadius: "14px",
              outline: "none",
              transition: "border-color 0.2s",
              boxShadow: "inset 0 1px 2px rgba(0,0,0,0.02)",
            }}
            onFocus={(e) => (e.target.style.borderColor = "#4f46e5")}
            onBlur={(e) => (e.target.style.borderColor = "#cbd5e1")}
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            style={{
              padding: "0 24px",
              fontSize: "15px",
              fontWeight: "600",
              background:
                isStreaming || !input.trim()
                  ? "#cbd5e1"
                  : "linear-gradient(135deg, #4f46e5, #0b0f19)",
              color: "#ffffff",
              border: "none",
              borderRadius: "14px",
              cursor: isStreaming || !input.trim() ? "default" : "pointer",
              transition: "opacity 0.2s",
            }}
          >
            전송
          </button>
        </form>
      </div>

      {/* 미디어 쿼리 주입 */}
      <style>{`
        @media (max-width: 768px) {
          .chat-sidebar {
            display: none !important;
          }
          .menu-toggle-btn {
            display: block !important;
          }
        }
        .session-item:hover {
          background: rgba(79, 70, 229, 0.05) !important;
        }
      `}</style>
    </div>
  );
}
