"""`build_product_ingredient_map`(제품명->성분명 브릿지 사전 빌더) 단위 테스트.

`build_index`/`build_ingredient_index`(접두사 인덱스)는 `test_retrieve_service.py`에서
`retrieve_service.search_documents()`를 통해 간접 검증되지만, 이 함수는 완전 일치 사전이라
별도로 둔다."""

from ai_worker.services.drug_name_resolver import build_product_ingredient_map


def test_build_product_ingredient_map_groups_multiple_ingredients_per_product():
    """복합제는 한 제품에 성분이 여럿이다(예: 타이레놀콜드-에스정 -> 4성분)."""
    rows = [
        {"ITEM_NAME": "타이레놀콜드-에스정", "INGR_NAME": "아세트아미노펜"},
        {"ITEM_NAME": "타이레놀콜드-에스정", "INGR_NAME": "슈도에페드린염산염"},
        {"ITEM_NAME": "타이레놀정500밀리그람(아세트아미노펜)", "INGR_NAME": "아세트아미노펜"},
    ]

    mapping = build_product_ingredient_map(rows)

    assert mapping["타이레놀콜드-에스정"] == ("슈도에페드린염산염", "아세트아미노펜")
    assert mapping["타이레놀정500밀리그람(아세트아미노펜)"] == ("아세트아미노펜",)


def test_build_product_ingredient_map_skips_rows_with_empty_fields():
    """MySQL JOIN 결과에 이름이 비는 행이 섞여도(매칭 실패 등) 조용히 건너뛴다 — 브릿지가
    없으면 그냥 필터가 하나(item_name)만 걸릴 뿐, 검색 자체가 죽으면 안 되므로."""
    rows = [
        {"ITEM_NAME": "", "INGR_NAME": "아세트아미노펜"},
        {"ITEM_NAME": "무명약", "INGR_NAME": ""},
        {"ITEM_NAME": "  ", "INGR_NAME": "  "},
        {"ITEM_NAME": "정상약", "INGR_NAME": "정상성분"},
    ]

    mapping = build_product_ingredient_map(rows)

    assert mapping == {"정상약": ("정상성분",)}


def test_build_product_ingredient_map_strips_whitespace():
    rows = [{"ITEM_NAME": " 타이레놀정500밀리그람(아세트아미노펜) ", "INGR_NAME": " 아세트아미노펜 "}]

    mapping = build_product_ingredient_map(rows)

    assert mapping == {"타이레놀정500밀리그람(아세트아미노펜)": ("아세트아미노펜",)}


def test_build_product_ingredient_map_empty_input_returns_empty_dict():
    assert build_product_ingredient_map([]) == {}
