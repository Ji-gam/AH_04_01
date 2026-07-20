"""MySQL -> CSV 내보내기 회귀 테스트.

DB 연결 없이 두 가지만 검증한다.
  1) 각 파일의 컬럼 집합이 `_tuning.yaml`이 전제하는 원래 API 표기와 어긋나지 않는지 —
     하나라도 틀리면 `exclude_columns`/`metadata_columns`가 조용히 안 먹혀 검색이 깨진다
     (`ai_worker/source/_tuning.yaml` 참고).
  2) `_write_csv`가 실제로 `CsvLoader`가 읽을 수 있는 형식을 만드는지 — 포맷만 맞고
     내용이 안 읽히면 아무 의미가 없다.
"""

from ai_worker.ingest.loaders import CsvLoader
from ai_worker.ingest.sources import Source
from ai_worker.scripts.export_source_from_mysql import EXPORTS, _write_csv

# 원래 CSV(`git show HEAD~1:ai_worker/source/*.csv`로 확인 가능)의 헤더. drugs_data.csv는
# openDe/updateDe/itemImage/bizrno가 있었지만 `_tuning.yaml`의 exclude_columns라 본문에
# 안 실렸고 metadata_columns도 아니라서(itemSeq만 씀) 안 옮겨도 무해하다 — 그래서 뺐다.
_EXPECTED_COLUMNS = {
    "drugs_data.csv": {
        "entpName",
        "itemName",
        "itemSeq",
        "efcyQesitm",
        "useMethodQesitm",
        "atpnWarnQesitm",
        "atpnQesitm",
        "intrcQesitm",
        "seQesitm",
        "depositMethodQesitm",
    },
    "dur_pwnm_taboo.csv": {
        "DUR_SEQ",
        "TYPE_NAME",
        "MIX_TYPE",
        "INGR_CODE",
        "INGR_ENG_NAME",
        "INGR_NAME",
        "MIX_INGR",
        "ORI_INGR",
        "CLASS_NAME",
        "FORM_NAME",
        "GRADE",
        "NOTIFICATION_DATE",
        "PROHBT_CONTENT",
        "REMARK",
        "DEL_YN",
    },
    "dur_odsn_atent.csv": {
        "DUR_SEQ",
        "TYPE_NAME",
        "MIX_TYPE",
        "INGR_CODE",
        "INGR_ENG_NAME",
        "INGR_NAME",
        "MIX_INGR",
        "ORI_INGR",
        "FORM_NAME",
        "NOTIFICATION_DATE",
        "PROHBT_CONTENT",
        "REMARK",
        "DEL_YN",
    },
    "dur_mdctn_pd_atent.csv": {
        "DUR_SEQ",
        "TYPE_NAME",
        "MIX_TYPE",
        "INGR_CODE",
        "INGR_ENG_NAME",
        "INGR_NAME",
        "MIX_INGR",
        "ORI_INGR",
        "CLASS_NAME",
        "FORM_NAME",
        "MAX_DOSAGE_TERM",
        "NOTIFICATION_DATE",
        "PROHBT_CONTENT",
        "REMARK",
        "DEL_YN",
    },
    "dur_efcy_dplct.csv": {
        "DUR_SEQ",
        "TYPE_NAME",
        "MIX_TYPE",
        "INGR_CODE",
        "INGR_ENG_NAME",
        "INGR_NAME",
        "MIX_INGR",
        "ORI_INGR",
        "CLASS_NAME",
        "EFFECT_CODE",
        "NOTIFICATION_DATE",
        "PROHBT_CONTENT",
        "REMARK",
        "DEL_YN",
        "SERS_NAME",
    },
    "dur_cpcty_atent.csv": {
        "DUR_SEQ",
        "TYPE_NAME",
        "MIX_TYPE",
        "INGR_CODE",
        "INGR_ENG_NAME",
        "INGR_NAME",
        "MIX_INGR",
        "ORI_INGR",
        "CLASS_NAME",
        "FORM_NAME",
        "MAX_QTY",
        "NOTIFICATION_DATE",
        "PROHBT_CONTENT",
        "REMARK",
        "DEL_YN",
    },
    "dur_spcify_agrde_taboo.csv": {
        "DUR_SEQ",
        "TYPE_NAME",
        "MIX_TYPE",
        "INGR_CODE",
        "INGR_ENG_NAME",
        "INGR_NAME",
        "MIX_INGR",
        "ORI_INGR",
        "CLASS_NAME",
        "FORM_NAME",
        "NOTIFICATION_DATE",
        "PROHBT_CONTENT",
        "REMARK",
        "DEL_YN",
        "AGE_BASE",
    },
    "_item_ingredient_map.csv": {"ITEM_NAME", "INGR_NAME"},
    "dur_usjnt_taboo.csv": {
        "TYPE_NAME",
        "MIX_TYPE",
        "INGR_CODE",
        "INGR_ENG_NAME",
        "INGR_KOR_NAME",
        "MIX",
        "ORI",
        "CLASS",
        "MIXTURE_MIX_TYPE",
        "MIXTURE_INGR_CODE",
        "MIXTURE_INGR_ENG_NAME",
        "MIXTURE_INGR_KOR_NAME",
        "MIXTURE_MIX",
        "MIXTURE_ORI",
        "MIXTURE_CLASS",
        "NOTIFICATION_DATE",
        "PROHBT_CONTENT",
        "REMARK",
        "DEL_YN",
    },
}


def test_every_export_is_covered_by_the_expected_column_table():
    """새 파일을 EXPORTS에 추가하고 _EXPECTED_COLUMNS 갱신을 깜빡하면 여기서 걸린다."""
    assert {e.filename for e in EXPORTS} == set(_EXPECTED_COLUMNS)


def test_export_columns_match_original_csv_header():
    """`_tuning.yaml`의 exclude_columns/metadata_columns는 원래 API 표기(TYPE_NAME 등)를
    전제한다. 컬럼 하나라도 틀리면 그 설정이 조용히 안 먹혀 검색이 깨진다."""
    by_name = {e.filename: e for e in EXPORTS}
    for filename, expected in _EXPECTED_COLUMNS.items():
        got = set(by_name[filename].columns.keys())
        assert got == expected, f"{filename}: expected={expected - got} unexpected={got - expected}"


def test_query_aliases_every_mysql_column_to_its_original_name():
    """쿼리가 `MySQL컬럼 AS 원래이름`으로 별칭을 달아, DictWriter가 헤더 그대로 쓸 수 있어야 한다."""
    export = next(e for e in EXPORTS if e.filename == "dur_spcify_agrde_taboo.csv")

    assert "age_base AS AGE_BASE" in export.query
    assert "ingr_name AS INGR_NAME" in export.query
    assert export.query.startswith("SELECT ")
    assert export.query.endswith("FROM dur_spcify_agrde_taboo")


def test_item_ingredient_map_query_joins_drugs_data_for_item_name():
    """item_ingredient_map엔 item_name이 없다(item_seq만 있음, app/models/dur.py) — drugs_data와
    조인해야 한다. dur_prod_master_list가 아니라 drugs_data와 조인하는 이유: retrieve_service의
    db_holder["drug_names"]가 drugs_data.csv 기준으로 색인되므로, 같은 테이블로 조인해야
    ITEM_NAME 문자열이 정확히 일치한다(실측 2026-07-20)."""
    export = next(e for e in EXPORTS if e.filename == "_item_ingredient_map.csv")

    assert "d.item_name AS ITEM_NAME" in export.query
    assert "m.ingr_name AS INGR_NAME" in export.query
    assert "item_ingredient_map m JOIN drugs_data d ON m.item_seq = d.item_seq" in export.query


def test_written_csv_is_readable_by_the_real_csv_loader(tmp_path):
    """포맷이 맞다고 끝이 아니다 — 실제 소비자(CsvLoader)가 읽어서 올바른 메타데이터가
    붙는 Document를 만드는지까지 확인한다."""
    export = next(e for e in EXPORTS if e.filename == "dur_spcify_agrde_taboo.csv")
    rows = [
        {
            "DUR_SEQ": "455",
            "TYPE_NAME": "특정연령대금기",
            "MIX_TYPE": "단일",
            "INGR_CODE": "D000149",
            "INGR_ENG_NAME": "Acarbose",
            "INGR_NAME": "아카보즈",
            "MIX_INGR": "",
            "ORI_INGR": "[M085039]아카보즈",
            "CLASS_NAME": "[03960]당뇨병용제",
            "FORM_NAME": "정제",
            "NOTIFICATION_DATE": "20140109",
            "PROHBT_CONTENT": "안전성 및 유효성 미확립",
            "REMARK": "",
            "DEL_YN": "정상",
            "AGE_BASE": "18세 이하",
        }
    ]
    csv_path = tmp_path / export.filename
    _write_csv(csv_path, list(export.columns.keys()), rows)

    source = Source(path=csv_path, metadata_columns={"INGR_NAME": "ingr_name"})
    doc = next(CsvLoader(source).lazy_load())

    assert doc.metadata["ingr_name"] == "아카보즈"
    assert "AGE_BASE: 18세 이하" in doc.page_content
