import { useEffect, useRef, useState } from "react";

import Modal from "../../pages/AlarmPage/components/Modal";

export interface ShareSheetProps {
  title: string;
  // 기본값은 현재 페이지 URL — 상세화면(/info/:id)에서 그대로 쓰면 된다.
  url?: string;
}

/** 상세화면 공유 UI(T-LLM-3-1). 공유 아이콘 버튼을 누르면 모달로 3개 옵션(URL 복사/X/카카오톡)을
 * 보여준다. URL 복사/X는 앱 등록·API 키 없이 바로 동작한다. 카카오톡은 Kakao Developers 앱
 * 등록(사람이 해야 함, 배포 도메인 필요)이 선행돼야 해서 지금은 안내만 띄운다 — 실연동은
 * 별도 이슈(#164)로 추적한다. */
export function ShareSheet({ title, url }: ShareSheetProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(timerRef.current), []);

  function notify(message: string) {
    setToast(message);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setToast(null), 1600);
  }

  function shareUrl() {
    return url ?? window.location.href;
  }

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(shareUrl());
      notify("링크가 복사됐어요");
    } catch {
      notify("링크 복사에 실패했어요");
    } finally {
      setIsModalOpen(false);
    }
  }

  function handleShareToX() {
    const params = new URLSearchParams({ url: shareUrl(), text: title });
    window.open(
      `https://twitter.com/intent/tweet?${params.toString()}`,
      "_blank",
      "noopener,noreferrer",
    );
    setIsModalOpen(false);
  }

  function handleShareToKakao() {
    // Kakao Share SDK는 Kakao Developers 앱 등록 + JS 키 + 배포 도메인 등록이 선행돼야
    // 동작한다(사람이 해야 하는 일). 배포 전인 지금은 안내만 띄운다 — 후속 이슈에서 실연동.
    notify("카카오톡 공유는 준비 중이에요");
    setIsModalOpen(false);
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setIsModalOpen(true)}
        aria-label="공유하기"
        className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-white text-lg transition-transform active:scale-95"
      >
        📤
      </button>

      {isModalOpen && (
        <Modal onClose={() => setIsModalOpen(false)}>
          <div className="rounded-2xl bg-background p-5">
            <p className="mb-4 text-sm font-semibold">공유하기</p>
            <div className="flex flex-col gap-1">
              <ShareOption icon="🔗" label="URL 복사" onClick={handleCopyLink} />
              <ShareOption icon="𝕏" label="X" onClick={handleShareToX} />
              <ShareOption icon="💬" label="카카오톡" onClick={handleShareToKakao} />
            </div>
          </div>
        </Modal>
      )}

      {toast && (
        <div className="absolute left-1/2 top-full z-10 mt-2 -translate-x-1/2 whitespace-nowrap rounded-full bg-foreground/90 px-4 py-2 text-xs text-background">
          {toast}
        </div>
      )}
    </div>
  );
}

function ShareOption({
  icon,
  label,
  onClick,
}: {
  icon: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm hover:bg-secondary"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-white text-base">
        {icon}
      </span>
      {label}
    </button>
  );
}
