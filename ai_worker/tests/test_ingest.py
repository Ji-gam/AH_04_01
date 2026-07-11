"""
T-LLM-2-rag-source-label: `_load_docs_from_csv`가 Chroma 메타데이터 `source`에
원본 CSV 파일명 대신 사람이 읽기 좋은 한글 라벨을 넣는지 검증한다.
"""

import pytest

from ai_worker.tasks.ingest import _display_source_label, _load_docs_from_csv


@pytest.mark.parametrize(
    "file_name,expected_label",
    [
        ("dur_pwnm_taboo.csv", "식약처 DUR 임부금기 정보"),
        ("dur_odsn_atent.csv", "식약처 DUR 노인주의 정보"),
        ("dur_mdctn_pd_atent.csv", "식약처 DUR 투여기간주의 정보"),
        ("dur_efcy_dplct.csv", "식약처 DUR 효능군중복 정보"),
    ],
)
def test_display_source_label_maps_known_files_to_korean_label(file_name, expected_label):
    assert _display_source_label(file_name) == expected_label


def test_display_source_label_falls_back_to_raw_file_name_for_unknown_files():
    assert _display_source_label("unknown_future_file.csv") == "unknown_future_file.csv"


def test_load_docs_from_csv_uses_display_label_in_metadata_source(tmp_path):
    csv_file = tmp_path / "dur_pwnm_taboo.csv"
    csv_file.write_text(
        "DUR_SEQ,TYPE_NAME,INGR_NAME,INGR_ENG_NAME,PROHBT_CONTENT,GRADE,CLASS_NAME\n"
        "1,임부금기,테스트성분,test_ingr,임부에 대한 안전성 미확립,1등급,테스트분류\n",
        encoding="utf-8",
    )

    docs = _load_docs_from_csv(csv_file)

    assert len(docs) == 1
    assert docs[0].metadata["source"] == "식약처 DUR 임부금기 정보"
