import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { consentApi } from "../../api/healthInfoApi";
import PageTitle from "../../components/common/PageTitle";
import { CONSENT_ITEMS, type ConsentItem } from "../../constants/consentItems";
import { useAuth } from "../../hooks/useAuth";
import { pinkTheme as t } from "../../theme/pinkTheme";
import Modal from "../AlarmPage/components/Modal";

/** (2026-07-28 전면 개편) 회원가입 시 한 화면에서 한 번에 받는 통합 동의 화면.
 * RequireAuth가 이 중 필수 3개(이용약관/건강정보/AI챗봇)를 아직 안 마친 계정을
 * 자동으로 여기로 보낸다 - 이메일 가입/로그인, 소셜 로그인 전부 동일하게 적용된다
 * (LoginPage.tsx에서도 로그인/가입 직후 한 번 더 체크해서 보냄).
 *
 * - 마케팅만 선택, 나머지 3개는 필수.
 * - 위치정보는 별도 동의 항목을 안 둔다 - 병원/약국 찾기 등에서 브라우저 자체
 *   geolocation 권한요청이 이미 그 역할을 하고 있어 중복이라 판단(2026-07-28 결정).
 * - 진짜 동의 여부의 근거는 서버 DB(users.*_consented_at)뿐이다(예전엔
 *   localStorage에만 남겨서 서버에 근거가 없었음 - 그 문제를 고치는 김에 아예
 *   localStorage 캐시 자체를 없애고 서버 값만 기준으로 삼는다).
 * - 문구는 화면에서는 압축해서 보여주되(길게 늘어놓으면 안 읽음), "전문 보기"로
 *   전체 내용을 확인할 수 있게 한다(layered notice 방식). 항목 정의 자체는
 *   constants/consentItems.ts에 있음(DataConsentPage.tsx와 공유). */

export default function ConsentPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, refreshUser } = useAuth();
  const [checked, setChecked] = useState<Record<ConsentItem["key"], boolean>>({
    terms_of_service: false,
    health_info: false,
    ai_chat: false,
    marketing: false,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [detailItem, setDetailItem] = useState<ConsentItem | null>(null);

  useEffect(() => {
    if (
      user?.terms_of_service_consented_at &&
      user?.health_info_consented_at &&
      user?.ai_chat_consented_at
    ) {
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? "/", { replace: true });
    }
  }, [navigate, user, location.state]);

  const requiredDone = CONSENT_ITEMS.filter((i) => i.required).every((i) => checked[i.key]);
  const allChecked = CONSENT_ITEMS.every((i) => checked[i.key]);

  function toggleAll() {
    const next = !allChecked;
    setChecked({
      terms_of_service: next,
      health_info: next,
      ai_chat: next,
      marketing: next,
    });
  }

  async function handleAgreeAndContinue() {
    if (!requiredDone) return;
    setIsSaving(true);
    try {
      await consentApi.update({
        terms_of_service: checked.terms_of_service,
        health_info: checked.health_info,
        ai_chat: checked.ai_chat,
        marketing: checked.marketing,
      });
      // (2026-07-28 버그 수정) 서버엔 저장됐는데 useAuth()의 캐시된 user는 그대로라,
      // 홈으로 이동해도 Layout/RequireAuth가 여전히 "미동의"로 보고 다시 이 화면으로
      // 튕겨서 홈으로 못 넘어가는 문제가 있었다 - 이동 전에 캐시부터 최신화한다.
      await refreshUser();
    } catch (err) {
      console.error("동의 서버 기록 실패:", err);
    } finally {
      setIsSaving(false);
    }
    const from = (location.state as { from?: string } | null)?.from;
    navigate(from ?? "/", { replace: true });
  }

  return (
    <div
      style={{
        minHeight: "100%",
        background: t.pageBg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 400,
          background: t.cardBg,
          border: `1px solid ${t.border}`,
          borderRadius: "16px",
          padding: "24px",
          boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
        }}
      >
        <PageTitle icon={ShieldCheck} style={{ marginBottom: 4 }}>
          서비스 이용을 위한 동의
        </PageTitle>
        <p style={{ margin: "0 0 16px", fontSize: 12.5, color: t.textMuted }}>
          아래 필수 항목에 동의하셔야 서비스를 이용할 수 있어요.
        </p>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "10px 4px",
            borderBottom: `1px solid ${t.border}`,
            marginBottom: 12,
            fontSize: 14,
            fontWeight: 700,
            color: t.text,
            cursor: "pointer",
          }}
        >
          <input type="checkbox" checked={allChecked} onChange={toggleAll} />
          전체 동의
        </label>

        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
          {CONSENT_ITEMS.map((item) => (
            <div key={item.key} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <label
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "flex-start",
                  fontSize: 13,
                  color: t.text,
                  cursor: "pointer",
                  flex: 1,
                }}
              >
                <input
                  type="checkbox"
                  checked={checked[item.key]}
                  onChange={(e) => setChecked((prev) => ({ ...prev, [item.key]: e.target.checked }))}
                  style={{ marginTop: 2 }}
                />
                <span>
                  <span style={{ fontWeight: 700 }}>
                    {item.title} {item.required ? "(필수)" : "(선택)"}
                  </span>
                  <br />
                  <span style={{ fontSize: 12, color: t.textMuted }}>{item.summary}</span>
                </span>
              </label>
              <button
                type="button"
                onClick={() => setDetailItem(item)}
                style={{
                  flex: "none",
                  background: "none",
                  border: "none",
                  color: t.primary,
                  fontSize: 12,
                  textDecoration: "underline",
                  cursor: "pointer",
                  padding: 0,
                  marginTop: 2,
                }}
              >
                전문 보기
              </button>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={handleAgreeAndContinue}
          disabled={!requiredDone || isSaving}
          style={{
            width: "100%",
            padding: "12px",
            border: "none",
            borderRadius: "10px",
            background: requiredDone ? t.primary : t.border,
            color: "#fff",
            fontWeight: 700,
            cursor: requiredDone ? "pointer" : "not-allowed",
          }}
        >
          {isSaving ? "저장 중..." : "동의하고 시작하기"}
        </button>
      </div>

      {detailItem && (
        <Modal onClose={() => setDetailItem(null)}>
          <div
            style={{
              background: t.cardBg,
              border: `1px solid ${t.border}`,
              borderRadius: 16,
              padding: 20,
              boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
            }}
          >
            <p style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 700, color: t.text }}>
              {detailItem.title}
            </p>
            <div
              style={{
                fontSize: 13,
                lineHeight: 1.7,
                color: t.text,
                whiteSpace: "pre-wrap",
                maxHeight: "50vh",
                overflowY: "auto",
                marginBottom: 16,
              }}
            >
              {detailItem.fullText}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setDetailItem(null)}
                style={{
                  padding: "9px 20px",
                  borderRadius: 10,
                  border: `1px solid ${t.border}`,
                  background: t.cardBg,
                  color: t.textMuted,
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                닫기
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
