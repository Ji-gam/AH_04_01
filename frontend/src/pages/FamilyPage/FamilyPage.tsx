import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  familyApi,
  type FamilyInviteCode,
  type FamilyLinkItem,
  type FamilyMembersResult,
} from "../../api/familyApi";
import { pinkTheme } from "../../theme/pinkTheme";

const cardStyle: React.CSSProperties = {
  background: pinkTheme.cardBg,
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: 16,
  padding: "16px",
  boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
};

const inputStyle: React.CSSProperties = {
  padding: "12px 14px",
  border: `1px solid ${pinkTheme.border}`,
  borderRadius: "10px",
  fontSize: "14px",
  outline: "none",
};

const primaryButtonStyle: React.CSSProperties = {
  padding: "12px",
  border: "none",
  borderRadius: "10px",
  background: pinkTheme.primary,
  color: "#fff",
  fontWeight: 600,
  cursor: "pointer",
};

const emptyRowStyle: React.CSSProperties = { margin: 0, fontSize: 13, color: pinkTheme.textMuted };

function LinkRow({ item, right }: { item: FamilyLinkItem; right?: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        border: `1px solid ${pinkTheme.border}`,
        borderRadius: 10,
        padding: "10px 12px",
        gap: 8,
      }}
    >
      <span style={{ fontSize: 14, color: pinkTheme.text }}>
        {item.name} <span style={{ color: pinkTheme.textMuted }}>({item.relation_label})</span>
      </span>
      {right}
    </div>
  );
}

/** 더보기 > 가족관리. 연로한 부모님 등 가족 구성원을 "내가 보호자"인 관계로 연결한다.
 * [승인 플로우] 이메일만 알면 요청은 보낼 수 있지만, 상대방이 "수락"해야 실제로 연결되고
 * 그때부터 약 등록(더보기 > 약 등록) 시 "나 or 이 가족 구성원" 중 누구 몫으로 등록할지 고를 수
 * 있게 된다. 아직 푸시 알림 인프라가 없어서, 받은 요청은 이 화면(또는 홈 화면)을 열 때(또는
 * 새로고침) 보인다 - 실시간 팝업 알림은 아니다.
 * [초대코드] 이메일 요청과 별개로, 초대코드 경로도 같이 제공한다(카카오 임시 가입 계정처럼
 * 이메일로 못 찾는 경우의 대안). 코드는 발급 즉시 30분 유효/1회용이고, 입력하는 순간 승인
 * 절차 없이 바로 연결된다(코드를 안다는 것 자체가 이미 상호 동의로 간주).
 * 확인/미루기를 양쪽 화면에서 동기화하는 기능은 다음 PR에서 다룬다. */
export default function FamilyPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const cameFromMore = (location.state as { from?: string } | null)?.from === "more";
  const [data, setData] = useState<FamilyMembersResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // 연결 방식 - 이메일 요청(승인 필요) or 초대코드(즉시 연결). 카카오는 지금 임시로 실이메일이
  // 아닌 더미 이메일(kakao_xxx@social.local)만 있어서, 그 계정은 이메일 방식으로 못 찾는다 -
  // 초대코드가 그 대안이다(나중에 카카오 비즈앱 전환해서 실이메일을 받게 되면 이메일 방식도
  // 그대로 다시 쓸 수 있으니, 두 경로를 계속 같이 제공한다).
  const [linkMethod, setLinkMethod] = useState<"email" | "code">("email");

  const [email, setEmail] = useState("");
  const [relationLabel, setRelationLabel] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [isLinking, setIsLinking] = useState(false);

  // 초대코드 발급(보호자 쪽) - 코드는 승인 절차 없이 즉시 연결되므로 만료시간을 짧게(30분) 둔다.
  const [issueRelationLabel, setIssueRelationLabel] = useState("");
  const [issuedCode, setIssuedCode] = useState<FamilyInviteCode | null>(null);
  const [issueError, setIssueError] = useState<string | null>(null);
  const [isIssuing, setIsIssuing] = useState(false);

  // 초대코드 입력(피보호자 쪽) - 입력하는 순간 바로 연결된다(승인 절차 없음).
  const [redeemCode, setRedeemCode] = useState("");
  const [redeemError, setRedeemError] = useState<string | null>(null);
  const [isRedeeming, setIsRedeeming] = useState(false);

  async function load() {
    setLoading(true);
    setLoadError(null);
    try {
      setData(await familyApi.list());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "가족 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleRequestLink(e: FormEvent) {
    e.preventDefault();
    setLinkError(null);
    setIsLinking(true);
    try {
      await familyApi.requestLink(email.trim(), relationLabel.trim());
      setEmail("");
      setRelationLabel("");
      await load();
    } catch (err) {
      setLinkError(err instanceof Error ? err.message : "가족 연결 요청에 실패했습니다.");
    } finally {
      setIsLinking(false);
    }
  }

  async function handleAccept(linkId: number) {
    try {
      await familyApi.accept(linkId);
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "수락에 실패했습니다.");
    }
  }

  async function handleReject(linkId: number) {
    if (!window.confirm("이 연결 요청을 거절할까요?")) return;
    try {
      await familyApi.reject(linkId);
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "거절에 실패했습니다.");
    }
  }

  async function handleUnlink(linkId: number) {
    if (!window.confirm("이 가족 연결(또는 대기중인 요청)을 해제할까요?")) return;
    try {
      await familyApi.unlink(linkId);
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "연결 해제에 실패했습니다.");
    }
  }

  async function handleIssueCode(e: FormEvent) {
    e.preventDefault();
    setIssueError(null);
    setIsIssuing(true);
    try {
      setIssuedCode(await familyApi.createInviteCode(issueRelationLabel.trim()));
    } catch (err) {
      setIssueError(err instanceof Error ? err.message : "초대코드 발급에 실패했습니다.");
    } finally {
      setIsIssuing(false);
    }
  }

  async function handleRedeemCode(e: FormEvent) {
    e.preventDefault();
    setRedeemError(null);
    setIsRedeeming(true);
    try {
      await familyApi.redeemInviteCode(redeemCode.trim());
      setRedeemCode("");
      await load();
    } catch (err) {
      setRedeemError(err instanceof Error ? err.message : "초대코드 연결에 실패했습니다.");
    } finally {
      setIsRedeeming(false);
    }
  }

  async function handleCopyCode() {
    if (!issuedCode) return;
    try {
      await navigator.clipboard.writeText(issuedCode.code);
    } catch {
      // 클립보드 권한이 없는 브라우저도 있어서, 실패해도 화면에 이미 보이는 코드를 직접
      // 옮겨 적으면 되니 조용히 무시한다.
    }
  }

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div
        style={{
          maxWidth: 480,
          margin: "0 auto",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <button
          type="button"
          onClick={() => navigate(cameFromMore ? "/more" : "/")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            alignSelf: "flex-start",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          ← 뒤로가기
        </button>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: 0 }}>
          👨‍👩‍👧 가족관리
        </h1>
        <p style={{ margin: 0, fontSize: 13, color: pinkTheme.textMuted, lineHeight: 1.5 }}>
          부모님 등 가족 구성원을 이메일 또는 초대코드로 연결해요. 연결되면 약 등록할 때 "나 또는 이
          분" 중 누구 몫으로 등록할지 고를 수 있어요.
        </p>

        {/* 연결 방식 탭 */}
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            onClick={() => setLinkMethod("email")}
            style={{
              flex: 1,
              padding: "10px",
              border: `1px solid ${linkMethod === "email" ? pinkTheme.primary : pinkTheme.border}`,
              borderRadius: 10,
              background: linkMethod === "email" ? pinkTheme.primary : pinkTheme.cardBg,
              color: linkMethod === "email" ? "#fff" : pinkTheme.textMuted,
              fontWeight: 600,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            이메일로 요청
          </button>
          <button
            type="button"
            onClick={() => setLinkMethod("code")}
            style={{
              flex: 1,
              padding: "10px",
              border: `1px solid ${linkMethod === "code" ? pinkTheme.primary : pinkTheme.border}`,
              borderRadius: 10,
              background: linkMethod === "code" ? pinkTheme.primary : pinkTheme.cardBg,
              color: linkMethod === "code" ? "#fff" : pinkTheme.textMuted,
              fontWeight: 600,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            초대코드
          </button>
        </div>

        {linkMethod === "email" ? (
          /* 연결 요청 폼 (이메일) - 상대방이 수락해야 연결됨 */
          <form
            onSubmit={handleRequestLink}
            style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: 10 }}
          >
            <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text, fontSize: 14 }}>
              가족 구성원에게 연결 요청 보내기
            </p>
            <input
              type="email"
              name="family-email"
              autoComplete="off"
              placeholder="가족분의 가입 이메일"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={inputStyle}
              required
            />
            <input
              type="text"
              name="relation-label"
              autoComplete="off"
              placeholder="관계 (예: 어머니, 아버지, 할머니)"
              value={relationLabel}
              onChange={(e) => setRelationLabel(e.target.value)}
              style={inputStyle}
              maxLength={20}
              required
            />
            {linkError && (
              <p style={{ margin: 0, color: pinkTheme.danger, fontSize: 13 }}>{linkError}</p>
            )}
            <button type="submit" disabled={isLinking} style={primaryButtonStyle}>
              {isLinking ? "요청 보내는 중..." : "연결 요청 보내기"}
            </button>
          </form>
        ) : (
          <>
            {/* 초대코드 발급 (보호자 쪽 - 예: 자녀가 부모님께 드릴 코드를 만듦) */}
            <form
              onSubmit={handleIssueCode}
              style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: 10 }}
            >
              <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text, fontSize: 14 }}>
                초대코드 발급하기
              </p>
              <p style={{ margin: 0, fontSize: 12, color: pinkTheme.textMuted }}>
                이메일을 몰라도 돼요(카카오로 가입한 가족분께 추천). 코드를 발급해서 카톡/문자로
                전달하면, 상대방이 입력하는 즉시 연결돼요(30분 안에 사용, 1회용).
              </p>
              <input
                type="text"
                name="issue-relation-label"
                autoComplete="off"
                placeholder="관계 (예: 어머니, 아버지, 할머니)"
                value={issueRelationLabel}
                onChange={(e) => setIssueRelationLabel(e.target.value)}
                style={inputStyle}
                maxLength={20}
                required
              />
              {issueError && (
                <p style={{ margin: 0, color: pinkTheme.danger, fontSize: 13 }}>{issueError}</p>
              )}
              <button type="submit" disabled={isIssuing} style={primaryButtonStyle}>
                {isIssuing ? "발급 중..." : "코드 발급하기"}
              </button>
              {issuedCode && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: pinkTheme.primarySoft,
                    border: `1px solid ${pinkTheme.primary}`,
                    borderRadius: 10,
                    padding: "12px 14px",
                  }}
                >
                  <span
                    style={{
                      fontSize: 22,
                      fontWeight: 700,
                      letterSpacing: 3,
                      color: pinkTheme.primary,
                    }}
                  >
                    {issuedCode.code}
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyCode}
                    style={{
                      border: `1px solid ${pinkTheme.primary}`,
                      borderRadius: 8,
                      background: pinkTheme.cardBg,
                      color: pinkTheme.primary,
                      fontSize: 12,
                      fontWeight: 600,
                      padding: "6px 12px",
                      cursor: "pointer",
                    }}
                  >
                    복사
                  </button>
                </div>
              )}
            </form>

            {/* 초대코드 입력 (피보호자 쪽 - 받은 코드를 입력하면 즉시 연결) */}
            <form
              onSubmit={handleRedeemCode}
              style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: 10 }}
            >
              <p style={{ margin: 0, fontWeight: 600, color: pinkTheme.text, fontSize: 14 }}>
                받은 초대코드 입력하기
              </p>
              <input
                type="text"
                name="redeem-code"
                autoComplete="off"
                placeholder="6자리 코드 입력"
                value={redeemCode}
                onChange={(e) => setRedeemCode(e.target.value.toUpperCase())}
                style={{ ...inputStyle, letterSpacing: 3, fontWeight: 700, textAlign: "center" }}
                maxLength={6}
                required
              />
              {redeemError && (
                <p style={{ margin: 0, color: pinkTheme.danger, fontSize: 13 }}>{redeemError}</p>
              )}
              <button type="submit" disabled={isRedeeming} style={primaryButtonStyle}>
                {isRedeeming ? "연결하는 중..." : "코드 입력해서 바로 연결하기"}
              </button>
            </form>
          </>
        )}

        {loading && <p style={{ color: pinkTheme.textMuted, fontSize: 13 }}>불러오는 중...</p>}
        {loadError && <p style={{ color: pinkTheme.danger, fontSize: 13 }}>{loadError}</p>}

        {!loading && !loadError && data && (
          <>
            {/* 내가 받은 요청 - 여기가 "받는 사람 쪽 알림"에 해당하는 자리 (실시간 푸시는 아님) */}
            {data.as_member_pending.length > 0 && (
              <div style={{ ...cardStyle, borderColor: pinkTheme.primary }}>
                <p
                  style={{
                    margin: "0 0 10px",
                    fontWeight: 600,
                    color: pinkTheme.primary,
                    fontSize: 14,
                  }}
                >
                  🔔 받은 연결 요청
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {data.as_member_pending.map((item) => (
                    <LinkRow
                      key={item.link_id}
                      item={item}
                      right={
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            type="button"
                            onClick={() => handleAccept(item.link_id)}
                            style={{
                              border: "none",
                              borderRadius: 8,
                              background: pinkTheme.primary,
                              color: "#fff",
                              fontSize: 12,
                              fontWeight: 600,
                              padding: "6px 12px",
                              cursor: "pointer",
                            }}
                          >
                            수락
                          </button>
                          <button
                            type="button"
                            onClick={() => handleReject(item.link_id)}
                            style={{
                              border: `1px solid ${pinkTheme.border}`,
                              borderRadius: 8,
                              background: pinkTheme.cardBg,
                              color: pinkTheme.textMuted,
                              fontSize: 12,
                              padding: "6px 12px",
                              cursor: "pointer",
                            }}
                          >
                            거절
                          </button>
                        </div>
                      }
                    />
                  ))}
                </div>
              </div>
            )}

            {/* 내가 관리하는 가족 (수락됨) */}
            <div style={cardStyle}>
              <p
                style={{ margin: "0 0 10px", fontWeight: 600, color: pinkTheme.text, fontSize: 14 }}
              >
                내가 관리하는 가족
              </p>
              {data.as_guardian_accepted.length === 0 ? (
                <p style={emptyRowStyle}>아직 연결된 가족이 없어요.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {data.as_guardian_accepted.map((item) => (
                    <LinkRow
                      key={item.link_id}
                      item={item}
                      right={
                        <button
                          type="button"
                          onClick={() => handleUnlink(item.link_id)}
                          style={{
                            border: "none",
                            background: "none",
                            color: pinkTheme.textMuted,
                            fontSize: 12,
                            cursor: "pointer",
                            padding: "4px 8px",
                          }}
                        >
                          연결 해제
                        </button>
                      }
                    />
                  ))}
                </div>
              )}
            </div>

            {/* 내가 보낸, 아직 응답 대기중인 요청 */}
            {data.as_guardian_pending.length > 0 && (
              <div style={cardStyle}>
                <p
                  style={{
                    margin: "0 0 10px",
                    fontWeight: 600,
                    color: pinkTheme.text,
                    fontSize: 14,
                  }}
                >
                  응답 대기중인 요청
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {data.as_guardian_pending.map((item) => (
                    <LinkRow
                      key={item.link_id}
                      item={item}
                      right={
                        <button
                          type="button"
                          onClick={() => handleUnlink(item.link_id)}
                          style={{
                            border: "none",
                            background: "none",
                            color: pinkTheme.textMuted,
                            fontSize: 12,
                            cursor: "pointer",
                            padding: "4px 8px",
                          }}
                        >
                          요청 취소
                        </button>
                      }
                    />
                  ))}
                </div>
              </div>
            )}

            {/* 나를 관리하고 있는 가족 (투명성 확인용) */}
            {data.as_member_accepted.length > 0 && (
              <div style={cardStyle}>
                <p
                  style={{
                    margin: "0 0 10px",
                    fontWeight: 600,
                    color: pinkTheme.text,
                    fontSize: 14,
                  }}
                >
                  나를 관리하고 있는 가족
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {data.as_member_accepted.map((item) => (
                    <div
                      key={item.link_id}
                      style={{
                        border: `1px solid ${pinkTheme.border}`,
                        borderRadius: 10,
                        padding: "10px 12px",
                        fontSize: 14,
                        color: pinkTheme.text,
                      }}
                    >
                      {item.name}님이 나를 "{item.relation_label}"(으)로 등록해서 관리하고 있어요.
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
