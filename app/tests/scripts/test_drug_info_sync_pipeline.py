import os
import sqlite3
import sys

SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "drug_info_sync")
SCRIPT_DIR = os.path.abspath(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from config_db import API_SPECS, APISpec  # type: ignore[import-not-found]  # noqa: E402
from mapping_recalls import clean_product_name, find_matching_item_seq  # type: ignore[import-not-found]  # noqa: E402
from pipeline_db import APIPipeline  # type: ignore[import-not-found]  # noqa: E402
from run_db import get_api_key  # type: ignore[import-not-found]  # noqa: E402


def make_spec(**overrides) -> APISpec:
    defaults = dict(
        name="sample_api",
        base_url="https://apis.data.go.kr/sample",
        output_filename="sample",
        db_table="sample_table",
        primary_keys=["ITEM_SEQ"],
        index_columns=["ITEM_SEQ"],
    )
    defaults.update(overrides)
    return APISpec(**defaults)


def make_pipeline(tmp_path, **spec_overrides) -> APIPipeline:
    spec = make_spec(**spec_overrides)
    return APIPipeline(spec, api_key="dummy-key", output_dir=str(tmp_path))


class TestParseXml:
    def test_extracts_items_and_total_count(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        xml = """<response><body><totalCount>2</totalCount>
        <items>
            <item><ITEM_SEQ>111</ITEM_SEQ><ITEM_NAME>테스트약A</ITEM_NAME></item>
            <item><ITEM_SEQ>222</ITEM_SEQ><ITEM_NAME>테스트약B</ITEM_NAME></item>
        </items></body></response>"""

        items, total_count = pipeline._parse_xml(xml)

        assert total_count == 2
        assert items == [
            {"ITEM_SEQ": "111", "ITEM_NAME": "테스트약A"},
            {"ITEM_SEQ": "222", "ITEM_NAME": "테스트약B"},
        ]

    def test_returns_empty_on_malformed_xml(self, tmp_path):
        pipeline = make_pipeline(tmp_path)

        items, total_count = pipeline._parse_xml("<not><closed>")

        assert items == []
        assert total_count == 0

    def test_total_count_defaults_to_zero_when_element_missing_or_empty(self, tmp_path):
        pipeline = make_pipeline(tmp_path)

        items, total_count = pipeline._parse_xml("<response><body><items></items></body></response>")
        assert items == []
        assert total_count == 0

        items, total_count = pipeline._parse_xml("<response><totalCount></totalCount></response>")
        assert total_count == 0


class TestCheckpoint:
    def test_save_and_load_roundtrip(self, tmp_path):
        pipeline = make_pipeline(tmp_path)

        pipeline._save_checkpoint(7)

        assert pipeline._load_checkpoint() == 7

    def test_load_returns_start_page_when_no_checkpoint_exists(self, tmp_path):
        pipeline = make_pipeline(tmp_path, start_page=3)

        assert pipeline._load_checkpoint() == 3

    def test_delete_checkpoint_removes_file(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        pipeline._save_checkpoint(5)

        pipeline._delete_checkpoint()

        assert pipeline._load_checkpoint() == pipeline.spec.start_page

    def test_checkpoints_for_different_extra_labels_are_independent(self, tmp_path):
        pipeline = make_pipeline(tmp_path)

        pipeline._save_checkpoint(4, extra_label="202501")
        pipeline._save_checkpoint(9, extra_label="202502")

        assert pipeline._load_checkpoint(extra_label="202501") == 4
        assert pipeline._load_checkpoint(extra_label="202502") == 9


class TestFlushToDb:
    def test_creates_table_with_unique_constraint_and_index(self, tmp_path):
        pipeline = make_pipeline(tmp_path, primary_keys=["ITEM_SEQ"], index_columns=["ITEM_SEQ"])
        conn = sqlite3.connect(":memory:")

        pipeline._flush_to_db(conn, [{"ITEM_SEQ": "1", "ITEM_NAME": "약A"}])

        cursor = conn.cursor()
        cursor.execute("SELECT ITEM_SEQ, ITEM_NAME FROM sample_table")
        assert cursor.fetchall() == [("1", "약A")]

        cursor.execute("PRAGMA index_list(sample_table)")
        assert any(row[2] for row in cursor.fetchall())  # UNIQUE 제약조건이 생성되었는지 확인

    def test_upserts_existing_rows_by_primary_key_instead_of_duplicating(self, tmp_path):
        pipeline = make_pipeline(tmp_path, primary_keys=["ITEM_SEQ"])
        conn = sqlite3.connect(":memory:")

        pipeline._flush_to_db(conn, [{"ITEM_SEQ": "1", "ITEM_NAME": "약A"}])
        pipeline._flush_to_db(conn, [{"ITEM_SEQ": "1", "ITEM_NAME": "약A(개정됨)"}])

        cursor = conn.cursor()
        cursor.execute("SELECT ITEM_SEQ, ITEM_NAME FROM sample_table")
        rows = cursor.fetchall()
        assert rows == [("1", "약A(개정됨)")]

    def test_ignores_empty_record_list(self, tmp_path):
        pipeline = make_pipeline(tmp_path)
        conn = sqlite3.connect(":memory:")

        pipeline._flush_to_db(conn, [])

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        assert cursor.fetchall() == []


class TestCleanProductName:
    def test_strips_parenthesized_ingredient_and_spaces_and_lowercases(self):
        assert clean_product_name("타이레놀정500밀리그람(아세트아미노펜)") == "타이레놀정500밀리그람"

    def test_removes_all_whitespace(self):
        assert clean_product_name("액티피드 정") == "액티피드정"

    def test_returns_empty_string_for_falsy_input(self):
        assert clean_product_name("") == ""
        assert clean_product_name(None) == ""


class TestFindMatchingItemSeq:
    def test_exact_match_takes_priority(self):
        drug_dict = {"부루펜정": "SEQ1", "부루펜정400": "SEQ2"}

        assert find_matching_item_seq("부루펜정", drug_dict) == "SEQ1"

    def test_falls_back_to_substring_match_when_no_exact_match(self):
        drug_dict = {"부루펜정400밀리그람": "SEQ2"}

        assert find_matching_item_seq("부루펜정400", drug_dict) == "SEQ2"

    def test_no_substring_match_for_short_strings_under_four_chars(self):
        drug_dict = {"가나다라마바사": "SEQ1"}

        assert find_matching_item_seq("가나", drug_dict) is None

    def test_returns_none_when_nothing_matches(self):
        drug_dict = {"부루펜정": "SEQ1"}

        assert find_matching_item_seq("타이레놀정", drug_dict) is None


class TestGetApiKey:
    def test_raises_when_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("DATA_GO_KR_API_KEY", raising=False)

        try:
            get_api_key()
            raise AssertionError("환경변수가 없으면 예외가 발생해야 한다")
        except RuntimeError:
            pass

    def test_returns_env_var_value_when_set(self, monkeypatch):
        monkeypatch.setenv("DATA_GO_KR_API_KEY", "test-key-1234")

        assert get_api_key() == "test-key-1234"


class TestApiSpecsConfig:
    def test_every_spec_has_a_public_data_portal_url_and_primary_keys(self):
        assert len(API_SPECS) > 0
        for api_name, spec in API_SPECS.items():
            assert spec.base_url.startswith("http")
            assert spec.name == api_name
            assert len(spec.primary_keys) > 0
