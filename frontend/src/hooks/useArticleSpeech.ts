/**
 * T-ACC-1 기사 낭독 훅. 기기에 이미 있는 음성 기능(`speechSynthesis`)으로 기사 원문을 읽어준다.
 * 서버에서 mp3를 만들지 않는 이유는 `docs/tasks/T-ACC-1-news-article-tts.md` 2절 참고.
 *
 * [아이폰 때문에 이렇게 만들었다] 맥 사파리와 아이폰 사파리가 이 API에서 갈리는데, 나중에
 * 고칠 문제가 아니라 처음부터 구조에 들어가야 하는 것들이다.
 *
 *   1. **첫 발화는 클릭 핸들러 안에서 동기로 실행해야 한다.** 아이폰은 클릭 핸들러에서 뭔가를
 *      기다린 뒤(await, setTimeout) 말을 시키면 무시한다. 맥은 그냥 봐준다. 그래서 `start()`는
 *      목소리 목록 로딩을 기다리지 않고 곧바로 `speak()`를 호출한다.
 *   2. **긴 텍스트는 중간에 끊긴다.** 그래서 조각(`buildSpeechChunks`)을 한 번에 큐에 밀어넣지
 *      않고, 하나가 끝나면 다음 하나를 넣는 식으로 직렬 재생한다. 진행 상황을 정확히 알 수
 *      있는 것도 같은 구조 덕분이다(PRD F-ACC-1의 "어디를 읽고 있는지").
 *   3. **음성이 없거나 시작에 실패할 수 있다.** 특히 홈화면에 추가한 앱 모드(standalone)에서
 *      무음 사례가 보고돼 있다. 그래서 시작 후에도 소리가 나지 않으면 `failed`를 켜서 호출부가
 *      안내 문구로 격하할 수 있게 한다 - 버튼을 죽이거나 화면을 깨뜨리지 않는다.
 *
 * [일시정지를 native pause로 하지 않는 이유] `speechSynthesis.pause()`는 아이폰에서 신뢰할 수
 * 없다(멈추지 않거나, `paused`가 true인데 소리가 계속 나거나). 그래서 기기별로 다르게 동작하는
 * 코드 두 벌을 두지 않고, **모든 기기에서 같은 방식**을 쓴다: 일시정지는 취소 + 위치 기억,
 * 이어듣기는 그 조각부터 다시 재생. 대가는 이어들을 때 그 조각(최대 180자)을 처음부터 다시
 * 읽는 것인데, 조각이 짧아 부담이 적고 낭독 기능에서는 오히려 문맥이 이어져 낫다.
 * 같은 방식이 재생 속도 변경에도 그대로 쓰인다(발화 중에는 속도를 바꿀 수 없어 다시 시작해야 함).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { buildSpeechChunks, splitParagraphs } from "@/lib/ttsText";

export type SpeechStatus = "unsupported" | "idle" | "speaking" | "paused";

export type SpeechRate = "slow" | "normal" | "fast";

/**
 * "보통"이 1.0이 아닌 이유: PRD F-ACC-1이 이 기능을 **고령 사용자 접근성**으로 규정하고 있어
 * 기본값을 브라우저 기본 속도보다 조금 느리게 잡았다.
 */
const RATE_VALUES: Record<SpeechRate, number> = {
  slow: 0.7,
  normal: 0.9,
  fast: 1.15,
};

/**
 * `start()` 후 이 시간 안에 발화가 시작되지 않으면 실패로 본다. 아이폰 standalone 무음처럼
 * 오류 이벤트조차 오지 않는 경우를 잡기 위한 장치다.
 */
const START_TIMEOUT_MS = 2500;

function findKoreanVoice(): SpeechSynthesisVoice | null {
  // 목록이 아직 비어 있을 수 있다(아이폰은 비동기 로딩). 기다리지 않는다 - 위 1번 제약.
  const voices = window.speechSynthesis.getVoices();
  return voices.find((voice) => voice.lang?.toLowerCase().startsWith("ko")) ?? null;
}

export function useArticleSpeech(title: string, bodyText: string) {
  const chunks = useMemo(() => buildSpeechChunks(title, bodyText), [title, bodyText]);
  const paragraphCount = useMemo(() => splitParagraphs(bodyText).length, [bodyText]);

  const [status, setStatus] = useState<SpeechStatus>("idle");
  const [rate, setRateState] = useState<SpeechRate>("normal");
  const [chunkIndex, setChunkIndex] = useState(0);
  const [failed, setFailed] = useState(false);

  /**
   * 재생 세션 번호. `cancel()`이 이미 끝난 발화의 `onend`를 뒤늦게 호출하는 브라우저가 있어,
   * 이 번호가 다르면 낡은 콜백으로 보고 무시한다. 없으면 정지한 뒤에도 큐가 계속 진행된다.
   */
  const runIdRef = useRef(0);
  const chunkIndexRef = useRef(0);
  const rateRef = useRef<SpeechRate>("normal");
  const startTimerRef = useRef<number | null>(null);
  const chunksRef = useRef(chunks);
  chunksRef.current = chunks;

  const isSupported = typeof window !== "undefined" && "speechSynthesis" in window;

  const clearStartTimer = useCallback(() => {
    if (startTimerRef.current !== null) {
      window.clearTimeout(startTimerRef.current);
      startTimerRef.current = null;
    }
  }, []);

  /** 한 조각을 읽고, 끝나면 다음 조각으로 이어간다. 낡은 세션의 콜백은 전부 무시한다. */
  const speakChunk = useCallback(
    (index: number, runId: number) => {
      if (runId !== runIdRef.current) return;

      const list = chunksRef.current;
      if (index >= list.length) {
        // 끝까지 읽었다. 처음으로 되돌려 다시 들을 수 있게 한다.
        chunkIndexRef.current = 0;
        setChunkIndex(0);
        setStatus("idle");
        return;
      }

      const utterance = new SpeechSynthesisUtterance(list[index].text);
      utterance.lang = "ko-KR";
      utterance.rate = RATE_VALUES[rateRef.current];
      const voice = findKoreanVoice();
      // 목소리를 못 찾아도 lang만 주고 맡긴다 - 엔진이 알아서 고르는 편이 무음보다 낫다.
      if (voice) utterance.voice = voice;

      utterance.onstart = () => {
        if (runId !== runIdRef.current) return;
        clearStartTimer();
      };

      utterance.onend = () => {
        if (runId !== runIdRef.current) return;
        chunkIndexRef.current = index + 1;
        setChunkIndex(index + 1);
        speakChunk(index + 1, runId);
      };

      utterance.onerror = () => {
        if (runId !== runIdRef.current) return;
        clearStartTimer();
        // 조각 하나가 실패하면 나머지도 같은 이유로 실패할 가능성이 높아 재생을 끝낸다.
        runIdRef.current += 1;
        setStatus("idle");
        setFailed(true);
      };

      window.speechSynthesis.speak(utterance);
    },
    [clearStartTimer],
  );

  /**
   * `from` 조각부터 재생을 시작한다. **클릭 핸들러에서 동기로 호출되어야 한다**(위 1번 제약)
   * — 이 함수 안에서 await하거나 타이머를 거친 뒤 speak하면 아이폰이 무시한다.
   */
  const startRun = useCallback(
    (from: number) => {
      if (!isSupported || chunksRef.current.length === 0) return;

      window.speechSynthesis.cancel();
      const runId = runIdRef.current + 1;
      runIdRef.current = runId;

      chunkIndexRef.current = from;
      setChunkIndex(from);
      setFailed(false);
      setStatus("speaking");

      speakChunk(from, runId);

      // 소리가 정말 나기 시작했는지 확인한다. onstart가 오면 이 타이머는 취소된다.
      clearStartTimer();
      startTimerRef.current = window.setTimeout(() => {
        startTimerRef.current = null;
        if (runId !== runIdRef.current) return;
        if (window.speechSynthesis.speaking) return;
        runIdRef.current += 1;
        window.speechSynthesis.cancel();
        setStatus("idle");
        setFailed(true);
      }, START_TIMEOUT_MS);
    },
    [clearStartTimer, isSupported, speakChunk],
  );

  const start = useCallback(() => startRun(0), [startRun]);

  /** 재생을 완전히 끝내고 처음으로 되돌린다 (TRD T-ACC-1: 정지 버튼으로 즉시 중단). */
  const stop = useCallback(() => {
    runIdRef.current += 1;
    clearStartTimer();
    if (isSupported) window.speechSynthesis.cancel();
    chunkIndexRef.current = 0;
    setChunkIndex(0);
    setStatus("idle");
  }, [clearStartTimer, isSupported]);

  /** 현재 조각 위치를 기억한 채 소리만 끊는다. 이어듣기는 그 조각을 처음부터 다시 읽는다. */
  const pause = useCallback(() => {
    runIdRef.current += 1;
    clearStartTimer();
    if (isSupported) window.speechSynthesis.cancel();
    setStatus("paused");
  }, [clearStartTimer, isSupported]);

  const resume = useCallback(() => startRun(chunkIndexRef.current), [startRun]);

  const setRate = useCallback(
    (next: SpeechRate) => {
      rateRef.current = next;
      setRateState(next);
      // 발화 중인 utterance의 속도는 바꿀 수 없다 - 현재 조각부터 새 속도로 다시 시작한다.
      if (status === "speaking") startRun(chunkIndexRef.current);
    },
    [startRun, status],
  );

  // 화면을 벗어나면 즉시 멈춘다. 없으면 다른 화면으로 이동해도 기사를 계속 읽는다.
  useEffect(() => {
    return () => {
      runIdRef.current += 1;
      if (startTimerRef.current !== null) window.clearTimeout(startTimerRef.current);
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // 기사가 바뀌면(상세화면에서 다른 기사로 이동) 재생 상태를 초기화한다.
  useEffect(() => {
    runIdRef.current += 1;
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    chunkIndexRef.current = 0;
    setChunkIndex(0);
    setStatus("idle");
    setFailed(false);
  }, [chunks]);

  const currentChunk = chunks[Math.min(chunkIndex, Math.max(chunks.length - 1, 0))];
  const currentParagraphIndex = status === "idle" ? null : (currentChunk?.paragraphIndex ?? null);

  return {
    status: isSupported ? status : ("unsupported" as SpeechStatus),
    failed,
    /** 하이라이트할 단락 번호. 제목을 읽는 중이거나 정지 상태면 null. */
    currentParagraphIndex,
    /** 진행 표시용. 제목을 읽는 중이면 0. */
    spokenParagraphNumber: currentParagraphIndex === null ? 0 : currentParagraphIndex + 1,
    paragraphCount,
    rate,
    setRate,
    start,
    pause,
    resume,
    stop,
  };
}
