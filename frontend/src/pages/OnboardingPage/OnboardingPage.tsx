import { useState } from "react";

import { pinkTheme } from "../../theme/pinkTheme";

interface Props {
  onFinish: () => void;
}

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  zIndex: 2000,
  background: pinkTheme.pageBg,
  display: "flex",
  flexDirection: "column",
  padding: "24px 28px 40px",
};

const primaryButtonStyle: React.CSSProperties = {
  width: "100%",
  padding: "16px 0",
  border: "none",
  borderRadius: 14,
  background: pinkTheme.primary,
  color: "#fff",
  fontWeight: 700,
  fontSize: 16,
  cursor: "pointer",
};

const centerColumnStyle: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: 18,
  textAlign: "center",
};

/** 비로그인 첫 진입 시 보여주는 스플래시 + 알림안내 온보딩(피그마 시안, 2026-07-16).
 * URL은 그대로 "/"를 쓰고, HomeEntry가 조건부로 이 컴포넌트를 띄운다 - Layout의 상단/하단
 * 네비게이션 위를 fixed + 높은 zIndex로 덮어서 전체화면 스플래시처럼 보이게 한다
 * (기존 Modal.tsx와 같은 방식). 화면이 2장뿐이라 라우트 분리 없이 내부 step으로 전환한다. */
export default function OnboardingPage({ onFinish }: Props) {
  const [step, setStep] = useState<1 | 2>(1);

  if (step === 1) {
    return (
      <div style={overlayStyle}>
        <div style={centerColumnStyle}>
          <div
            style={{
              width: 88,
              height: 88,
              border: `2px solid ${pinkTheme.primary}`,
              borderRadius: 24,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path
                d="M2 13h3.5l1.8-5 3.4 10 2.8-8 1.6 3H21"
                stroke={pinkTheme.primary}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <p style={{ margin: 0, fontSize: 26, fontWeight: 800, color: pinkTheme.primary }}>
            Re:medi
          </p>
          <p style={{ margin: 0, fontSize: 13, color: pinkTheme.textMuted, lineHeight: 1.5 }}>
            복약관리와 건강 상담을
            <br />한 곳에서
          </p>
        </div>
        <button type="button" style={primaryButtonStyle} onClick={() => setStep(2)}>
          시작하기
        </button>
      </div>
    );
  }

  return (
    <div style={overlayStyle}>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          type="button"
          onClick={onFinish}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            fontSize: 13,
            cursor: "pointer",
            padding: 4,
          }}
        >
          건너뛰기
        </button>
      </div>
      <div style={centerColumnStyle}>
        <div
          style={{
            width: 96,
            height: 96,
            borderRadius: "50%",
            background: pinkTheme.primarySoft,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 40,
          }}
          aria-hidden
        >
          🔔
        </div>
        <p
          style={{
            margin: 0,
            fontSize: 19,
            fontWeight: 800,
            color: pinkTheme.text,
            lineHeight: 1.4,
          }}
        >
          복약 시간을 놓치지 않게
          <br />
          알려드려요
        </p>
        <p style={{ margin: 0, fontSize: 13, color: pinkTheme.textMuted, lineHeight: 1.5 }}>
          약 이름, 시간, 반복 주기를 등록하면
          <br />
          맞춤 알림을 보내드려요
        </p>
      </div>
      <button type="button" style={primaryButtonStyle} onClick={onFinish}>
        다음
      </button>
    </div>
  );
}
