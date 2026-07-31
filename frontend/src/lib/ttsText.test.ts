/**
 * T-ACC-1 낭독 텍스트 변환 테스트.
 *
 * 여기 있는 케이스는 상상한 것이 아니라 **실제로 수집된 코메디닷컴 기사 본문에서 뽑은 것들**이다
 * (`docs/tasks/T-ACC-1-news-article-tts.md` 4절 표와 1:1 대응). 전처리 결과를 DB에 저장하지 않는
 * 설계라 규칙에 버그가 있으면 모든 기사에 동시에 나타난다 - 그 위험을 여기서 막는다.
 */
import { describe, expect, it } from "vitest";

import {
  SPEECH_MAX_CHUNK_CHARS,
  buildSpeechChunks,
  splitParagraphs,
  toSpeechText,
} from "./ttsText";

describe("toSpeechText", () => {
  it("drops URLs that would be read character by character", () => {
    expect(toSpeechText("자세한 내용은 https://kormedi.com/12345 에서 볼 수 있다.")).toBe(
      "자세한 내용은 에서 볼 수 있다.",
    );
    expect(toSpeechText("출처 www.kormedi.com 참고")).toBe("출처 참고");
  });

  it("keeps only the visible text of markdown links", () => {
    expect(toSpeechText("[관련 기사](https://example.com)를 참고하라")).toBe(
      "관련 기사를 참고하라",
    );
    expect(toSpeechText("![혈압계 사진](https://example.com/a.jpg)")).toBe("혈압계 사진");
  });

  it("removes parentheses that only restate a name in the Latin alphabet", () => {
    expect(toSpeechText("미국심리학회(APA)가 발행하는")).toBe("미국심리학회가 발행하는");
    expect(toSpeechText("영국의학저널(BMJ)에 실렸다")).toBe("영국의학저널에 실렸다");
    expect(toSpeechText("생성형 인공지능(AI) 챗봇이")).toBe("생성형 인공지능 챗봇이");
    expect(
      toSpeechText("정신병리학 및 임상과학 저널(Journal of Psychopathology and Clinical Science)"),
    ).toBe("정신병리학 및 임상과학 저널");
  });

  it("keeps parentheses that carry information", () => {
    // 숫자로 시작하는 괄호는 지우면 정보가 사라진다.
    expect(toSpeechText("위험이 높았다(30%)")).toBe("위험이 높았다(30퍼센트)");
    expect(toSpeechText("29일(현지시간) 발표했다")).toBe("29일(현지시간) 발표했다");
  });

  it("strips quotation brackets but keeps the title inside", () => {
    expect(toSpeechText("국제학술지 《정신병리학 저널》에 게재된")).toBe(
      "국제학술지 정신병리학 저널에 게재된",
    );
    expect(toSpeechText("「건강수명」 보고서")).toBe("건강수명 보고서");
  });

  it("reads units in Korean instead of Latin letters", () => {
    expect(toSpeechText("하루 500mg을 복용")).toBe("하루 500밀리그램을 복용");
    expect(toSpeechText("몸무게가 63kg까지 빠졌다")).toBe("몸무게가 63킬로그램까지 빠졌다");
    expect(toSpeechText("혈압이 120mmHg 미만")).toBe("혈압이 120밀리미터 수은주 미만");
    expect(toSpeechText("공복혈당 126mg/dL 이상")).toBe("공복혈당 126밀리그램 퍼 데시리터 이상");
    expect(toSpeechText("하루 2000kcal")).toBe("하루 2000킬로칼로리");
    expect(toSpeechText("사망위험이 47% 낮았다")).toBe("사망위험이 47퍼센트 낮았다");
    expect(toSpeechText("체온이 37.5℃를 넘으면")).toBe("체온이 37.5도를 넘으면");
  });

  it("reads a numeric range as 'A에서 B'", () => {
    expect(toSpeechText("30~40대 남성에게서")).toBe("30에서 40대 남성에게서");
    expect(toSpeechText("7 ~ 8시간 수면")).toBe("7에서 8시간 수면");
  });

  it("turns the interpunct into a comma so the voice pauses", () => {
    expect(toSpeechText("혈압·혈당·콜레스테롤을 관리")).toBe("혈압, 혈당, 콜레스테롤을 관리");
  });

  it("removes markdown emphasis and heading markers", () => {
    expect(toSpeechText("## 핵심 요약")).toBe("핵심 요약");
    expect(toSpeechText("**중요한** 사실")).toBe("중요한 사실");
  });

  it("removes decorative symbols and collapses whitespace", () => {
    expect(toSpeechText("※ 주의  ▲ 증가")).toBe("주의 증가");
    expect(toSpeechText("  앞뒤 공백  ")).toBe("앞뒤 공백");
  });

  it("strips brackets around subheadings", () => {
    expect(toSpeechText("[자주 묻는 질문]")).toBe("자주 묻는 질문");
  });

  it("handles an ellipsis the way the source actually writes it", () => {
    // 문장 중간이면 쉼표로 바꿔 숨을 쉬게 한다.
    expect(toSpeechText("결론은…이렇다")).toBe("결론은, 이렇다");
    expect(toSpeechText("의존까지...다섯 가지 위험")).toBe("의존까지, 다섯 가지 위험");
    // 문장부호 뒤라면 버린다 - 쉼표로 바꾸면 `된다?, 정신건강`이라는 이상한 문장이 된다.
    expect(toSpeechText("‘독’ 된다?⋯정신건강 악화")).toBe("‘독’ 된다? 정신건강 악화");
    expect(toSpeechText("먹었는데…효과는")).toBe("먹었는데, 효과는");
  });

  it("adds a space when a letter is glued to the end of a sentence", () => {
    // 기사 FAQ가 `인가요?A.`처럼 붙여 쓴다 - 그대로 넘기면 "인가요에이"로 뭉쳐 읽힌다.
    expect(toSpeechText("악화시킨다는 뜻인가요?A. 아직 확정된 것은 아니다.")).toBe(
      "악화시킨다는 뜻인가요? A. 아직 확정된 것은 아니다.",
    );
    // 소수점은 건드리면 안 된다.
    expect(toSpeechText("평균 4.95mmHg 낮았다")).toBe("평균 4.95밀리미터 수은주 낮았다");
  });

  it("handles a real sentence from a collected article", () => {
    const raw =
      "미국심리학회(APA)가 발행하는 국제학술지 《정신병리학 및 임상과학 저널(Journal of " +
      "Psychopathology and Clinical Science)》에 최근 게재된 논문은 AI 챗봇이 정신질환을 가진 " +
      "이용자에게 의도치 않은 부정적 영향을 줄 수 있는 다섯 가지 경로를 제시했다.";

    expect(toSpeechText(raw)).toBe(
      "미국심리학회가 발행하는 국제학술지 정신병리학 및 임상과학 저널에 최근 게재된 논문은 " +
        "AI 챗봇이 정신질환을 가진 이용자에게 의도치 않은 부정적 영향을 줄 수 있는 다섯 가지 " +
        "경로를 제시했다.",
    );
  });
});

describe("splitParagraphs", () => {
  it("splits on blank lines and drops empty paragraphs", () => {
    expect(splitParagraphs("첫 단락\n\n둘째 단락\n\n\n\n셋째 단락")).toEqual([
      "첫 단락",
      "둘째 단락",
      "셋째 단락",
    ]);
  });

  it("returns an empty array for blank input", () => {
    expect(splitParagraphs("")).toEqual([]);
    expect(splitParagraphs("\n\n  \n\n")).toEqual([]);
  });
});

describe("buildSpeechChunks", () => {
  it("reads the title first, then each paragraph in order", () => {
    const chunks = buildSpeechChunks("제목입니다", "첫 단락이다.\n\n둘째 단락이다.");

    expect(chunks).toEqual([
      { text: "제목입니다", paragraphIndex: null },
      { text: "첫 단락이다.", paragraphIndex: 0 },
      { text: "둘째 단락이다.", paragraphIndex: 1 },
    ]);
  });

  it("keeps paragraph numbering aligned with what the screen renders", () => {
    const bodyText = "가 단락\n\n나 단락\n\n다 단락";
    const rendered = splitParagraphs(bodyText);

    for (const chunk of buildSpeechChunks("제목", bodyText)) {
      if (chunk.paragraphIndex === null) continue;
      // 하이라이트가 엉뚱한 단락을 가리키지 않으려면 이 대응이 깨지지 않아야 한다.
      expect(rendered[chunk.paragraphIndex]).toContain(chunk.text);
    }
  });

  it("skips a paragraph that becomes empty after cleanup", () => {
    // 영문 병기만 있던 단락은 다듬으면 아무것도 남지 않는다.
    const chunks = buildSpeechChunks("제목", "본문이다.\n\n(Photo by Getty Images)\n\n마지막이다.");

    expect(chunks.map((chunk) => chunk.text)).toEqual(["제목", "본문이다.", "마지막이다."]);
    // 사라진 단락 때문에 뒤 단락의 번호가 밀리지 않는다(화면 기준 번호를 그대로 쓴다).
    expect(chunks.map((chunk) => chunk.paragraphIndex)).toEqual([null, 0, 2]);
  });

  it("splits a long paragraph into sentence-sized chunks", () => {
    const sentence = "이것은 충분히 긴 한국어 문장이며 낭독 단위를 넘기기 위한 예시 문장이다.";
    const longParagraph = Array(6).fill(sentence).join(" ");

    const chunks = buildSpeechChunks("제목", longParagraph);
    const bodyChunks = chunks.filter((chunk) => chunk.paragraphIndex === 0);

    expect(bodyChunks.length).toBeGreaterThan(1);
    for (const chunk of bodyChunks) {
      expect(chunk.text.length).toBeLessThanOrEqual(SPEECH_MAX_CHUNK_CHARS);
    }
    // 쪼개져도 전부 같은 단락을 가리켜야 하이라이트가 튀지 않는다.
    expect(new Set(bodyChunks.map((chunk) => chunk.paragraphIndex))).toEqual(new Set([0]));
  });

  it("returns no chunks when there is nothing to read", () => {
    expect(buildSpeechChunks("", "")).toEqual([]);
  });
});
