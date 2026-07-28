import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { consentApi } from "../../api/healthInfoApi";
import type { ConsentStatusResult } from "../../api/types";
import PageTitle from "../../components/common/PageTitle";
import { CONSENT_ITEMS, type ConsentItem } from "../../constants/consentItems";
import { pinkTheme as t } from "../../theme/pinkTheme";
import Modal from "../AlarmPage/components/Modal";

/** (2026-07-28 전면 개편) 예전엔 이 화면 자체에서 6개 항목(이용약관/건강정보/민감정보/
 * 위치정보/AI상담/마케팅)을 체크박스로 편집하고 localStorage에 저장했다 - 근데:
 *  1) 온보딩 어디에도 연결이 안 돼있어서 더보기 메뉴로 스스로 찾아 들어가지 않으면
 *     평생 못 봤고,
 *  2) 기본값이 마케팅 빼고 전부 true(이미 동의함)라서, 체크한 적 없어도 동의한 걸로
 *     취급되는 버그가 있었다.
 * 이제 진짜 동의(이용약관/건강정보/AI챗봇 필수 + 마케팅 선택)는 회원가입 직후
 * ConsentPage.tsx에서 한 번에 받고 서버 DB에 남긴다(RequireAuth가 강제). 위치정보는
 * 병원/약국 찾기 등에서 브라우저 자체 geolocation 권한요청이 이미 다루고 있어 별도
 * 항목을 안 둔다. 이 화면은 이제 "내가 언제 뭘 동의했는지" 서버 값을 그대로 보여주는
 * 읽기 전용 확인 화면으로 바꿨다 - 여기서 다시 체크/해제하는 기능은 없다(철회는
 * 회원탈퇴로 처리). 항목 정의는 constants/consentItems.ts에서 ConsentPage.tsx와
 * 공유한다(문구가 두 화면에서 따로 놀지 않게). */

// ConsentItem.key("terms_of_service")와 ConsentStatusResult의 실제 필드명
// ("terms_of_service_consented_at")이 달라서 매핑이 필요하다.
const STATUS_KEY_MAP: Record<ConsentItem["key"], keyof ConsentStatusResult> = {
  terms_of_service: "terms_of_service_consented_at",
  health_info: "health_info_consented_at",
  ai_chat: "ai_chat_consented_at",
  marketing: "marketing_consented_at",
};

export default function DataConsentPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<ConsentStatusResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailItem, setDetailItem] = useState<ConsentItem | null>(null);

  useEffect(() => {
    consentApi
      .get()
      .then(setStatus)
      .catch((err) => setError(err instanceof Error ? err.message : "동의 현황을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ minHeight: "100%", background: t.pageBg, padding: "20px 12px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto", color: t.text }}>
        <button
          type="button"
          onClick={() => navigate("/more")}
          style={{
            background: "none",
            border: "none",
            color: t.textMuted,
            padding: 0,
            marginBottom: 12,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          ← 뒤로가기
        </button>

        <PageTitle icon={ShieldCheck} style={{ marginBottom: 4 }}>
          내 동의 현황
        </PageTitle>
        <p style={{ margin: "0 0 16px", fontSize: 12.5, color: t.textMuted }}>
          회원가입 시 동의하신 내용이에요. 철회를 원하시면 회원탈퇴를 이용해주세요.
        </p>

        {loading && <p style={{ fontSize: 13, color: t.textMuted }}>불러오는 중...</p>}
        {!loading && error && <p style={{ fontSize: 13, color: t.danger }}>{error}</p>}

        {!loading && !error && status && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {CONSENT_ITEMS.map((item) => {
              const consentedAt = status[STATUS_KEY_MAP[item.key]];
              return (
                <div
                  key={item.key}
                  style={{
                    background: t.cardBg,
                    border: `1px solid ${t.border}`,
                    borderRadius: 12,
                    padding: 14,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>
                      {item.title} {item.required ? "(필수)" : "(선택)"}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        padding: "2px 10px",
                        borderRadius: 999,
                        background: consentedAt ? "#EAF7EF" : t.pageBg,
                        color: consentedAt ? t.success : t.textMuted,
                        border: `1px solid ${consentedAt ? t.success : t.border}`,
                      }}
                    >
                      {consentedAt ? "동의함" : "미동의"}
                    </span>
                  </div>
                  <p style={{ margin: "6px 0 0", fontSize: 12.5, color: t.textMuted }}>{item.summary}</p>
                  {consentedAt && (
                    <p style={{ margin: "6px 0 0", fontSize: 11, color: t.textMuted }}>
                      동의 시각: {new Date(consentedAt).toLocaleString("ko-KR")}
                    </p>
                  )}
                  <button
                    type="button"
                    onClick={() => setDetailItem(item)}
                    style={{
                      marginTop: 6,
                      background: "none",
                      border: "none",
                      color: t.primary,
                      fontSize: 12,
                      textDecoration: "underline",
                      cursor: "pointer",
                      padding: 0,
                    }}
                  >
                    전문 보기
                  </button>
                </div>
              );
            })}
          </div>
        )}
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
