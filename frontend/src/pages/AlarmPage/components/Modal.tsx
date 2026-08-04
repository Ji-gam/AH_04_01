import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  onClose: () => void;
  children: ReactNode;
}

/** 현재 열려 있는 모달들의 스택(마운트 순서). 모달이 중첩됐을 때(예: 홈 > 마이다이어리 허브
 * > 식단 기록) ESC가 모든 모달을 한꺼번에 닫아버리면 안 되므로, 가장 위(마지막에 열린) 모달만
 * ESC에 반응하게 하려고 둔다. 배경 클릭은 이미 안쪽 모달만 닫힌다(안쪽 백드롭 클릭이 바깥
 * 콘텐츠 래퍼의 stopPropagation에 막혀서 바깥까지 전파되지 않음). */
const modalStack: object[] = [];

/**
 * 화면 중앙에 콘텐츠를 띄우는 공용 모달.
 * 어두운 배경을 클릭하거나 ESC를 누르면 닫힌다. 열려 있는 동안 뒤 배경 스크롤을 막는다.
 */
export default function Modal({ onClose, children }: Props) {
  // 스택 등록/해제는 마운트·언마운트에만 일어나야 한다 - onClose가 인라인 화살표 함수로
  // 넘어오는 호출부가 많아서(매 렌더 새 identity) 의존성에 넣으면 리렌더마다 스택 순서가
  // 뒤집혀 "가장 위 모달" 판정이 틀어진다. 그래서 최신 onClose는 ref로 읽는다.
  const tokenRef = useRef({});
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const token = tokenRef.current;
    modalStack.push(token);

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (modalStack[modalStack.length - 1] !== token) return; // 내 위에 다른 모달이 있으면 무시
      onCloseRef.current();
    };
    document.addEventListener("keydown", onKeyDown);

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      const index = modalStack.indexOf(token);
      if (index !== -1) modalStack.splice(index, 1);
      // 중첩된 경우 안쪽이 닫혀도 바깥 모달이 설정한 "hidden"으로 되돌아가므로
      // 스크롤 잠금은 그대로 유지된다(바깥이 닫힐 때 원래 값으로 복원).
      document.body.style.overflow = prevOverflow;
    };
  }, []);

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
