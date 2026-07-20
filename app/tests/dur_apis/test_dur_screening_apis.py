import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio

ACTIFED = "액티피드정"  # 197000053, 품목 기준 규칙 0건이지만 item_ingredient_map으로 성분 해결됨
IBUPROFEN_200 = "부루펜정200밀리그램(이부프로펜)"  # 197700120
IBUPROFEN_400 = "부루펜정400밀리그램(이부프로펜)"  # 198300343, IBUPROFEN_200과 EFCY(D000363) 공유
RECALLED_DRUG = "자모다정(독시라민숙신산염)"  # 202500644, medicine_recalls 보유
NONEXISTENT = "존재하지않는약품123"

DUR_SIMPLE_RULE_CODES = ["PWNM", "ODSN", "SPCIFY_AGRDE", "MDCTN", "SEOBANG", "CPCTY"]


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_basic_screening_returns_dur_simple_for_known_drug():
    async with await _client() as client:
        response = await client.post(
            "/api/v1/dur/screening/basic",
            json={"drug_names": [IBUPROFEN_200, NONEXISTENT]},
        )
    assert response.status_code == 200
    data = response.json()

    assert data["unmatched_drug_names"] == [NONEXISTENT]
    assert len(data["results"]) == 1
    result = data["results"][0]
    assert result["drug_detail"]["item_name"] == IBUPROFEN_200
    assert result["drug_detail"]["atc_code"] == "M01AE01"  # T-MED-14-1: drug_prdt_prmsn_detail 기반

    dur_simple = result["dur_simple"]
    # dur_simple은 present 여부와 무관하게 항상 6개 고정 순서로 내려간다.
    assert [f["rule_code"] for f in dur_simple] == DUR_SIMPLE_RULE_CODES

    pwnm = next(f for f in dur_simple if f["rule_code"] == "PWNM")
    assert pwnm["present"] is True
    assert pwnm["prohbt_content"]


async def test_basic_screening_all_flags_off_for_clean_drug():
    async with await _client() as client:
        response = await client.post("/api/v1/dur/screening/basic", json={"drug_names": [ACTIFED]})
    assert response.status_code == 200
    data = response.json()

    dur_simple = data["results"][0]["dur_simple"]
    assert len(dur_simple) == 6
    assert all(f["present"] is False for f in dur_simple)
    assert all(f["prohbt_content"] is None for f in dur_simple)
    assert data["unmatched_drug_names"] == []


async def test_basic_screening_rejects_empty_drug_names():
    async with await _client() as client:
        response = await client.post("/api/v1/dur/screening/basic", json={"drug_names": []})
    assert response.status_code == 400


async def test_basic_screening_all_unmatched_returns_200_with_empty_results():
    async with await _client() as client:
        response = await client.post("/api/v1/dur/screening/basic", json={"drug_names": [NONEXISTENT]})
    assert response.status_code == 200
    data = response.json()

    assert data["results"] == []
    assert data["unmatched_drug_names"] == [NONEXISTENT]


async def test_interaction_screening_detects_efficacy_duplication():
    async with await _client() as client:
        response = await client.post(
            "/api/v1/dur/screening/interaction",
            json={"drug_names": [IBUPROFEN_200, IBUPROFEN_400]},
        )
    assert response.status_code == 200
    data = response.json()

    interactions = data["drug_intrc"]["interactions"]
    assert any(
        i["rule_type"] == "효능군중복주의"
        and {i["drug_a"]["item_name"], i["drug_b"]["item_name"]} == {IBUPROFEN_200, IBUPROFEN_400}
        for i in interactions
    )
    hit = next(i for i in interactions if i["rule_type"] == "효능군중복주의")
    assert {hit["drug_a"]["item_seq"], hit["drug_b"]["item_seq"]} == {"197700120", "198300343"}


async def test_interaction_screening_deduplicates_bidirectional_pairs():
    async with await _client() as client:
        response = await client.post(
            "/api/v1/dur/screening/interaction",
            json={"drug_names": [IBUPROFEN_200, IBUPROFEN_400]},
        )
    data = response.json()

    pairs = [frozenset({i["drug_a"]["item_seq"], i["drug_b"]["item_seq"]}) for i in data["drug_intrc"]["interactions"]]
    assert len(pairs) == len(set(pairs))


async def test_interaction_screening_includes_recall_for_single_drug():
    async with await _client() as client:
        response = await client.post(
            "/api/v1/dur/screening/interaction",
            json={"drug_names": [RECALLED_DRUG]},
        )
    assert response.status_code == 200
    data = response.json()

    assert data["drug_intrc"]["interactions"] == []
    recalls = data["drug_intrc"]["recalls"]
    assert any(r["item_name"] == RECALLED_DRUG and r["item_seq"] == "202500644" for r in recalls)


async def test_ingredient_screening_returns_ingredient_detail():
    async with await _client() as client:
        response = await client.post(
            "/api/v1/dur/screening/ingredient",
            json={"drug_names": [IBUPROFEN_200]},
        )
    assert response.status_code == 200
    data = response.json()

    ingr_codes = {i["ingr_code"] for i in data["ingredients"]}
    assert "D000363" in ingr_codes


async def test_ingredient_screening_resolves_ingredients_for_zero_rule_drug():
    """T-MED-14-1: 품목 기준 규칙이 0건인 약도 item_ingredient_map을 통해 3단계 성분 조회가 된다."""
    async with await _client() as client:
        response = await client.post(
            "/api/v1/dur/screening/ingredient",
            json={"drug_names": [ACTIFED]},
        )
    assert response.status_code == 200
    data = response.json()

    ingr_codes = {i["ingr_code"] for i in data["ingredients"]}
    assert {"D000316", "D001098"}.issubset(ingr_codes)


async def test_ingredient_screening_includes_source_drug_dosage():
    """T-MED-14-1 후속: source_drugs가 item_seq/함량(qnt/unit)까지 포함하는지 확인."""
    async with await _client() as client:
        response = await client.post(
            "/api/v1/dur/screening/ingredient",
            json={"drug_names": [ACTIFED]},
        )
    assert response.status_code == 200
    data = response.json()

    pseudoephedrine = next(i for i in data["ingredients"] if i["ingr_code"] == "D000316")
    source = next(d for d in pseudoephedrine["source_drugs"] if d["item_seq"] == "197000053")
    assert source["item_name"] == ACTIFED
    assert source["qnt"] == "60"
    assert source["unit"] == "mg"


async def test_ingredient_screening_includes_rule_detail_for_grade_and_max_qty():
    """T-MED-14 후속: 임부금기/용량주의 규칙엔 rule_detail(등급/최대 1일 용량)이 채워지고,
    해당 컬럼이 없는 규칙(노인주의)은 null이어야 한다."""
    async with await _client() as client:
        response = await client.post(
            "/api/v1/dur/screening/ingredient",
            json={"drug_names": [IBUPROFEN_200]},
        )
    assert response.status_code == 200
    data = response.json()

    ibuprofen = next(i for i in data["ingredients"] if i["ingr_code"] == "D000363")
    rule_detail_by_type: dict[str, list] = {}
    for rule in ibuprofen["rules"]:
        rule_detail_by_type.setdefault(rule["rule_type"], []).append(rule["rule_detail"])

    assert any(d is not None for d in rule_detail_by_type["임부금기"])
    assert any(d is not None for d in rule_detail_by_type["용량주의"])
    assert all(d is None for d in rule_detail_by_type["노인주의"])


async def test_ingredient_screening_all_unmatched_returns_200_with_empty_ingredients():
    async with await _client() as client:
        response = await client.post(
            "/api/v1/dur/screening/ingredient",
            json={"drug_names": [NONEXISTENT]},
        )
    assert response.status_code == 200
    data = response.json()

    assert data["ingredients"] == []
    assert data["unmatched_drug_names"] == [NONEXISTENT]


async def test_p95_latency_under_3_seconds():
    payload = {"drug_names": [IBUPROFEN_200, IBUPROFEN_400, ACTIFED]}
    latencies = []

    async with await _client() as client:
        for _ in range(20):
            start = time.perf_counter()
            response = await client.post("/api/v1/dur/screening/interaction", json=payload)
            latencies.append(time.perf_counter() - start)
            assert response.status_code == 200

    latencies.sort()
    p95 = latencies[18]
    assert p95 <= 3.0, f"P95 latency is {p95}s, which is > 3.0s"
