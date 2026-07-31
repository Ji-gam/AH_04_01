import { AlertTriangle, Check, Pill } from "lucide-react";

import Modal from "../../pages/AlarmPage/components/Modal";
import { pinkTheme as t } from "../../theme/pinkTheme";

interface Props {
  message: string;
  onClose: () => void;
  /** "success"는 알약+체크 배지, "warning"은 호박색 경고 배지. 기본값은 "success". */
  tone?: "success" | "warning";
}

/**
 * 약 등록 결과를 알리는 공용 모달.
 *
 * (#329) 가족 몫 등록(FamilyTrackerView)은 이 모달로 결과를 알렸지만 본인 몫 등록
 * (MedicationPage)은 window.alert를 써서 같은 동작인데 화면이 달라 보였다 — 두 화면이
 * 같은 컴포넌트를 쓰도록 여기로 뽑았다.
 */
export default function MedicationResultModal({ message, onClose, tone = "success" }: Props) {
  const isWarning = tone === "warning";
  const badgeBg = isWarning ? "#B8860B" : t.primary;

  return (
    <Modal onClose={onClose}>
      <div
        style={{
          background: t.cardBg,
          border: `1px solid ${t.border}`,
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
              background: isWarning ? "#FDF3DC" : t.primarySoft,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Pill size={26} color={badgeBg} />
          </div>
          <div
            style={{
              position: "absolute",
              bottom: -2,
              right: -2,
              width: 20,
              height: 20,
              borderRadius: "50%",
              background: badgeBg,
              border: `2px solid ${t.cardBg}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {isWarning ? (
              <AlertTriangle size={11} color="#fff" strokeWidth={3} />
            ) : (
              <Check size={12} color="#fff" strokeWidth={3} />
            )}
          </div>
        </div>
        <p
          style={{
            margin: "0 0 18px",
            fontSize: 15,
            fontWeight: 700,
            lineHeight: 1.6,
            color: t.text,
          }}
        >
          {message}
        </p>
        <button
          type="button"
          onClick={onClose}
          style={{
            width: "100%",
            padding: "10px",
            border: "none",
            borderRadius: 10,
            background: t.primary,
            color: "#fff",
            fontWeight: 700,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          확인
        </button>
      </div>
    </Modal>
  );
}
