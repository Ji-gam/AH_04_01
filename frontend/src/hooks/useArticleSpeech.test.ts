/**
 * T-ACC-1 낭독 훅 테스트.
 *
 * jsdom에는 `speechSynthesis`가 없어서 가짜 구현을 심는다. 전역 setup.ts가 아니라 이 파일에
 * 두는 이유는, "음성 기능이 아예 없는 기기"도 테스트해야 해서다 - 전역으로 항상 심어두면
 * 그 경우를 만들 수 없다.
 *
 * 특히 지키려는 것 두 가지:
 *   1. `start()`가 **동기로** speak을 호출한다 (아이폰이 클릭 핸들러를 벗어난 발화를 무시한다)
 *   2. 정지/일시정지 후에 낡은 `onend`가 와도 큐가 진행되지 않는다 (`runId` 가드)
 */
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useArticleSpeech } from "./useArticleSpeech";

interface FakeUtterance {
  text: string;
  lang: string;
  rate: number;
  voice: SpeechSynthesisVoice | null;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

let spoken: FakeUtterance[] = [];
let speaking = false;
let voices: { lang: string; name: string }[] = [];
/** true면 speak()가 onstart를 부르지 않는다 - 아이폰 standalone 무음 재현용. */
let silent = false;

function installFakeSpeech() {
  spoken = [];
  speaking = false;
  silent = false;
  voices = [{ lang: "ko-KR", name: "Yuna" }];

  class FakeSpeechSynthesisUtterance implements FakeUtterance {
    text: string;
    lang = "";
    rate = 1;
    voice: SpeechSynthesisVoice | null = null;
    onstart: (() => void) | null = null;
    onend: (() => void) | null = null;
    onerror: (() => void) | null = null;

    constructor(text: string) {
      this.text = text;
    }
  }

  vi.stubGlobal("SpeechSynthesisUtterance", FakeSpeechSynthesisUtterance);
  vi.stubGlobal("speechSynthesis", {
    speak(utterance: FakeUtterance) {
      spoken.push(utterance);
      if (silent) return;
      speaking = true;
      utterance.onstart?.();
    },
    cancel() {
      speaking = false;
    },
    getVoices: () => voices,
    get speaking() {
      return speaking;
    },
  });
}

/** 마지막으로 넘긴 발화가 끝난 것처럼 만든다. */
function finishLast() {
  const last = spoken[spoken.length - 1];
  speaking = false;
  act(() => {
    last.onend?.();
  });
}

const TITLE = "기사 제목";
const BODY = "첫째 단락이다.\n\n둘째 단락이다.\n\n셋째 단락이다.";

beforeEach(installFakeSpeech);
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useArticleSpeech", () => {
  it("reports unsupported when the device has no speech engine", () => {
    vi.unstubAllGlobals();
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    expect(result.current.status).toBe("unsupported");
  });

  it("starts idle and knows how many paragraphs there are", () => {
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    expect(result.current.status).toBe("idle");
    expect(result.current.paragraphCount).toBe(3);
    expect(result.current.currentParagraphIndex).toBeNull();
  });

  it("speaks synchronously inside start() so iOS accepts it", () => {
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    // await 없이, start()가 반환되기 전에 이미 speak이 호출돼 있어야 한다.
    act(() => {
      result.current.start();
      expect(spoken).toHaveLength(1);
    });

    expect(spoken[0].text).toBe(TITLE);
    expect(spoken[0].lang).toBe("ko-KR");
    expect(result.current.status).toBe("speaking");
  });

  it("reads the title first, then walks through the paragraphs", () => {
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.start());
    // 제목을 읽는 동안에는 하이라이트할 단락이 없다.
    expect(result.current.currentParagraphIndex).toBeNull();

    finishLast();
    expect(spoken[1].text).toBe("첫째 단락이다.");
    expect(result.current.currentParagraphIndex).toBe(0);
    expect(result.current.spokenParagraphNumber).toBe(1);

    finishLast();
    expect(result.current.currentParagraphIndex).toBe(1);

    finishLast();
    expect(result.current.currentParagraphIndex).toBe(2);

    // 마지막 단락까지 끝나면 처음으로 되돌아간다.
    finishLast();
    expect(result.current.status).toBe("idle");
    expect(result.current.currentParagraphIndex).toBeNull();
    expect(spoken).toHaveLength(4);
  });

  it("picks a Korean voice when the device has one", () => {
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.start());

    expect(spoken[0].voice).toEqual({ lang: "ko-KR", name: "Yuna" });
  });

  it("still speaks when the voice list is not loaded yet", () => {
    // 아이폰은 목소리 목록을 비동기로 채운다. 기다리면 발화 자체가 무시되므로 그냥 진행해야 한다.
    voices = [];
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.start());

    expect(spoken).toHaveLength(1);
    expect(spoken[0].voice).toBeNull();
    expect(spoken[0].lang).toBe("ko-KR");
  });

  it("stops immediately and does not advance on a late onend", () => {
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.start());
    const cancelled = spoken[spoken.length - 1];

    act(() => result.current.stop());
    expect(result.current.status).toBe("idle");

    // cancel() 뒤에 뒤늦게 onend를 부르는 브라우저가 있다. 이때 큐가 이어지면 정지가 무의미해진다.
    act(() => cancelled.onend?.());
    expect(spoken).toHaveLength(1);
    expect(result.current.status).toBe("idle");
  });

  it("resumes the paragraph it was paused on", () => {
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.start());
    finishLast();
    expect(spoken[1].text).toBe("첫째 단락이다.");

    act(() => result.current.pause());
    expect(result.current.status).toBe("paused");
    // 일시정지 중에도 하이라이트는 그 단락에 남아 있어야 한다.
    expect(result.current.currentParagraphIndex).toBe(0);

    act(() => result.current.resume());
    expect(result.current.status).toBe("speaking");
    expect(spoken[2].text).toBe("첫째 단락이다.");
  });

  it("restarts the current paragraph at the new speed", () => {
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.start());
    finishLast();
    const beforeRate = spoken[1].rate;

    act(() => result.current.setRate("fast"));

    expect(result.current.rate).toBe("fast");
    expect(spoken[2].text).toBe("첫째 단락이다.");
    expect(spoken[2].rate).toBeGreaterThan(beforeRate);
  });

  it("does not restart when the speed changes while stopped", () => {
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.setRate("slow"));

    expect(spoken).toHaveLength(0);
    expect(result.current.status).toBe("idle");
  });

  it("falls back to a notice when the device stays silent", () => {
    // 아이폰 standalone 무음: speak()은 받아들여지지만 소리도, 오류 이벤트도 오지 않는다.
    vi.useFakeTimers();
    silent = true;
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.start());
    expect(result.current.failed).toBe(false);

    act(() => vi.advanceTimersByTime(3000));

    expect(result.current.failed).toBe(true);
    expect(result.current.status).toBe("idle");
  });

  it("reports failure when the engine raises an error", () => {
    const { result } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.start());
    act(() => spoken[0].onerror?.());

    expect(result.current.failed).toBe(true);
    expect(result.current.status).toBe("idle");
  });

  it("cancels playback when the screen goes away", () => {
    const cancel = vi.spyOn(window.speechSynthesis, "cancel");
    const { result, unmount } = renderHook(() => useArticleSpeech(TITLE, BODY));

    act(() => result.current.start());
    cancel.mockClear();
    unmount();

    // 없으면 다른 화면으로 이동해도 기사를 계속 읽는다.
    expect(cancel).toHaveBeenCalled();
  });

  it("does nothing when there is no article yet", () => {
    const { result } = renderHook(() => useArticleSpeech("", ""));

    act(() => result.current.start());

    expect(spoken).toHaveLength(0);
    expect(result.current.status).toBe("idle");
  });
});
