import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { pinkTheme as t } from "../../theme/pinkTheme";
import {
  DEFAULT_CONSENT,
  loadConsent,
  saveConsent,
  type ConsentKey,
  type DataConsent,
} from "../../utils/dataConsent";
import Modal from "../AlarmPage/components/Modal";
import ToggleSwitch from "../AlarmPage/components/ToggleSwitch";

interface DetailSection {
  heading: string;
  items: string[];
}

interface ConsentItemDef {
  key: ConsentKey;
  title: string;
  desc: string;
  required: boolean;
  requiredWarning: string;
  detail: {
    intro: string;
    sections: DetailSection[];
  };
}

const CONSENT_ITEMS: ConsentItemDef[] = [
  {
    key: "health",
    title: "건강정보 활용 동의",
    desc: "복약알림·상담 맞춤화를 위해 건강 데이터를 활용해요",
    required: true,
    requiredWarning: "건강정보 활용에 동의하지 않으면 맞춤 복약 알림 등 핵심 기능이 제한돼요.",
    detail: {
      intro:
        "[리:메디 Re:Medi]는 복약 알림, 맞춤형 생활습관 가이드, AI 상담 서비스를 제공하기 위해 아래 건강정보를 활용합니다.",
      sections: [
        {
          heading: "활용 정보",
          items: [
            "처방전 및 복약 기록",
            "건강 지표 (체중, 혈당, 혈압 등)",
            "생활습관 데이터 (식사 시간, 수면 시간, 운동 기록)",
          ],
        },
        {
          heading: "활용 목적",
          items: [
            "개인별 맞춤 복약 알림 제공",
            "AI 기반 식단·운동 추천",
            "복약 순응도 분석 및 개선 가이드",
          ],
        },
        {
          heading: "보관 및 처리",
          items: [
            "최소한의 정보만 수집하며, 서비스 탈퇴 시 즉시 삭제됩니다.",
            "제3자 제공 없이 내부 서비스 개선 목적으로만 사용됩니다.",
          ],
        },
      ],
    },
  },
  {
    key: "aiChat",
    title: "AI 상담 데이터 활용 동의",
    desc: "상담 품질 개선을 위해 대화 내용을 분석해요",
    required: false,
    requiredWarning: "",
    detail: {
      intro: "AI 상담 서비스(챗봇)를 이용하시면 대화 내용을 분석하여 더 정확한 답변을 제공합니다.",
      sections: [
        { heading: "활용 정보", items: ["AI 챗봇 대화 기록", "건강 관련 질문 및 답변"] },
        {
          heading: "활용 목적",
          items: [
            "사용자 건강 상태에 맞는 개인화된 조언 제공",
            "대화 품질 개선 및 AI 모델 학습 (익명화 처리)",
          ],
        },
        {
          heading: "보관 및 처리",
          items: [
            "대화 내용은 서비스 개선 목적으로만 익명화되어 사용됩니다.",
            "언제든지 대화 기록 삭제를 요청할 수 있습니다.",
          ],
        },
      ],
    },
  },
  {
    key: "location",
    title: "위치정보 활용 동의",
    desc: "가까운 응급실·약국 찾기, 위치 기반 서비스 제공을 위해 사용합니다.",
    required: true,
    requiredWarning:
      "위치정보 활용에 동의하지 않으면 가까운 응급실·약국 찾기 기능을 사용할 수 없어요.",
    detail: {
      intro: "위치정보를 활용하여 주변 응급 의료 시설과 약국을 안내해드립니다.",
      sections: [
        { heading: "활용 정보", items: ["현재 위치 (GPS)", "위치 기반 검색 기록"] },
        {
          heading: "활용 목적",
          items: ["가까운 응급실·약국 검색 및 길안내", "24시간 약국, 당번 약국 추천"],
        },
        {
          heading: "보관 및 처리",
          items: [
            "위치정보는 실시간으로만 사용되며, 저장하지 않습니다.",
            "위치 권한은 언제든지 설정에서 변경 가능합니다.",
          ],
        },
      ],
    },
  },
  {
    key: "marketing",
    title: "마케팅 정보 수신 동의",
    desc: "이벤트·혜택 정보를 알려드려요",
    required: false,
    requiredWarning: "",
    detail: {
      intro: "서비스 관련 유용한 정보를 받아보시겠습니까?",
      sections: [
        { heading: "활용 정보", items: ["푸시 알림, 이메일, SMS"] },
        { heading: "활용 목적", items: ["이벤트, 프로모션, 건강 정보 뉴스레터", "신규 기능 안내"] },
        {
          heading: "보관 및 처리",
          items: [
            "마케팅 동의는 언제든지 철회할 수 있습니다.",
            "철회 후에도 서비스 필수 알림은 계속 수신됩니다.",
          ],
        },
      ],
    },
  },
];

export default function DataConsentPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [consent, setConsent] = useState<DataConsent>(() =>
    user ? loadConsent(user.email) : DEFAULT_CONSENT,
  );
  const [detailKey, setDetailKey] = useState<ConsentKey | null>(null);
  const [saved, setSaved] = useState(false);

  const allAgreed = CONSENT_ITEMS.every((item) => consent[item.key]);

  function toggle(key: ConsentKey) {
    setConsent((prev) => ({ ...prev, [key]: !prev[key] }));
    setSaved(false);
  }

  function toggleAll() {
    const next = !allAgreed;
    setConsent(
      CONSENT_ITEMS.reduce((acc, item) => ({ ...acc, [item.key]: next }), {} as DataConsent),
    );
    setSaved(false);
  }

  function handleSave() {
    if (user) saveConsent(user.email, consent);
    setSaved(true);
  }

  const detailItem = CONSENT_ITEMS.find((item) => item.key === detailKey) ?? null;

  return (
    <div style={{ background: t.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          <button
            type="button"
            aria-label="뒤로"
            onClick={() => navigate("/more")}
            style={{
              border: "none",
              background: "none",
              color: t.text,
              fontSize: 20,
              cursor: "pointer",
              lineHeight: 1,
            }}
          >
            ←
          </button>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: t.text, margin: 0 }}>
            데이터 활용 동의
          </h1>
        </div>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "12px 14px",
            marginBottom: 14,
            borderRadius: 14,
            background: t.primarySoft,
            fontSize: 14,
            fontWeight: 700,
            color: t.text,
            cursor: "pointer",
          }}
        >
          <input type="checkbox" checked={allAgreed} onChange={toggleAll} />
          모두 동의
        </label>

        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 14 }}>
          {CONSENT_ITEMS.map((item) => (
            <div
              key={item.key}
              style={{
                background: t.cardBg,
                border: `1px solid ${t.border}`,
                borderRadius: 16,
                padding: "14px 16px",
                boxShadow: "0 2px 8px rgba(255, 111, 145, 0.08)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 12,
                }}
              >
                <button
                  type="button"
                  onClick={() => setDetailKey(item.key)}
                  style={{
                    flex: 1,
                    textAlign: "left",
                    background: "none",
                    border: "none",
                    padding: 0,
                    cursor: "pointer",
                    font: "inherit",
                  }}
                >
                  <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: t.text }}>
                    {item.title}
                    {item.required && (
                      <span
                        style={{ marginLeft: 6, fontSize: 11, fontWeight: 700, color: t.danger }}
                      >
                        필수
                      </span>
                    )}
                  </p>
                  <p style={{ margin: "4px 0 0", fontSize: 12, color: t.textMuted }}>{item.desc}</p>
                  <span
                    style={{
                      display: "inline-block",
                      marginTop: 6,
                      fontSize: 11,
                      color: t.primary,
                    }}
                  >
                    자세히 보기 ›
                  </span>
                </button>
                <ToggleSwitch
                  checked={consent[item.key]}
                  onChange={() => toggle(item.key)}
                  ariaLabel={item.title}
                />
              </div>

              {item.required && !consent[item.key] && (
                <p style={{ margin: "8px 0 0", fontSize: 11, color: t.danger, lineHeight: 1.5 }}>
                  ⚠️ {item.requiredWarning}
                </p>
              )}
            </div>
          ))}
        </div>

        <p style={{ margin: "0 0 20px", fontSize: 11, color: t.textMuted, lineHeight: 1.5 }}>
          동의를 철회하면 관련 기능(맞춤 알림·상담 추천)이 제한될 수 있어요.
        </p>

        <button
          type="button"
          onClick={handleSave}
          style={{
            width: "100%",
            padding: "14px 0",
            borderRadius: 12,
            border: "none",
            background: t.primary,
            color: "#fff",
            fontSize: 15,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          저장
        </button>

        {saved && (
          <p style={{ margin: "10px 0 0", fontSize: 13, color: t.success, textAlign: "center" }}>
            ✓ 저장되었습니다.
          </p>
        )}

        {detailItem && (
          <Modal onClose={() => setDetailKey(null)}>
            <div
              style={{
                background: t.cardBg,
                border: `1px solid ${t.border}`,
                borderRadius: 16,
                padding: 20,
                color: t.text,
              }}
            >
              <h2 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 700, color: t.primary }}>
                {detailItem.title}
              </h2>
              <p style={{ margin: "0 0 14px", fontSize: 13, lineHeight: 1.6 }}>
                {detailItem.detail.intro}
              </p>
              {detailItem.detail.sections.map((section) => (
                <div key={section.heading} style={{ marginBottom: 14 }}>
                  <p style={{ margin: "0 0 6px", fontSize: 13, fontWeight: 700, color: t.text }}>
                    {section.heading}
                  </p>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {section.items.map((line) => (
                      <li
                        key={line}
                        style={{ fontSize: 12.5, color: t.textMuted, lineHeight: 1.6 }}
                      >
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setDetailKey(null)}
                style={{
                  width: "100%",
                  marginTop: 4,
                  padding: "11px 0",
                  borderRadius: 10,
                  border: `1px solid ${t.border}`,
                  background: t.cardBg,
                  color: t.textMuted,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                닫기
              </button>
            </div>
          </Modal>
        )}
      </div>
    </div>
  );
}
