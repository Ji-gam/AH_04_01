"""(T-DOC-4) 음식 상호작용 원문 문단에서 알려진 음식/음료 명사를 찾아 문장 단위로 묶는 V1(규칙
기반) 추출 로직. 원래 `medication_service.py`에 있었으나, `app/scripts/build_food_drug_interaction_db.py`
(오프라인 빌드 스크립트)도 같은 로직으로 식약처 참조 테이블의 음식/알코올 상호작용 문단을 미리
음식별로 쪼개 DB에 저장해야 해서 무거운 의존성이 없는 이 모듈로 분리했다(`re`와
`app.dtos.medication_dto`만 사용 — `medication_service.py`를 그대로 import하면 FastAPI/SQLAlchemy
등 무거운 의존성이 딸려온다).

사전에 없는 음식/음료는 뽑히지 않는다 — 호출부가 결과가 비면 원문 전체 텍스트 노출로 폴백해야 한다.
추후 커버리지가 부족하면 이 모듈의 함수들만 LLM 기반 추출로 교체하면 된다(시그니처 유지)."""

import re

from app.dtos.medication_dto import FoodItem

KNOWN_FOOD_ITEMS = (
    "자몽주스",
    "자몽",
    "포멜로",
    "오렌지주스",
    "오렌지",
    "사과주스",
    "크랜베리 주스",
    "크랜베리",
    "우유",
    "유제품",
    "치즈",
    "요구르트",
    "사워크림",
    "아이스크림",
    "커피",
    "콜라",
    "녹차",
    "홍차",
    "차",
    "초콜릿",
    "카페인",
    "탄산음료",
    "청량음료",
    "알코올",
    "음주",
    "맥주 효모",
    "생맥주",
    "막걸리",
    "적포도주",
    "백포도주",
    "리큐어",
    "맥주",
    "와인",
    "술",
    "비타민 K",
    "비타민K",
    "비타민 E",
    "비타민E",
    "녹황색 채소",
    "브로콜리",
    "양배추",
    "케일",
    "콜라드그린",
    "시금치",
    "아스파라거스",
    "무청",
    "미니양배추",
    "소간",
    "콩류",
    "김",
    "매실",
    "바나나",
    "토마토",
    "저염소금",
    "등 푸른 생선",
    "조개",
    "멸치",
    "새우",
    "퓨린",
    "과당",
    "통조림 돼지고기",
    "아보카도",
    "건포도",
    "건자두",
    "건과일",
    "라즈베리",
    "사우어크라우트",
    "된장",
    "간장",
    "누에콩",
    "티라민",
    "세인트존스워트",
    "고지방",
    "고탄수화물",
    "식이섬유",
    "알로에",
    "화학조미료",
    "무기질 강화 음료",
    "칼슘강화 오렌지주스",
    "콩가루",
    "목화씨",
    "호두",
    "연어",
    "가다랑어",
    "참치",
)


def group_sentences_by_food_name(text: str) -> dict[str, list[str]]:
    """문장 단위로 쪼갠 뒤, `KNOWN_FOOD_ITEMS`에 있는 이름이 등장하는 문장들을 이름별로 묶는다.
    같은 문장에서 더 구체적인 이름(예: "자몽주스")이 매칭되면, 그 안에 포함된 짧은 이름(예: "자몽")은
    중복이므로 제외한다. 여러 텍스트(예: 음식/알코올 문단)에 걸쳐 같은 음식명이 나오는 경우를
    병합하고 싶은 호출부를 위해, 문장을 합친 문자열이 아니라 문장 리스트를 그대로 반환한다."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    sentences_by_name: dict[str, list[str]] = {}
    for sentence in sentences:
        matched = [name for name in KNOWN_FOOD_ITEMS if name in sentence]
        matched = [n for n in matched if not any(n != m and n in m for m in matched)]
        for name in matched:
            bucket = sentences_by_name.setdefault(name, [])
            if sentence not in bucket:
                bucket.append(sentence)
    return sentences_by_name


def extract_food_items(text: str) -> list[FoodItem]:
    """V1(규칙 기반): 텍스트에서 음식/음료 명사를 찾아 문장(들)을 detail로 묶은 `FoodItem` 목록을
    반환한다. 사전에 없는 음식/음료는 뽑히지 않는다 — 호출부가 결과가 비면 원문 전체 텍스트
    노출로 알아서 폴백한다."""
    return [
        FoodItem(name=name, detail=" ".join(sentences))
        for name, sentences in group_sentences_by_food_name(text).items()
    ]
