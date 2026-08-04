import { Users } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { familyApi, type FamilyLinkItem, type FamilyMembersResult } from "../../api/familyApi";
import PageTitle from "../../components/common/PageTitle";
import { pinkTheme } from "../../theme/pinkTheme";

import QrScanner from "./components/QrScanner";

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
  fontWeight: 700,
  cursor: "pointer",
};

const emptyRowStyle: React.CSSProperties = { margin: 0, fontSize: 13, color: pinkTheme.textMuted };

// [관계 선택 목록] 자유 텍스트 입력 대신 드롭다운으로 통일 - 오탈자/표기 불일치("어머니" vs
// "엄마" 등) 방지, 연로하신 분들도 타이핑 없이 고르기만 하면 되게. 목록에 없는 관계는
// "기타"를 고르면 직접 입력할 수 있게 남겨둔다.
const RELATION_OPTIONS = [
  "할아버지",
  "할머니",
  "아버지",
  "어머니",
  "배우자",
  "자녀",
  "형/오빠",
  "누나/언니",
  "동생",
  "기타",
] as const;

/** 관계 선택 드롭다운. "기타" 선택 시 아래 텍스트 입력이 나타난다 - 부모/이메일/QR 발급
 * 3개 폼이 전부 이 컴포넌트 하나로 통일해서 쓴다(자유 텍스트 입력을 각자 따로 두지 않음). */
function RelationSelect({
  value,
  onChange,
  idPrefix,
}: {
  value: string;
  onChange: (value: string) => void;
  idPrefix: string;
}) {
  const isKnownOption = (RELATION_OPTIONS as readonly string[]).includes(value);
  // [버그 수정] "기타"를 고르면 value를 빈 문자열로 비우는데, value===""만 보고 선택 상태를
  // 판단하면 "기타 선택 후 아직 입력 전"과 "아무것도 선택 안 함"을 구분 못 해서 드롭다운이
  // 다시 placeholder로 돌아가고 입력칸도 같이 사라졌었다 - "기타 모드"를 별도 상태로 갖는다.
  const [isOtherMode, setIsOtherMode] = useState(value !== "" && !isKnownOption);
  const selectValue = isOtherMode ? "기타" : isKnownOption ? value : "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <select
        id={`${idPrefix}-relation-select`}
        name={`${idPrefix}-relation-select`}
        value={selectValue}
        onChange={(e) => {
          const next = e.target.value;
          if (next === "기타") {
            setIsOtherMode(true);
            onChange("");
          } else {
            setIsOtherMode(false);
            onChange(next);
          }
        }}
        style={inputStyle}
        required
      >
        <option value="" disabled>
          관계를 선택해주세요
        </option>
        {RELATION_OPTIONS.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      {isOtherMode && (
        <input
          type="text"
          name={`${idPrefix}-relation-custom`}
          autoComplete="off"
          placeholder="관계를 직접 입력해주세요 (예: 이모, 삼촌)"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          style={inputStyle}
          maxLength={20}
          required
        />
      )}
    </div>
  );
}

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
 * [범위] 이번 화면은 "연결(요청/승인/초대코드)"까지만 다룬다 - 약 등록/조회/수정은 여기서
 * 안 하고 각각 트랙커(사진/수동 등록)와 복약알림(가족 선택해서 알림 보기/토글) 화면으로
 * 옮겼다(2026-07-16 결정 - 이 화면에 다 몰아두면 두 도메인(MedicationSchedule/
 * NotificationSchedule)이 뒤섞여 헷갈리고, 이미 있는 화면(트랙커/복약알림)과 중복된
 * UI가 생기기 때문).
 * [승인 플로우] 이메일만 알면 요청은 보낼 수 있지만, 상대방이 "수락"해야 실제로 연결된다.
 * 아직 푸시 알림 인프라가 없어서, 받은 요청은 이 화면(또는 홈 화면)을 열 때(또는 새로고침)
 * 보인다 - 실시간 팝업 알림은 아니다.
 * [초대코드] 이메일 요청과 별개로, 초대코드 경로도 같이 제공한다(카카오 임시 가입 계정처럼
 * 이메일로 못 찾는 경우의 대안). 코드는 발급 즉시 30분 유효/1회용이고, 입력하는 순간 승인
 * 절차 없이 바로 연결된다(코드를 안다는 것 자체가 이미 상호 동의로 간주). */
export default function FamilyPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const cameFromMore = (location.state as { from?: string } | null)?.from === "more";
  const [data, setData] = useState<FamilyMembersResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [linkMethod, setLinkMethod] = useState<"email" | "code" | "qr">("email");

  const [email, setEmail] = useState("");
  const [relationLabel, setRelationLabel] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [isLinking, setIsLinking] = useState(false);

  const [issueRelationLabel, setIssueRelationLabel] = useState("");
  const [issuedCode, setIssuedCode] = useState<{ code: string } | null>(null);
  const [issueError, setIssueError] = useState<string | null>(null);
  const [isIssuing, setIsIssuing] = useState(false);

  const [redeemCode, setRedeemCode] = useState("");
  const [redeemError, setRedeemError] = useState<string | null>(null);
  const [isRedeeming, setIsRedeeming] = useState(false);

  // [연결 해제 확인 모달] window.confirm(브라우저 기본 팝업) 대신 화면 안 모달로 확인받는다 -
  // 어느 목록(내가 관리하는 가족/응답 대기중인 요청/나를 관리하는 가족)에서 눌렀든 이 모달
  // 하나로 통일해서 처리한다.
  const [pendingUnlink, setPendingUnlink] = useState<{
    linkId: number;
    viewpoint: "guardian" | "member";
  } | null>(null);
  const [isUnlinking, setIsUnlinking] = useState(false);

  // [QR 탭 전용] 발급된 코드를 QR 이미지(data URL)로 렌더링, 그리고 카메라로 QR 스캔.
  // 코드 발급/입력 자체(issuedCode/redeemCode/handleIssueCode/handleRedeemCode)는 "초대코드"
  // 탭과 완전히 같은 로직을 그대로 재사용한다 - QR은 그 코드를 "타이핑 대신 카메라로
  // 주고받는" 또 다른 경로일 뿐이라, 중복 구현하지 않는다.
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [showScanner, setShowScanner] = useState(false);

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

  // 코드가 발급되면(초대코드 탭이든 QR 탭이든 상관없이) QR 이미지도 같이 만들어둔다 -
  // 어느 탭에서 발급했든 QR 탭으로 넘어가면 바로 볼 수 있게.
  useEffect(() => {
    if (!issuedCode) {
      setQrDataUrl(null);
      return;
    }
    QRCode.toDataURL(issuedCode.code, { width: 200, margin: 1 })
      .then(setQrDataUrl)
      .catch(() => setQrDataUrl(null)); // QR 생성 실패해도 숫자 코드 자체는 이미 화면에 보이니 문제없음
  }, [issuedCode]);

  // 카메라로 QR을 읽으면, 그 코드를 "받은 초대코드 입력하기"와 완전히 같은 방식으로
  // 바로 연결 시도한다 - 사용자가 굳이 6자리를 다시 타이핑할 필요 없이 스캔만으로 끝낸다.
  async function handleQrScanned(text: string) {
    setShowScanner(false);
    const code = text.trim().toUpperCase();
    setRedeemCode(code);
    setRedeemError(null);
    setIsRedeeming(true);
    try {
      await familyApi.redeemInviteCode(code);
      setRedeemCode("");
      await load();
    } catch (err) {
      setRedeemError(err instanceof Error ? err.message : "초대코드 연결에 실패했습니다.");
    } finally {
      setIsRedeeming(false);
    }
  }

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

  async function handleUnlink(linkId: number, viewpoint: "guardian" | "member" = "guardian") {
    setPendingUnlink({ linkId, viewpoint });
  }

  async function executeUnlink() {
    if (!pendingUnlink) return;
    const { linkId } = pendingUnlink;
    setIsUnlinking(true);
    try {
      await familyApi.unlink(linkId);
      setPendingUnlink(null);
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "연결 해제에 실패했습니다.");
    } finally {
      setIsUnlinking(false);
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
        <PageTitle icon={Users}>가족관리</PageTitle>
        <p style={{ margin: 0, fontSize: 13, color: pinkTheme.textMuted, lineHeight: 1.5 }}>
          부모님 등 가족 구성원을 이메일 또는 초대코드로 연결해요. 연결되면 트랙커(사진/수동 등록)와
          복약알림 화면에서 "나 또는 이 분" 중 누구 몫으로 확인·등록할지 고를 수 있어요.
        </p>

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
              fontWeight: 700,
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
              fontWeight: 700,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            초대코드
          </button>
          <button
            type="button"
            onClick={() => setLinkMethod("qr")}
            style={{
              flex: 1,
              padding: "10px",
              border: `1px solid ${linkMethod === "qr" ? pinkTheme.primary : pinkTheme.border}`,
              borderRadius: 10,
              background: linkMethod === "qr" ? pinkTheme.primary : pinkTheme.cardBg,
              color: linkMethod === "qr" ? "#fff" : pinkTheme.textMuted,
              fontWeight: 700,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            QR
          </button>
        </div>

        {linkMethod === "email" ? (
          <form
            onSubmit={handleRequestLink}
            style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: 10 }}
          >
            <p style={{ margin: 0, fontWeight: 700, color: pinkTheme.text, fontSize: 14 }}>
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
            <RelationSelect value={relationLabel} onChange={setRelationLabel} idPrefix="email" />
            {linkError && (
              <p style={{ margin: 0, color: pinkTheme.danger, fontSize: 13 }}>{linkError}</p>
            )}
            <button type="submit" disabled={isLinking} style={primaryButtonStyle}>
              {isLinking ? "요청 보내는 중..." : "연결 요청 보내기"}
            </button>
          </form>
        ) : linkMethod === "code" ? (
          <>
            <form
              onSubmit={handleIssueCode}
              style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: 10 }}
            >
              <p style={{ margin: 0, fontWeight: 700, color: pinkTheme.text, fontSize: 14 }}>
                초대코드 발급하기
              </p>
              <p style={{ margin: 0, fontSize: 13, color: pinkTheme.textMuted }}>
                이메일을 몰라도 돼요(카카오로 가입한 가족분께 추천). 코드를 발급해서 카톡/문자로
                전달하면, 상대방이 입력하는 즉시 연결돼요(30분 안에 사용, 1회용).
              </p>
              <RelationSelect
                value={issueRelationLabel}
                onChange={setIssueRelationLabel}
                idPrefix="issue-code"
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
                      borderRadius: 10,
                      background: pinkTheme.cardBg,
                      color: pinkTheme.primary,
                      fontSize: 12,
                      fontWeight: 700,
                      padding: "6px 12px",
                      cursor: "pointer",
                    }}
                  >
                    복사
                  </button>
                </div>
              )}
            </form>

            <form
              onSubmit={handleRedeemCode}
              style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: 10 }}
            >
              <p style={{ margin: 0, fontWeight: 700, color: pinkTheme.text, fontSize: 14 }}>
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
        ) : (
          <>
            <div style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: 10 }}>
              <p style={{ margin: 0, fontWeight: 700, color: pinkTheme.text, fontSize: 14 }}>
                QR코드로 초대하기
              </p>
              <p style={{ margin: 0, fontSize: 13, color: pinkTheme.textMuted }}>
                초대코드를 발급하면 QR코드도 같이 생겨요. 상대방이 이 화면(QR 탭)에서 "QR
                스캔하기"로 찍으면, 6자리를 안 옮겨 적어도 바로 연결돼요.
              </p>
              {!issuedCode ? (
                <form
                  onSubmit={handleIssueCode}
                  style={{ display: "flex", flexDirection: "column", gap: 10 }}
                >
                  <RelationSelect
                    value={issueRelationLabel}
                    onChange={setIssueRelationLabel}
                    idPrefix="issue-qr"
                  />
                  {issueError && (
                    <p style={{ margin: 0, color: pinkTheme.danger, fontSize: 13 }}>{issueError}</p>
                  )}
                  <button type="submit" disabled={isIssuing} style={primaryButtonStyle}>
                    {isIssuing ? "발급 중..." : "QR 초대코드 발급하기"}
                  </button>
                </form>
              ) : (
                <div
                  style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}
                >
                  {qrDataUrl && (
                    <img
                      src={qrDataUrl}
                      alt={`초대코드 ${issuedCode.code} QR코드`}
                      style={{
                        width: 200,
                        height: 200,
                        border: `1px solid ${pinkTheme.border}`,
                        borderRadius: 12,
                        padding: 8,
                        background: "#fff",
                      }}
                    />
                  )}
                  <span
                    style={{
                      fontSize: 18,
                      fontWeight: 700,
                      letterSpacing: 3,
                      color: pinkTheme.primary,
                    }}
                  >
                    {issuedCode.code}
                  </span>
                  <p style={{ margin: 0, fontSize: 13, color: pinkTheme.textMuted }}>
                    30분 안에 사용, 1회용이에요.
                  </p>
                </div>
              )}
            </div>

            <div style={{ ...cardStyle, display: "flex", flexDirection: "column", gap: 10 }}>
              <p style={{ margin: 0, fontWeight: 700, color: pinkTheme.text, fontSize: 14 }}>
                QR코드로 연결하기
              </p>
              {!showScanner ? (
                <button
                  type="button"
                  onClick={() => {
                    setRedeemError(null);
                    setShowScanner(true);
                  }}
                  style={primaryButtonStyle}
                >
                  📷 QR 스캔하기
                </button>
              ) : (
                <QrScanner onScan={handleQrScanned} onClose={() => setShowScanner(false)} />
              )}
              {isRedeeming && (
                <p style={{ margin: 0, fontSize: 13, color: pinkTheme.textMuted }}>
                  연결하는 중...
                </p>
              )}
              {redeemError && (
                <p style={{ margin: 0, color: pinkTheme.danger, fontSize: 13 }}>{redeemError}</p>
              )}
            </div>
          </>
        )}

        {loading && <p style={{ color: pinkTheme.textMuted, fontSize: 13 }}>불러오는 중...</p>}
        {loadError && <p style={{ color: pinkTheme.danger, fontSize: 13 }}>{loadError}</p>}

        {!loading && !loadError && data && (
          <>
            {data.as_member_pending.length > 0 && (
              <div style={{ ...cardStyle, borderColor: pinkTheme.primary }}>
                <p
                  style={{
                    margin: "0 0 10px",
                    fontWeight: 700,
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
                              borderRadius: 10,
                              background: pinkTheme.primary,
                              color: "#fff",
                              fontSize: 12,
                              fontWeight: 700,
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
                              borderRadius: 10,
                              background: pinkTheme.cardBg,
                              color: pinkTheme.textMuted,
                              fontSize: 12,
                              fontWeight: 700,
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

            <div style={cardStyle}>
              <p
                style={{ margin: "0 0 10px", fontWeight: 700, color: pinkTheme.text, fontSize: 14 }}
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
              <p style={{ margin: "10px 0 0", fontSize: 13, color: pinkTheme.textMuted }}>
                이 분 몫으로 약을 등록하려면 트랙커 화면에서, 복약알림을 보려면 복약알림 화면에서 이
                분을 선택하시면 돼요.
              </p>
            </div>

            {data.as_guardian_pending.length > 0 && (
              <div style={cardStyle}>
                <p
                  style={{
                    margin: "0 0 10px",
                    fontWeight: 700,
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

            {data.as_member_accepted.length > 0 && (
              <div style={cardStyle}>
                <p
                  style={{
                    margin: "0 0 10px",
                    fontWeight: 700,
                    color: pinkTheme.text,
                    fontSize: 14,
                  }}
                >
                  나를 관리하고 있는 가족
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {data.as_member_accepted.map((item) => (
                    <LinkRow
                      key={item.link_id}
                      item={item}
                      right={
                        <button
                          type="button"
                          onClick={() => handleUnlink(item.link_id, "member")}
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
                <p style={{ margin: "10px 0 0", fontSize: 13, color: pinkTheme.textMuted }}>
                  연결을 해제하면 이 분이 더 이상 회원님의 건강정보를 확인/관리할 수 없어요. 이미
                  등록된 약 정보는 그대로 남아요.
                </p>
              </div>
            )}
          </>
        )}
      </div>

      {pendingUnlink && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: 20,
          }}
          onClick={() => !isUnlinking && setPendingUnlink(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            style={{
              ...cardStyle,
              width: "100%",
              maxWidth: 340,
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            <p style={{ margin: 0, fontWeight: 700, color: pinkTheme.text, fontSize: 15 }}>
              가족 연결을 해제할까요?
            </p>
            <p style={{ margin: 0, fontSize: 13, color: pinkTheme.textMuted, lineHeight: 1.5 }}>
              {pendingUnlink.viewpoint === "member"
                ? "해제하면 이 분은 더 이상 회원님의 건강정보를 확인/관리할 수 없어요. 이미 등록된 약 정보는 그대로 남아요."
                : "이미 등록된 약 정보는 그대로 남고, 앞으로는 확인/등록만 못 하게 돼요."}
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                onClick={() => setPendingUnlink(null)}
                disabled={isUnlinking}
                style={{
                  flex: 1,
                  padding: "12px",
                  border: `1px solid ${pinkTheme.border}`,
                  borderRadius: 10,
                  background: pinkTheme.cardBg,
                  color: pinkTheme.text,
                  fontWeight: 700,
                  fontSize: 14,
                  cursor: isUnlinking ? "not-allowed" : "pointer",
                }}
              >
                취소
              </button>
              <button
                type="button"
                onClick={executeUnlink}
                disabled={isUnlinking}
                style={{
                  flex: 1,
                  padding: "12px",
                  border: "none",
                  borderRadius: 10,
                  background: pinkTheme.danger,
                  color: "#fff",
                  fontWeight: 700,
                  fontSize: 14,
                  cursor: isUnlinking ? "not-allowed" : "pointer",
                  opacity: isUnlinking ? 0.7 : 1,
                }}
              >
                {isUnlinking ? "해제하는 중..." : "연결 해제"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
