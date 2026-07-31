"""T-LLM-6: 기사 본문 → 카드뉴스 요약(LLM).

프롬프트와 스키마는 이 도메인이 직접 소유한다 - `AIWorkerGateway`는 "스키마를 만족하는 JSON을
받아온다"는 범용 능력만 제공하고 도메인 지식을 갖지 않는다(T-LLM-2-async-gateway의 경계).

수집(3단계)과 분리해 둔 이유: 카드요약은 LLM에 의존하고 느리며 실패할 수 있다. 수집과 한 몸으로
묶으면 OpenAI가 흔들릴 때 기사 저장까지 같이 실패한다. 그래서 기사를 먼저 다 저장하고,
요약은 `card_summary`가 빈 기사만 따로 채운다(다음 실행이 빠진 것만 다시 시도).
"""

import logging
from typing import cast

from app.dtos.health_news_dto import ICON_KEYS, SLIDES_MAX, SLIDES_MIN, CardSummary
from app.models.health_news import HealthNews
from app.services.ai_worker_gateway import AIWorkerGateway

logger = logging.getLogger(__name__)

# 기사 본문이 아무리 길어도 이만큼만 LLM에 보낸다. 코메디 기사는 보통 1,000~2,600자라
# 잘릴 일이 거의 없지만, 유별나게 긴 기사 하나가 토큰을 다 먹는 것을 막는 상한이다.
MAX_BODY_CHARS = 6000

_SYSTEM_PROMPT = f"""당신은 ReMedi의 건강 카드뉴스 편집자입니다.
건강 기사 한 편을 받아, 스마트폰에서 좌우로 넘겨 보는 카드 {SLIDES_MIN}~{SLIDES_MAX}장으로 요약하세요.

읽는 사람은 만성질환을 관리하는 일반인입니다. 의학 지식이 없다고 가정하고 쉬운 말로 쓰세요.

카드 한 장의 구성:
- tag: 그 카드가 무슨 이야기인지 나타내는 짧은 라벨 (예: 수면, 근력운동, 가이드라인)
- stat: 가장 큰 글씨로 보여줄 핵심 숫자나 값 (예: +1시간, 80%+, LDL -12%)
- substat: stat을 한 조각 보충하는 짧은 말 (예: 당화혈색소 -0.5%). 마땅한 게 없으면 비워두세요.
- text: 그 숫자가 무슨 뜻인지 설명하는 글. **2~3문장으로 충분히 쓰세요(70~95자).**
- icon_key: 아래 목록에서 카드 내용에 가장 어울리는 아이콘 하나

규칙:
1. 각 항목의 글자 수 제한을 반드시 지키세요. 넘으면 화면에서 잘려 보입니다.
2. **text는 카드마다 3~5줄(70~95자)을 채우세요.** 한 문장으로 끝내지 마세요 - 카드 아래쪽이
   텅 비어 보이고, 사용자는 기사 원문을 끝까지 읽지 않기 때문에 카드가 내용을 담아야 합니다.
   채우는 방법은 지어내는 것이 아니라, 기사에 이미 있는 내용을 덧붙이는 것입니다:
   (1) 그 숫자가 무슨 뜻인지 (2) 어떤 연구/조사에서 나온 것인지 (3) 그래서 무엇을 알 수 있는지.
   기사에 없는 사실을 보태서 길이를 늘리면 절대 안 됩니다.
   중요한 이야기일수록 앞 카드에 두세요 - 뒤로 갈수록 덜 읽힙니다.
3. stat은 되도록 모든 카드에 채우세요 - 가장 큰 글씨 자리라서 비면 카드가 허전해집니다.
   순서대로 시도하세요:
   (1) 기사에 숫자가 있으면 그 숫자를 그대로 씁니다. 기사에 없는 숫자를 계산하거나
       추정하거나 지어내면 절대 안 됩니다.
   (2) 숫자가 없으면 기사에 나온 핵심 표현을 짧게 씁니다 (예: "8년 만에", "예방 가능",
       "근거 부족", "1위").
   (3) (1)(2) 모두 정말 불가능한 카드만 비워두세요.
4. 숫자의 방향(늘었는지 줄었는지)을 기사와 반대로 쓰지 마세요. +/- 부호를 붙일 때는
   기사에서 그 값이 증가한 것인지 감소한 것인지 다시 확인하세요. 방향이 헷갈리면 부호를
   빼고 값만 쓰세요 (예: "63kg").
5. 카드마다 다른 이야기를 담으세요. 같은 내용을 다르게 말한 카드를 두지 마세요.
6. 진단하거나 치료를 권하는 말투를 쓰지 마세요. 기사가 전한 연구 결과를 그대로 옮기세요.
7. icon_key는 반드시 아래 목록의 값 그대로 쓰세요. 목록에 없는 이름은 쓸 수 없습니다.

사용 가능한 icon_key 목록:
{", ".join(ICON_KEYS)}
"""


def build_user_input(news: HealthNews) -> str:
    """LLM에 보낼 기사 본문. 제목을 같이 주면 기사의 초점을 잡는 데 도움이 된다."""
    body = news.body_text[:MAX_BODY_CHARS]
    return f"제목: {news.title}\n\n본문:\n{body}"


async def generate_card_summary(news: HealthNews, gateway: AIWorkerGateway | None = None) -> CardSummary:
    """기사 한 건의 카드요약을 생성한다. 실패하면 예외가 그대로 올라간다 - 호출하는 배치가
    기사 단위로 잡아서 나머지 기사를 계속 처리한다."""
    client = gateway or AIWorkerGateway()
    result = await client.call_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_input=build_user_input(news),
        schema=CardSummary,
    )
    # call_structured의 선언 반환형은 BaseModel이지만, 내부에서 schema.model_validate()로
    # 검증해 돌려주므로 실제로는 우리가 넘긴 CardSummary다.
    return cast(CardSummary, result)
