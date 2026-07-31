/**
 * T-ACC-1 낭독용 텍스트 변환. 기사 원문을 "소리로 읽기 좋은 문장 조각들"로 바꾼다.
 *
 * [왜 저장하지 않고 매번 변환하나]
 * 2,250자(수집 기사 평균) 치환은 1,000분의 1초도 안 걸려서 저장해 아낄 게 없다. 반대로
 * 저장해두면 규칙을 하나 고칠 때마다 컬럼 추가 → 마이그레이션 → 전체 재생성 배치가 딸려온다.
 * 이 규칙은 실제로 들어보며 계속 손볼 부분이라 그 비용이 특히 아프다.
 * 자세한 근거는 `docs/tasks/T-ACC-1-news-article-tts.md` 3절.
 *
 * [왜 단락 단위로 쪼개나] 두 가지 이유가 겹친다.
 *   1. 아이폰 사파리는 긴 텍스트를 한 번에 넘기면 중간에 끊긴다.
 *   2. PRD F-ACC-1이 "어디를 읽고 있는지" 표시를 요구한다 - 단락 하나 = 발화 하나로 넘겨야
 *      "한 단락 끝났다" 신호로 하이라이트를 옮길 수 있다.
 *
 * 화면에 보이는 본문은 원문 그대로 두고, 소리로 나갈 때만 다듬는다. 눈으로는 학술지 영문명이
 * 보이고 귀로는 안 들리는 셈인데, 읽어주기 용도로는 그게 맞다.
 */

/** 발화 하나. `paragraphIndex`는 하이라이트할 단락 번호이고, 제목 조각은 `null`이다. */
export interface SpeechChunk {
  text: string;
  paragraphIndex: number | null;
}

/**
 * 발화 하나에 넘길 최대 글자 수. 아이폰 사파리가 긴 발화를 중간에 끊는 것을 피하기 위한
 * 보수적인 값이다(정확한 한계는 iOS 버전마다 다르고 문서화돼 있지 않다).
 */
export const SPEECH_MAX_CHUNK_CHARS = 180;

/**
 * 본문을 단락 배열로 쪼갠다. **화면 렌더링과 낭독이 반드시 같은 함수를 써야 한다** - 서로
 * 다르게 쪼개면 하이라이트가 엉뚱한 단락을 가리킨다. 그래서 InfoDetailPage도 이걸 쓴다.
 */
export function splitParagraphs(bodyText: string): string[] {
  return bodyText
    .split("\n\n")
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph.length > 0);
}

/**
 * 괄호 안이 로마자로 시작하는 영문/숫자뿐이면 괄호째 지운다.
 *
 * 기사에 `미국심리학회(APA)`, `《… 저널(Journal of Psychopathology and Clinical Science)》`처럼
 * 영문 병기가 흔하다. 한국어 음성이 영문을 어색하게(때로는 한 글자씩) 읽는데, 바로 앞에 이미
 * 한국어 명칭이 나와서 지워도 뜻이 상하지 않는다.
 *
 * "로마자로 시작"을 조건에 넣은 이유는 `(30%)`, `(3.5kg)`, `(1)`처럼 숫자만 있는 괄호를
 * 살려두기 위해서다 - 그건 지우면 정보가 사라진다.
 */
function dropLatinParentheticals(text: string): string {
  return text.replace(/\(([^()]*)\)/g, (match, inner: string) =>
    /^[A-Za-z][A-Za-z0-9\s.,''&:;\-–—/+]*$/.test(inner) ? "" : match,
  );
}

/** 숫자에 붙은 단위 기호를 한국어로 바꾼다. 긴 단위를 먼저 처리해야 `mg/dL`이 `mg`로 먹히지 않는다. */
const UNIT_RULES: ReadonlyArray<readonly [RegExp, string]> = [
  [/(\d)\s*mg\s*\/\s*dL\b/gi, "$1밀리그램 퍼 데시리터"],
  [/(\d)\s*mmHg\b/gi, "$1밀리미터 수은주"],
  [/(\d)\s*kcal\b/gi, "$1킬로칼로리"],
  [/(\d)\s*mcg\b/gi, "$1마이크로그램"],
  [/(\d)\s*mg\b/gi, "$1밀리그램"],
  [/(\d)\s*kg\b/gi, "$1킬로그램"],
  [/(\d)\s*cm\b/gi, "$1센티미터"],
  [/(\d)\s*mm\b/gi, "$1밀리미터"],
  [/(\d)\s*ml\b/gi, "$1밀리리터"],
  [/(\d)\s*%/g, "$1퍼센트"],
  [/(\d)\s*℃/g, "$1도"],
  // 화씨는 숫자 앞으로 "화씨"가 나와야 자연스러워서, 다른 규칙과 달리 숫자 전체를 잡는다.
  [/(\d+(?:\.\d+)?)\s*℉/g, "화씨 $1도"],
];

/**
 * 낭독용으로 텍스트를 다듬는다. 순서에 의미가 있다 - URL을 먼저 지우지 않으면 그 안의 `/`나
 * 괄호가 뒤 규칙에 걸려 이상하게 남는다.
 */
export function toSpeechText(raw: string): string {
  let text = raw;

  // 1. 마크다운 링크/이미지는 보이는 글자만 남긴다. **2번보다 먼저** 해야 한다 - 주소를 먼저
  //    지우면 `[글자](` 만 남아 링크 문법이 깨진다. 본문은 수집 단계에서 이미 평문이지만
  //    (app/services/health_news_source.py) TRD 성공요건이라 방어적으로 처리한다.
  text = text.replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1");

  // 2. 주소는 한 글자씩 읽혀서 통째로 버린다. 한국어는 주소 뒤에 조사가 공백 없이 붙는 일이
  //    많아, `\S+`로 잡으면 닫는 괄호와 뒤 한글까지 먹는다 - 경계 문자를 명시적으로 뺀다.
  text = text.replace(/https?:\/\/[^\s)\]}>,]+/gi, " ").replace(/\bwww\.[^\s)\]}>,]+/gi, " ");

  // 3. 영문 병기 괄호 제거.
  text = dropLatinParentheticals(text);

  // 4. 인용 괄호는 기호만 떼고 안쪽 글자는 남긴다(학술지·도서명, `[자주 묻는 질문]` 같은
  //    소제목이 들어있다). 공백이 아니라 빈 문자열로 바꿔야 `저널》에` → `저널에`가 된다
  //    (공백을 넣으면 조사가 떨어져 읽힌다).
  text = text.replace(/[《》〈〉「」『』【】[\]]/g, "");

  // 5. 숫자 범위의 물결. **6번보다 먼저** 처리해야 한다 - 6번이 `~`를 마크다운 기호로 보고
  //    지워버리면 `30~40대`가 `3040대`가 된다.
  text = text.replace(/(\d)\s*[~∼〜]\s*(\d)/g, "$1에서 $2");

  // 6. 마크다운 강조·헤딩 기호. 여는 쪽만 지우면 `**강조**`가 `강조**`로 남으므로 전부 지운다.
  text = text.replace(/^#{1,6}\s*/gm, "").replace(/[*_`~]/g, "");

  // 7. 단위 기호 → 한국어.
  for (const [pattern, replacement] of UNIT_RULES) {
    text = text.replace(pattern, replacement);
  }

  // 8. 중간점은 붙여 읽어 뭉개지므로 쉼표로 바꿔 숨을 쉬게 한다.
  text = text.replace(/\s*·\s*/g, ", ");

  // 9. 그 밖에 낭독에 방해가 되는 장식 기호.
  text = text.replace(/[※▲▼■□◆◇○●▶◀→←↑↓]/g, " ");

  // 10. 말줄임표. 코메디닷컴 제목은 `된다?⋯정신건강`처럼 문장부호 바로 뒤에 붙여 쓰는데,
  //     이때 쉼표로 바꾸면 `된다?, 정신건강`이라는 이상한 문장이 된다. 문장부호 뒤에서는
  //     그냥 버리고, 그 밖에는(`의존까지...다섯 가지`) 쉼표로 바꿔 숨을 쉬게 한다.
  //     첫 규칙은 진짜 말줄임표 문자(`…` `⋯`)만 본다 - 마침표 세 개(`...`)까지 넣으면 그
  //     자체가 말줄임표인데 "마침표 + 말줄임표"로 잘못 읽어 `까지. 다섯`이 된다.
  text = text.replace(/([.!?])\s*[…⋯]\s*/g, "$1 ").replace(/(?:[…⋯]|\.{2,})/g, ", ");

  // 11. 문장부호 뒤에 글자가 바로 붙은 경우 띄어준다. 기사 FAQ가 `인가요?A. 아직`처럼 붙여
  //     쓰는데, 그대로 넘기면 "인가요에이"로 뭉쳐 읽힌다. 숫자는 제외해야 `4.95`가 안 깨진다.
  text = text.replace(/([.!?])(?=[A-Za-z가-힣])/g, "$1 ");

  // 12. 위 치환들이 남긴 빈칸 정리. 쉼표 앞 공백과 중복 쉼표까지 걷어낸다.
  //     빈 괄호는 주소만 들어있던 괄호(`(https://…)`)의 잔재다.
  return text
    .replace(/\(\s*\)/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s+([,.!?])/g, "$1")
    .replace(/,(\s*,)+/g, ",")
    .trim();
}

/**
 * 한 단락이 `SPEECH_MAX_CHUNK_CHARS`를 넘으면 문장 단위로 다시 쪼갠다. 문장 하나가 그보다도
 * 길면 마지막 공백에서 자른다(자를 곳이 없으면 그냥 넘긴다 - 안 읽는 것보다는 낫다).
 */
function splitIntoSpeakableParts(text: string, max: number): string[] {
  if (text.length <= max) return [text];

  // 문장부호 뒤 공백에서 끊는다. 한국어 기사는 대부분 "…했다. " 형태로 끝난다.
  const sentences = text.split(/(?<=[.!?])\s+/);
  const parts: string[] = [];
  let buffer = "";

  const flush = () => {
    if (buffer.length > 0) {
      parts.push(buffer);
      buffer = "";
    }
  };

  for (const sentence of sentences) {
    if (buffer.length > 0 && buffer.length + 1 + sentence.length > max) flush();

    if (sentence.length <= max) {
      buffer = buffer.length > 0 ? `${buffer} ${sentence}` : sentence;
      continue;
    }

    // 문장 하나가 한계를 넘는 경우.
    flush();
    let rest = sentence;
    while (rest.length > max) {
      const cut = rest.lastIndexOf(" ", max);
      if (cut <= 0) break;
      parts.push(rest.slice(0, cut));
      rest = rest.slice(cut + 1);
    }
    buffer = rest;
  }

  flush();
  return parts;
}

/**
 * 기사를 낭독 조각들로 만든다. 제목을 먼저 읽고 본문 단락을 순서대로 읽는다(면책문구는 읽지 않음).
 * 다듬은 결과가 빈 문자열인 조각은 버린다 - 영문 병기만 있던 단락이 통째로 사라질 수 있다.
 */
export function buildSpeechChunks(title: string, bodyText: string): SpeechChunk[] {
  const chunks: SpeechChunk[] = [];

  const spokenTitle = toSpeechText(title);
  if (spokenTitle.length > 0) {
    for (const part of splitIntoSpeakableParts(spokenTitle, SPEECH_MAX_CHUNK_CHARS)) {
      chunks.push({ text: part, paragraphIndex: null });
    }
  }

  splitParagraphs(bodyText).forEach((paragraph, paragraphIndex) => {
    const spoken = toSpeechText(paragraph);
    if (spoken.length === 0) return;
    for (const part of splitIntoSpeakableParts(spoken, SPEECH_MAX_CHUNK_CHARS)) {
      chunks.push({ text: part, paragraphIndex });
    }
  });

  return chunks;
}
