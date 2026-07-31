import { Trash2 } from "lucide-react";

import Modal from "../../pages/AlarmPage/components/Modal";
import { pinkTheme as t } from "../../theme/pinkTheme";

interface Props {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  /** 실행 버튼 문구. 기본값 "삭제". */
  confirmLabel?: string;
  /** 실행 중에는 버튼을 잠가 중복 요청을 막는다. */
  isBusy?: boolean;
}

/**
 * 되돌릴 수 없는 동작(주로 삭제)을 실행하기 전에 확인받는 공용 모달.
 *
 * (#331) 약 삭제가 브라우저 기본 `window.confirm`을 쓰고 있어, 등록 결과 안내
 * ([[MedicationResultModal]])만 앱 디자인이고 삭제 확인은 OS 대화상자가 떠서 어긋났다.
 */
export default function ConfirmModal({
  message,
  onConfirm,
  onCancel,
  confirmLabel = "삭제",
  isBusy = false,
}: Props) {
  return (
    <Modal onClose={onCancel}>
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
        <div
          style={{
            width: 52,
            height: 52,
            margin: "0 auto 12px",
            borderRadius: "50%",
            background: "#FDECEF",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Trash2 size={24} color={t.danger} />
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
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            onClick={onCancel}
            disabled={isBusy}
            style={{
              flex: 1,
              padding: "10px",
              border: `1px solid ${t.border}`,
              borderRadius: 10,
              background: t.cardBg,
              color: t.text,
              fontWeight: 700,
              fontSize: 13,
              cursor: isBusy ? "not-allowed" : "pointer",
            }}
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isBusy}
            style={{
              flex: 1,
              padding: "10px",
              border: "none",
              borderRadius: 10,
              background: t.danger,
              color: "#fff",
              fontWeight: 700,
              fontSize: 13,
              cursor: isBusy ? "not-allowed" : "pointer",
              opacity: isBusy ? 0.7 : 1,
            }}
          >
            {isBusy ? "처리 중..." : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
