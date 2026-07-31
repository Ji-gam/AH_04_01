import { Check, Pill } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import Modal from "../../pages/AlarmPage/components/Modal";
import { pinkTheme } from "../../theme/pinkTheme";

/** (2026-07-30) 개인건강정보/가족 복약등록/본인 복약등록 세 군데에서 각자 따로 만들었던
 * "등록·저장 완료" 확인 모달(핑크 원 + 중앙 아이콘 + 체크 뱃지)을 하나로 통합했다.
 * 예전엔 초록 이모지 체크나 스타일 없는 인라인 텍스트로 제각각이었는데, 지금은 이 컴포넌트
 * 하나만 갖다 쓰면 세 화면이 항상 같은 모양을 유지한다 - 나중에 스타일을 바꿀 일이 생겨도
 * 여기 한 곳만 고치면 전부 반영된다.
 *
 * [2026-07-30] 중앙 아이콘은 화면 맥락에 따라 다른 게 더 어울려서(예: 복약등록은 알약,
 * 개인건강정보 저장은 클립보드) props로 바꿔 끼울 수 있게 했다 - 구석의 체크 뱃지는
 * "완료됐다"는 공통 의미라 모든 화면에서 고정으로 둔다. */

interface SuccessModalProps {
  message: string;
  onConfirm: () => void;
  confirmLabel?: string;
  icon?: LucideIcon;
}

export default function SuccessModal({
  message,
  onConfirm,
  confirmLabel = "확인",
  icon: Icon = Pill,
}: SuccessModalProps) {
  return (
    <Modal onClose={onConfirm}>
      <div
        style={{
          background: pinkTheme.cardBg,
          border: `1px solid ${pinkTheme.border}`,
          borderRadius: 16,
          padding: 24,
          boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
          textAlign: "center",
        }}
      >
        <div style={{ position: "relative", width: 52, height: 52, margin: "0 auto 12px" }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: "50%",
              background: pinkTheme.primarySoft,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon size={24} color={pinkTheme.primary} />
          </div>
          <div
            style={{
              position: "absolute",
              bottom: -2,
              right: -2,
              width: 20,
              height: 20,
              borderRadius: "50%",
              background: pinkTheme.primary,
              border: `2px solid ${pinkTheme.cardBg}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Check size={12} color="#fff" strokeWidth={3} />
          </div>
        </div>
        <p style={{ margin: "0 0 18px", fontSize: 15, fontWeight: 700, color: pinkTheme.text }}>
          {message}
        </p>
        <button
          type="button"
          onClick={onConfirm}
          style={{
            width: "100%",
            padding: "10px",
            border: "none",
            borderRadius: 10,
            background: pinkTheme.primary,
            color: "#fff",
            fontWeight: 700,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
