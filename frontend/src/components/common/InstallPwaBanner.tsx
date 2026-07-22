import { useEffect, useState } from "react";

import { pinkTheme } from "../../theme/pinkTheme";
import { dismissInstallPrompt, isInstallPromptDismissed } from "../../utils/installPromptDismiss";

// 표준 DOM 타입에 없는 이벤트라 직접 선언한다 (Chrome/Edge/Android만 지원, iOS Safari는
// 이 이벤트 자체가 없다 - 그래서 아래에서 iOS는 별도 안내 문구로 분기한다).
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function isIos(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

function isStandalone(): boolean {
  // 이미 "홈 화면에서 실행 중"이면(설치됨) 배너를 보여줄 필요가 없다.
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

/** "홈 화면에 추가" 설치 유도 배너(2026-07-21, 선택 기능) - 없어도 앱 사용에 지장 없고,
 * 닫으면 이 기기에서는 다시 안 뜬다(installPromptDismiss.ts).
 * - Android/데스크톱 Chrome/Edge: `beforeinstallprompt` 이벤트를 가로채서 "설치하기"
 *   버튼을 누르면 그 즉시 네이티브 설치창을 띄운다.
 * - iOS Safari: 이 이벤트 자체를 지원 안 해서, "공유 > 홈 화면에 추가"를 직접 누르라는
 *   안내 문구만 보여준다(자동 설치 트리거 API가 없음). */
export default function InstallPwaBanner() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [showIosHint, setShowIosHint] = useState(false);
  const [dismissed, setDismissed] = useState(() => isInstallPromptDismissed());

  useEffect(() => {
    if (isStandalone() || isInstallPromptDismissed()) return;

    if (isIos()) {
      setShowIosHint(true);
      return;
    }

    function handleBeforeInstallPrompt(e: Event) {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    }
    function handleInstalled() {
      setDeferredPrompt(null);
      dismissInstallPrompt();
      setDismissed(true);
    }

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      window.removeEventListener("appinstalled", handleInstalled);
    };
  }, []);

  function handleDismiss() {
    dismissInstallPrompt();
    setDismissed(true);
  }

  async function handleInstallClick() {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    // 수락/거절 상관없이 네이티브 설치창은 브라우저당 한 번만 뜨므로(재사용 불가),
    // 배너도 같이 닫는다 - 거절했어도 다시 이 배너로 조를 필요는 없다.
    setDeferredPrompt(null);
    dismissInstallPrompt();
    setDismissed(true);
  }

  if (dismissed || (!deferredPrompt && !showIosHint)) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 14px",
        background: pinkTheme.primarySoft,
        borderBottom: `1px solid ${pinkTheme.border}`,
      }}
    >
      <span style={{ fontSize: 20 }} aria-hidden>
        📲
      </span>
      <div style={{ flex: 1, fontSize: 12.5, color: pinkTheme.text, lineHeight: 1.4 }}>
        {showIosHint ? (
          <>
            홈 화면에 추가하면 앱처럼 쓸 수 있어요 —{" "}
            <strong>공유 버튼 → &quot;홈 화면에 추가&quot;</strong>를 눌러보세요.
          </>
        ) : (
          "Re:Medi를 홈 화면에 추가하고 앱처럼 사용해보세요."
        )}
      </div>
      {!showIosHint && (
        <button
          type="button"
          onClick={handleInstallClick}
          style={{
            border: "none",
            borderRadius: 999,
            background: pinkTheme.primary,
            color: "#fff",
            fontSize: 12,
            fontWeight: 700,
            padding: "6px 12px",
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          설치하기
        </button>
      )}
      <button
        type="button"
        aria-label="설치 배너 닫기"
        onClick={handleDismiss}
        style={{
          border: "none",
          background: "none",
          color: pinkTheme.textMuted,
          fontSize: 16,
          lineHeight: 1,
          padding: 4,
          cursor: "pointer",
        }}
      >
        ✕
      </button>
    </div>
  );
}
