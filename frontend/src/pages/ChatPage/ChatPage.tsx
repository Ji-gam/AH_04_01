import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useLocation, useNavigate } from "react-router-dom";

import DisclaimerBanner from "../../components/common/DisclaimerBanner";
import { useChatStream } from "../../hooks/useChatStream";
import { pinkTheme } from "../../theme/pinkTheme";

export default function ChatPage() {
  // 홈 화면 "AI 건강 상담" 입력창에서 넘어온 질문을 도착하자마자 자동으로 전송한다.
  const location = useLocation();
  const navigate = useNavigate();
  const autoSentRef = useRef(false);
  // 쿼리 파라미터(?autoMessage=...)는 알림의 액션 버튼(예: F-NTFY-5 "불편한 증상이
  // 있어요")이 service-worker의 clients.openWindow(url)로 열 때 쓴다 - 탭이 완전히
  // 닫혀있던 경우라 React Router의 location.state를 실어보낼 방법이 없기 때문이다.
  // in-app navigate(location.state)와 나란히 지원한다.
  const queryAutoMessageRef = useRef(new URLSearchParams(location.search).get("autoMessage"));
  // 최초 마운트 시점의 location.state/쿼리만 본다(전송 직후 지우므로 리렌더 때는 이미 없음) -
  // 자동 전송이 예정돼 있으면 "마지막 상담 복원"을 건너뛰어야 질문이 화면에 바로 보인다.
  const hasAutoMessageRef = useRef(
    Boolean((location.state as { autoMessage?: string } | null)?.autoMessage) ||
      Boolean(queryAutoMessageRef.current),
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
  // 출처 칩을 클릭해 연 메시지 인덱스 — 화면 중앙 모달로 해당 메시지의 출처 목록을 보여준다.
  const [sourcesModalIndex, setSourcesModalIndex] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // LLM 응답 스트리밍이 끝나면(true -> false) 바로 다음 질문을 이어 칠 수 있도록 입력란에
  // 포커스를 되돌린다.
  useEffect(() => {
    if (!isStreaming) {
      inputRef.current?.focus();
    }
  }, [isStreaming]);

  // 새 메시지가 추가되거나(질문 전송/답변 시작) 스트리밍 토큰이 이어 붙을 때마다, 지금
  // 입력 중이거나 답변 중인 말풍선이 항상 화면에 보이도록 맨 아래로 따라간다.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, isStreaming]);

  useEffect(() => {
    const autoMessage =
      (location.state as { autoMessage?: string } | null)?.autoMessage ??
      queryAutoMessageRef.current;
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
        height: "100%",
        overflow: "hidden",
        background: pinkTheme.pageBg,
        display: "flex",
        justifyContent: "center",
      }}
    >
      {/* 다른 화면들과 폭을 맞춘다(maxWidth: 480, margin: 0 auto 관례) - 챗 화면은 세로 꽉 채운
          플렉스 레이아웃이라 그 관례를 그대로 못 쓰고, height: 100%를 유지하는 안쪽 래퍼로 감싼다. */}
      <div
        style={{
          display: "flex",
          height: "100%",
          width: "100%",
          maxWidth: 480,
          overflow: "hidden",
          background: pinkTheme.pageBg,
        }}
      >
        {/* 상담 목록은 화면 크기와 무관하게 항상 메뉴 버튼으로 여는 Drawer 하나로 통일한다 —
            480px 폭 안에 사이드바를 상시 노출하면 채팅창이 너무 좁아져 글자가 세로로
            찌그러진다(2026-07-29 실측). */}
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
              <div
                style={{ display: "flex", justifyContent: "space-between", marginBottom: "15px" }}
              >
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
              type="button"
              onClick={() => navigate("/")}
              style={{
                background: "none",
                border: "none",
                color: pinkTheme.textMuted,
                padding: 0,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              ← 뒤로가기
            </button>
            <button
              onClick={() => setIsMobileMenuOpen(true)}
              style={{
                background: pinkTheme.cardBg,
                border: `1px solid ${pinkTheme.border}`,
                borderRadius: 8,
                color: pinkTheme.text,
                cursor: "pointer",
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
                    display: "flex",
                    flexDirection: "column",
                    alignItems: isUser ? "flex-end" : "flex-start",
                  }}
                >
                  {/* 말풍선 + 출처 칩을 한 행에 나란히 배치(칩은 말풍선 옆에 위치 고정) */}
                  <div
                    style={{
                      display: "flex",
                      flexDirection: isUser ? "row-reverse" : "row",
                      alignItems: "flex-end",
                      gap: "6px",
                    }}
                  >
                    <div
                      className="chat-bubble-content"
                      style={{
                        display: "inline-block",
                        padding: "10px 14px",
                        border: isUser ? "none" : `1px solid ${pinkTheme.border}`,
                        borderRadius: isUser ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
                        background: isUser ? pinkTheme.primary : pinkTheme.cardBg,
                        color: isUser ? "#fff" : pinkTheme.text,
                        fontSize: "13px",
                        textAlign: "left",
                        boxShadow: "0 1px 4px rgba(255, 111, 145, 0.08)",
                      }}
                    >
                      <ReactMarkdown>{m.content}</ReactMarkdown>
                    </div>
                    {m.sources && m.sources.length > 0 && (
                      <button
                        onClick={() => setSourcesModalIndex(i)}
                        style={{
                          flexShrink: 0,
                          fontSize: "11px",
                          padding: "3px 10px",
                          borderRadius: 999,
                          border: `1px solid ${pinkTheme.border}`,
                          background: pinkTheme.primarySoft,
                          color: pinkTheme.primary,
                          fontWeight: 700,
                          cursor: "pointer",
                          whiteSpace: "nowrap",
                        }}
                      >
                        📎 출처 {m.sources.length}
                      </button>
                    )}
                  </div>
                  {/* 면책 문구는 항상 말풍선 아래쪽에 고정 */}
                  {m.disclaimer && (
                    <span
                      style={{
                        display: "block",
                        fontSize: "11px",
                        color: pinkTheme.danger,
                        marginTop: "4px",
                        maxWidth: "100%",
                        textAlign: isUser ? "right" : "left",
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
            <div ref={messagesEndRef} />
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
              ref={inputRef}
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
                background:
                  isStreaming || !input.trim() ? pinkTheme.primarySoft : pinkTheme.primary,
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
      </div>

      {/* 출처 칩 클릭 시 화면 중앙에 뜨는 반응형 모달. 논문/PDF는 제목만, DUR(csv)은
          노출명만 각각 한 줄로 보여준다 — 항목당 표시 텍스트는 항상 sources[].name 하나뿐이라
          별도 분기 없이 단일 렌더링 경로로 두 요구사항을 동시에 만족한다. */}
      {sourcesModalIndex !== null && messages[sourcesModalIndex]?.sources && (
        <div
          onClick={() => setSourcesModalIndex(null)}
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100vw",
            height: "100vh",
            background: "rgba(90, 74, 78, 0.45)",
            zIndex: 2000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
            boxSizing: "border-box",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "min(90vw, 360px)",
              maxHeight: "70vh",
              overflowY: "auto",
              background: pinkTheme.cardBg,
              borderRadius: 14,
              border: `1px solid ${pinkTheme.border}`,
              boxShadow: "0 8px 28px rgba(90, 74, 78, 0.25)",
              padding: "14px 16px",
              boxSizing: "border-box",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "10px",
              }}
            >
              <strong style={{ fontSize: "13px", color: pinkTheme.text }}>참고 출처</strong>
              <button
                onClick={() => setSourcesModalIndex(null)}
                style={{
                  border: "none",
                  background: "transparent",
                  color: pinkTheme.textMuted,
                  fontSize: "16px",
                  lineHeight: 1,
                  cursor: "pointer",
                  padding: "2px 4px",
                }}
                aria-label="닫기"
              >
                ×
              </button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {messages[sourcesModalIndex]!.sources!.map((s, si) =>
                s.url ? (
                  <a
                    key={si}
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={s.name}
                    style={{
                      display: "block",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      fontSize: "12.5px",
                      color: pinkTheme.primary,
                      fontWeight: 600,
                      padding: "6px 8px",
                      borderRadius: 8,
                      border: `1px solid ${pinkTheme.border}`,
                    }}
                  >
                    {s.name}
                  </a>
                ) : (
                  <span
                    key={si}
                    title={s.name}
                    style={{
                      display: "block",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      fontSize: "12.5px",
                      color: pinkTheme.text,
                      padding: "6px 8px",
                      borderRadius: 8,
                      border: `1px solid ${pinkTheme.border}`,
                    }}
                  >
                    {s.name}
                  </span>
                ),
              )}
            </div>
          </div>
        </div>
      )}

      <style>{`
        .chat-bubble-content p {
          margin: 0;
        }
        .chat-bubble-content p + p {
          margin-top: 8px;
        }
        .chat-bubble-content ul,
        .chat-bubble-content ol {
          margin: 8px 0;
          padding-left: 20px;
        }
        .chat-bubble-content li + li {
          margin-top: 4px;
        }
      `}</style>
    </div>
  );
}
