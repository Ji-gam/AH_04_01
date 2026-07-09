import { useEffect, type ReactNode } from "react";

interface Props {
  onClose: () => void;
  children: ReactNode;
}

/**
 * 화면 중앙에 콘텐츠를 띄우는 공용 모달.
 * 어두운 배경을 클릭하거나 ESC를 누르면 닫힌다. 열려 있는 동안 뒤 배경 스크롤을 막는다.
 */
export default function Modal({ onClose, children }: Props) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(90, 74, 78, 0.45)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: "100%", maxWidth: 440, maxHeight: "85vh", overflowY: "auto" }}
      >
        {children}
      </div>
    </div>
  );
}
