import pytest

from app.database.database import dur_db_connection
from app.repositories.dur_repository import DurScreeningRepository

ACTIFED = "액티피드정"  # 197000053, 규칙 0건이지만 item_ingredient_map(MATERIAL_NAME 매칭)으로 해결됨
IBUPROFEN_200 = "부루펜정200밀리그램(이부프로펜)"  # 197700120, CPCTY/ODSN/PWNM/EFCY 보유
IBUPROFEN_400 = "부루펜정400밀리그램(이부프로펜)"  # 198300343, EFCY(D000363) 공유
NONEXISTENT = "존재하지않는의약품이름12345"
# 195900034: 규칙도 0건이고 item_ingredient_map에도 없는 구조적으로 해결 불가능한 케이스
# (dur_prod_master_list에 성분 정보 자체가 없어 22개 테이블 어디서도 INGR_CODE를 못 찾음)
UNRESOLVABLE_ITEM_SEQ = "195900034"


class _CountingConnection:
    """sqlite3.Connection은 C 확장 타입이라 monkeypatch 불가 - execute 호출만
    카운트하고 나머지는 실제 connection에 위임하는 얇은 프록시로 대체한다."""

    def __init__(self, real_conn):
        self._real_conn = real_conn
        self.execute_count = 0

    def execute(self, *args, **kwargs):
        self.execute_count += 1
        return self._real_conn.execute(*args, **kwargs)


@pytest.fixture
def repo():
    with dur_db_connection() as conn:
        yield DurScreeningRepository(conn), conn


@pytest.fixture
def counting_repo():
    with dur_db_connection() as conn:
        counting_conn = _CountingConnection(conn)
        yield DurScreeningRepository(counting_conn), counting_conn


def test_resolve_item_seqs_matches_exact_name(repo):
    repository, _ = repo
    matched, unmatched = repository.resolve_item_seqs([IBUPROFEN_200])

    assert unmatched == []
    assert len(matched) == 1
    assert matched[0]["item_seq"] == "197700120"
    assert matched[0]["item_name"] == IBUPROFEN_200


def test_resolve_item_seqs_reports_unmatched_names(repo):
    repository, _ = repo
    matched, unmatched = repository.resolve_item_seqs([IBUPROFEN_200, NONEXISTENT])

    assert unmatched == [NONEXISTENT]
    assert len(matched) == 1


def test_resolve_item_seqs_uses_at_most_two_queries(counting_repo):
    repository, conn = counting_repo

    repository.resolve_item_seqs([IBUPROFEN_200, IBUPROFEN_400, ACTIFED, NONEXISTENT])

    assert conn.execute_count <= 2


def test_get_single_drug_rules_returns_hits_for_known_drug(repo):
    repository, _ = repo
    rules = repository.get_single_drug_rules(["197700120"])

    rule_types = {r["rule_type"] for r in rules}
    assert "임부금기" in rule_types


def test_get_single_drug_rules_empty_for_no_rule_drug(repo):
    repository, _ = repo
    rules = repository.get_single_drug_rules(["197000053"])

    assert rules == []


def test_get_single_drug_rules_uses_one_query(counting_repo):
    repository, conn = counting_repo

    repository.get_single_drug_rules(["197700120", "198300343", "197000053"])

    assert conn.execute_count == 1


def test_get_efficacy_groups_finds_shared_ingredient(repo):
    repository, _ = repo
    groups = repository.get_efficacy_groups(["197700120", "198300343"])

    ingr_codes = {g["ingr_code"] for g in groups}
    item_seqs = {g["item_seq"] for g in groups}
    assert "D000363" in ingr_codes
    assert {"197700120", "198300343"}.issubset(item_seqs)


def test_get_interactions_within_set_restricts_to_input_pairs(repo):
    repository, _ = repo
    # 실제 USJNT 페어(코니트라캡슐 197700120과 무관한 쌍)가 입력 집합 밖이면 안 끌려온다.
    interactions = repository.get_interactions_within_set(["200000913", "197700120"])

    for row in interactions:
        assert row["item_seq"] in {"200000913", "197700120"}
        assert row["mixture_item_seq"] in {"200000913", "197700120"}


def test_get_interactions_within_set_finds_known_pair(repo):
    repository, _ = repo
    interactions = repository.get_interactions_within_set(["200000913", "200200173"])

    assert len(interactions) >= 1
    assert interactions[0]["prohbt_content"] == "횡문근융해증"


def test_get_interactions_within_set_uses_one_query(counting_repo):
    repository, conn = counting_repo

    repository.get_interactions_within_set(["200000913", "200200173", "197700120"])

    assert conn.execute_count == 1


def test_get_recalls_returns_known_recall(repo):
    repository, _ = repo
    recalls = repository.get_recalls(["202500644"])

    assert len(recalls) == 1
    assert recalls[0]["item_name"] == "자모다정(독시라민숙신산염)"


def test_get_ingredient_codes_for_items_derives_from_rule_hits(repo):
    repository, _ = repo
    codes = repository.get_ingredient_codes_for_items(["197700120"])

    assert "197700120" in codes
    assert ("D000363", "이부프로펜") in codes["197700120"] or any(code == "D000363" for code, _ in codes["197700120"])


def test_get_ingredient_codes_for_items_resolves_via_material_name_for_no_rule_drug(repo):
    repository, _ = repo
    codes = repository.get_ingredient_codes_for_items(["197000053"])

    ingr_codes = {code for code, _ in codes["197000053"]}
    assert {"D000316", "D001098"}.issubset(ingr_codes)


def test_get_ingredient_codes_for_items_empty_when_truly_unresolvable(repo):
    repository, _ = repo
    codes = repository.get_ingredient_codes_for_items([UNRESOLVABLE_ITEM_SEQ])

    assert codes.get(UNRESOLVABLE_ITEM_SEQ, set()) == set()


def test_get_ingredient_codes_for_items_uses_at_most_two_queries(counting_repo):
    repository, conn = counting_repo

    repository.get_ingredient_codes_for_items(["197700120", "197000053", UNRESOLVABLE_ITEM_SEQ])

    assert conn.execute_count <= 2


def test_get_ingredient_level_rules_uses_one_query(counting_repo):
    repository, conn = counting_repo

    repository.get_ingredient_level_rules(["D000363"])

    assert conn.execute_count == 1


def test_get_drug_identification_uses_one_query(counting_repo):
    repository, conn = counting_repo

    repository.get_drug_identification(["197700120"])

    assert conn.execute_count == 1


def test_get_drug_identification_returns_empty_for_unknown_item(repo):
    repository, _ = repo
    rows = repository.get_drug_identification(["존재하지않는itemseq"])

    assert rows == []
