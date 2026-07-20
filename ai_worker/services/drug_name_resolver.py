"""질의에서 약 이름을 찾아 검색 필터 값을 만드는 사전(LLM 호출 0회).

**사람은 성분명으로 묻지 않는다.** "아세트아미노펜 부작용"이라고 치는 사람은 없고
"타이레놀 부작용"이라고 친다. 그런데 `retrieve_service`는 성분명만 봤으므로 그런 질문이
전부 0건이었다 — e약은요 4,758건이 색인만 되고 한 번도 뽑히지 않던 이유다.

## 왜 LLM 리라이팅이 아닌가

질의 리라이팅용으로 작은 LLM을 앞단에 두는 안을 검토했고, 재보고 접었다(2026-07-17).

  1. **조사는 애초에 문제가 아니었다.** 한국어 조사는 명사 뒤에 붙으므로
     `"타이레놀" in "타이레놀은부작용이뭐야?"`가 그냥 참이다. LLM이 풀어줄 문제가 없다.
  2. **진짜 막힌 건 "부분 브랜드명"이고, 그건 질의가 아니라 색인 쪽 문제다.** 사용자는
     "훼스탈"이라 치는데 제품명은 `훼스탈골드정`이다. LLM이 완벽하게 `훼스탈`을 뽑아줘도
     여전히 `훼스탈` vs `훼스탈골드정`을 매칭해야 한다 — LLM은 이걸 못 푼다.
  3. 스트리밍 채팅 앞단에 LLM을 하나 더 붙이면 첫 토큰 지연이 늘고 질문마다 과금된다.
     이 코드베이스는 정확히 그 이유로 질환 분류 LLM을 걷어냈다(`disease_query_resolver` 참고).

실측(질문 7개 / 반례 10개): 아래 방식으로 7/7 적중, 오탐 0/10.
한계에 부딪히면 그때 LLM을 얹으면 된다 — 순서가 그렇다.

## 남아있는 것

"타이레놀 부작용?"은 e약은요를 뽑지만 "타이레놀 같이 먹어도 돼?"는 DUR 병용금기를 못
뽑는다. DUR 규칙은 성분(아세트아미노펜)으로 키가 걸려 있어서다. 제품 -> 성분 변환이
필요한데 그 표(`item_ingredient_map`)는 SQL 쪽에 있어 별도 작업이다.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

# 브랜드명 뒤에 붙는 제형·용량. 여기서부터 잘라내면 앞에 브랜드가 남는다.
# 실제 데이터 예: "타이레놀정500밀리그람(아세트아미노펜)" -> "타이레놀"
_FORM_OR_DOSE = re.compile(
    r"(정|캡슐|시럽|산|액|겔|크림|연고|주사|주|현탁액|점안액|로오숀|로션|패취|과립|환|고|"
    r"분말|에어로솔|스프레이|좌제|질정|외용액|\d|\(|_|-)"
)

# 검색 키의 최소 길이. 짧을수록 일반 낱말과 부딪혀 오탐이 는다. 3자에서 반례 10개 전부
# 0건이었다("머리가 아파요", "혈당 관리 운동" 등).
_MIN_KEY_LEN = 3


def brand_core(item_name: str) -> str:
    """제품명에서 브랜드 부분만 남긴다. `타이레놀정500밀리그람(...)` -> `타이레놀`

    제형 키워드가 이름 맨 앞에 있으면 그건 제형이 아니라 브랜드의 일부다 — `겔포스현탁액`의
    "겔"을 제형으로 보고 자르면 코어가 빈 문자열이 된다(실측 버그)."""
    match = _FORM_OR_DOSE.search(item_name)
    if match is None:
        return item_name.strip()
    if match.start() < _MIN_KEY_LEN:
        match = _FORM_OR_DOSE.search(item_name, _MIN_KEY_LEN)
        if match is None:
            return item_name.strip()
    return item_name[: match.start()].strip()


@dataclass(frozen=True)
class DrugNameIndex:
    """검색 키 -> 그 이름을 가진 제품들. **긴 키부터** 정렬돼 있다(더 구체적인 게 이긴다).

    질의마다 정렬하지 않으려고 만들 때 한 번만 정렬해둔다 — 키가 1만 개가 넘는다."""

    entries: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def resolve(self, query: str) -> tuple[str, list[str]] | None:
        """질의에 들어있는 약 이름을 찾는다. 없으면 None(호출자가 검색을 생략한다).

        공백을 지우고 부분 문자열로 본다 — 조사·어미가 뒤에 붙어도 브랜드는 그대로 남는다."""
        text = query.replace(" ", "")
        for key, products in self.entries:
            if key in text:
                return key, list(products)
        return None


def _build_prefix_index(names: Iterable[str], core_of: Callable[[str], str]) -> DrugNameIndex:
    """공통 접두사 인덱싱 메커니즘. `core_of`로 이름마다 "검색 키를 뽑을 기준 문자열"만
    바꿔치기한다 — 제품명은 브랜드 코어, 성분명은 원본 그대로(제형이 안 붙으므로)."""
    keys: dict[str, set[str]] = {}
    for name in names:
        core = core_of(name)
        for end in range(_MIN_KEY_LEN, len(core) + 1):
            keys.setdefault(core[:end], set()).add(name)

    entries = tuple(
        sorted(((k, tuple(sorted(v))) for k, v in keys.items()), key=lambda entry: len(entry[0]), reverse=True)
    )
    return DrugNameIndex(entries=entries)


def build_index(item_names: Iterable[str]) -> DrugNameIndex:
    """제품명 목록에서 검색 키를 만든다.

    브랜드 코어뿐 아니라 **그 접두사도 전부** 등록한다. 제품은 `훼스탈골드정`인데 사용자는
    "훼스탈"까지만 치기 때문이다. 접두사를 열면 오탐이 늘 것 같지만, 3자 이상으로 자르면
    일반 건강 질문 반례 10개에서 오탐이 하나도 안 났다(실측)."""
    return _build_prefix_index(item_names, core_of=brand_core)


def build_ingredient_index(ingr_names: Iterable[str]) -> DrugNameIndex:
    """성분명 목록에서 검색 키를 만든다. `build_index`와 같은 접두사 인덱싱을 쓰되
    `brand_core()`는 적용하지 않는다 — 성분명("졸피뎀타르타르산염")엔 제품명과 달리 제형·용량
    접미사가 안 붙으므로 그 전처리가 필요 없다(붙이면 화학명을 엉뚱하게 잘라낼 위험만 있다).

    이걸로 "졸피뎀 노인이 먹어도 돼?"가 저장된 "졸피뎀타르타르산염"에 걸린다 — 예전엔 질의
    전체 문자열이 성분명에 포함되는지만 봐서(양방향 완전 포함 검사) 이런 질문이 0건이었다."""
    return _build_prefix_index(ingr_names, core_of=lambda name: name.strip())
