"""처방전 사진(약품 여러 개) 인식 시 발생했던 두 회귀 시나리오에 대한 테스트.
(#99) 약품명 카드 아래 괄호로 표기된 성분/일반명 줄이 별도 약품 후보로 오매칭되는 문제,
용량 단위 표기가 없는 약품명 줄이 후보에서 조용히 탈락하는 문제를 다룬다."""

from app.models.medication_model import Medication
from app.repositories.medication_repository import MedicationRepository
from app.services import medication_service
from app.services.medication_service import OcrField
from app.tests.conftest import TestSessionLocal


async def test_parenthesized_ingredient_line_is_not_treated_as_a_drug_name():
    """복약안내문 카드에는 브랜드명 줄 아래에 "(클로피도그렐 75mg)"처럼 괄호로 감싼 성분/일반명
    줄이 따로 붙는다. 이 줄이 브랜드와 별개의 약품 후보로 잡혀 엉뚱한 성분약이 매칭/생성되면
    안 된다."""
    repo = MedicationRepository()
    async with TestSessionLocal() as session:
        brand = await repo.create_medication(
            session, Medication(standard_code="KD_PLAV001", medication_name="플라빅스정75mg", form_type="TABLET")
        )
        ingredient_only = await repo.create_medication(
            session, Medication(standard_code="KD_CLOP001", medication_name="클로피도그렐 75mg", form_type="TABLET")
        )

        matched, _auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session,
            repo,
            [
                OcrField(text="*플라빅스정75mg", confidence=0.9),
                OcrField(text="(클로피도그렐 75mg)", confidence=0.9),
            ],
        )

    matched_ids = {m.id for m in matched}
    assert brand.id in matched_ids
    assert ingredient_only.id not in matched_ids, "괄호 성분표기 줄이 별도 약품으로 잘못 매칭됨"


async def test_drug_name_without_dosage_unit_still_matches_by_form_suffix():
    """처방전 카드마다 약품명/용량이 서로 다른 OCR 필드로 쪼개져 mg 등 단위가 없어도,
    "디스커스"처럼 흔한 제형 접미사로 끝나면 후보에서 빠지지 않아야 한다."""
    repo = MedicationRepository()
    async with TestSessionLocal() as session:
        med = await repo.create_medication(
            session,
            Medication(standard_code="KD_SERE001", medication_name="세레타이드500디스커스", form_type="INHALER"),
        )

        matched, _auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, repo, [OcrField(text="세레타이드500디스커스", confidence=0.9)]
        )

    matched_ids = {m.id for m in matched}
    assert med.id in matched_ids


async def test_all_six_prescription_items_are_recognized():
    """실제 처방전(사진)처럼 약품명+용량이 붙은 줄과, 용량 단위가 ㎍/h처럼 mg/g/ml 패턴에
    걸리지 않는 줄이 섞여 있어도, 6개 약품이 모두 후보로 인식돼야 한다."""
    repo = MedicationRepository()
    names = [
        "아달라트오로스정60mg",
        "노스판패취10㎍/h",
        "히아루론점안액0.88ml",
        "포사맥스플러스디정",
        "세레타이드500디스커스",
        "플라빅스정75mg",
    ]
    async with TestSessionLocal() as session:
        created = [
            await repo.create_medication(
                session, Medication(standard_code=f"KD_RX{i:03d}", medication_name=name, form_type="TABLET")
            )
            for i, name in enumerate(names)
        ]

        ocr_fields = [OcrField(text=name, confidence=0.9) for name in names]
        matched, _auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, repo, ocr_fields
        )

    matched_ids = {m.id for m in matched}
    assert {m.id for m in created} <= matched_ids


def test_form_suffix_recognized_when_manufacturer_bracket_follows_on_same_line():
    """(#103) 실제 처방전에서는 브랜드명+용량이 제조사명 대괄호와 한 줄에 같이 인쇄된다
    (예: "노스판패취10ug/h [한국먼디파마]"). mg/g/ml 단위가 아닌 약(패취 등)은 제형 접미사
    조건에만 의존하는데, 뒤따르는 제조사명(한글)이 문자열 끝에 오는 바람에 예전에는 후보로
    인정되지 않았다(_looks_like_drug_name이 False). 접미사 뒤에 한글이 바로 이어지지만 않으면
    인정하도록 고쳤으므로 이제는 후보로 인정돼야 한다."""
    assert medication_service._looks_like_drug_name("노스판패취10ug/h [한국먼디파마]")
    assert medication_service._looks_like_drug_name("노스판패취10㎍/h [한국먼디파마]")


async def test_drug_with_manufacturer_bracket_and_non_mg_dosage_is_matched():
    """제형 접미사만으로 후보 인정된 약도, 실제 DB 매칭/자동 생성 흐름까지 이어지는지 확인한다."""
    repo = MedicationRepository()
    async with TestSessionLocal() as session:
        matched, auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, repo, [OcrField(text="노스판패취10ug/h [한국먼디파마]", confidence=0.9)]
        )

    assert len(matched) == 1
    assert matched[0].id in auto_created_ids


async def test_fuzzy_match_rescues_clova_character_misread():
    """(#106) 실제 처방전 사진으로 검증한 결과, CLOVA가 "패취"를 "매취"로 잘못 읽어서
    ("노스판매취10ug/h") 용량/접미사 패턴을 하나도 못 만족해 _looks_like_drug_name이 거르는
    사례가 확인됐다(브랜드명 줄과 제조사명 대괄호는 실제로는 서로 다른 OCR 필드로 나뉘어
    들어온다 — 서버 로그로 확인). 이런 한 글자 오인식은 마스터 DB 약품명과의 유사도 비교로
    구제돼야 한다."""
    repo = MedicationRepository()
    async with TestSessionLocal() as session:
        med = await repo.create_medication(
            session, Medication(standard_code="KD_NOSP002", medication_name="노스판패취10㎍/h", form_type="PATCH")
        )

        matched, _auto_created_ids, match_confidence = await medication_service._match_or_create_medications(
            session,
            repo,
            [
                OcrField(text="노스판매취10ug/h", confidence=0.9),
                OcrField(text="[한국먼디파마]", confidence=0.9),
            ],
        )

    matched_ids = {m.id for m in matched}
    assert med.id in matched_ids
    assert match_confidence[med.id] == 0.9


async def test_fuzzy_match_does_not_trigger_on_unrelated_prescription_text():
    """처방전 설명 문구("혈압을 낮추고 심장 근육으로...") 같은 무관한 텍스트가 마스터 DB의
    엉뚱한 약과 우연히 유사도가 높게 나와 오매칭되면 안 된다. (약이 하나뿐인 DB라 후보가
    없을 때의 참고용 fallback으로는 나올 수 있지만, 그 경우 confidence 맵에는 없어야
    한다 — 실제 유사도 매칭으로 인정된 게 아니라는 뜻)"""
    repo = MedicationRepository()
    async with TestSessionLocal() as session:
        med = await repo.create_medication(
            session, Medication(standard_code="KD_NOSP003", medication_name="노스판패취10㎍/h", form_type="PATCH")
        )

        matched, _auto_created_ids, match_confidence = await medication_service._match_or_create_medications(
            session,
            repo,
            [OcrField(text="혈압을 낮추고 심장 근육으로 산소를 많이 공급합니다", confidence=0.9)],
        )

    assert med.id not in match_confidence
