"""MySQL(`app/models/dur.py`) -> `ai_worker/source/`의 DUR/e약은요 CSV 재생성.

CSV는 더 이상 원본이 아니라 **빌드 산출물**이다. 원본은 MySQL이다(`app/scripts/seed_dur.py`가
`drugs_full.db`에서 이미 옮겨놨다). 이 스크립트는 매 빌드 시점에 최신 MySQL 데이터로
`ai_worker/source/`의 CSV 8개(RAG 문서 재료) + 조회용 사전 CSV 1개(`_item_ingredient_map.csv`,
RAG 문서 아님)를 다시 써서, 기존 `python -m ai_worker.ingest`가 그대로 읽게 한다 —
인제스천 엔진(`ai_worker/ingest/*`)과 `_tuning.yaml`은 이 변경으로 한 줄도 안 바뀐다.

컬럼명을 원래 식약처 API 표기(`TYPE_NAME` 등)로 되돌려 쓰는 이유: `_tuning.yaml`의
`exclude_columns`/`metadata_columns`가 전부 그 표기를 전제로 만들어져 있다. 여기서만
MySQL 컬럼명(snake_case) -> 원래 표기로 변환해두면 나머지는 손 안 대도 된다.

실행: uv run python -m ai_worker.scripts.export_source_from_mysql
"""

import asyncio
import csv
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ai_worker.core.config import settings
from ai_worker.ingest.sources import SOURCE_DIR

# {원래 API 컬럼명(=CSV 헤더): MySQL 컬럼명}. `app/scripts/seed_dur.py`의 매핑을 뒤집은
# 값이다(그쪽 원본을 그대로 import하지 않는다 — ai_worker는 app/에 의존하지 않는다는
# 경계를 유지하고, `_TABLE_SPECS`는 그쪽의 비공개(`_` 접두) 내부 구현이다).
_INGREDIENT_RULE_COLS = {"INGR_CODE": "ingr_code", "INGR_NAME": "ingr_name"}
_INGREDIENT_RULE_TAIL = {"PROHBT_CONTENT": "prohbt_content", "REMARK": "remark", "DEL_YN": "del_yn"}
_INGREDIENT_RULE_HEAD = {
    "DUR_SEQ": "dur_seq",
    "TYPE_NAME": "type_name",
    "MIX_TYPE": "mix_type",
    **_INGREDIENT_RULE_COLS,
    "INGR_ENG_NAME": "ingr_eng_name",
    "MIX_INGR": "mix_ingr",
    "ORI_INGR": "ori_ingr",
}


class _Export:
    """CSV 파일 하나(=MySQL 테이블 하나)에 대한 {원래 컬럼명: MySQL 컬럼명}과 쿼리."""

    def __init__(self, filename: str, table: str, columns: dict[str, str]) -> None:
        self.filename = filename
        self.table = table
        self.columns = columns

    @property
    def query(self) -> str:
        select = ", ".join(f"{mysql_col} AS {orig}" for orig, mysql_col in self.columns.items())
        return f"SELECT {select} FROM {self.table}"


EXPORTS: list[_Export] = [
    _Export(
        "drugs_data.csv",
        "drugs_data",
        {
            "entpName": "entp_name",
            "itemName": "item_name",
            "itemSeq": "item_seq",
            "efcyQesitm": "efcy_qesitm",
            "useMethodQesitm": "use_method_qesitm",
            "atpnWarnQesitm": "atpn_warn_qesitm",
            "atpnQesitm": "atpn_qesitm",
            "intrcQesitm": "intrc_qesitm",
            "seQesitm": "se_qesitm",
            "depositMethodQesitm": "deposit_method_qesitm",
        },
    ),
    _Export(
        "dur_pwnm_taboo.csv",
        "dur_pwnm_taboo",
        {
            **_INGREDIENT_RULE_HEAD,
            "CLASS_NAME": "class_name",
            "FORM_NAME": "form_name",
            "GRADE": "grade",
            "NOTIFICATION_DATE": "notification_date",
            **_INGREDIENT_RULE_TAIL,
        },
    ),
    _Export(
        "dur_odsn_atent.csv",
        "dur_odsn_atent",
        {
            **_INGREDIENT_RULE_HEAD,
            "FORM_NAME": "form_name",
            "NOTIFICATION_DATE": "notification_date",
            **_INGREDIENT_RULE_TAIL,
        },
    ),
    _Export(
        "dur_spcify_agrde_taboo.csv",
        "dur_spcify_agrde_taboo",
        {
            **_INGREDIENT_RULE_HEAD,
            "CLASS_NAME": "class_name",
            "FORM_NAME": "form_name",
            "NOTIFICATION_DATE": "notification_date",
            **_INGREDIENT_RULE_TAIL,
            "AGE_BASE": "age_base",
        },
    ),
    _Export(
        "dur_mdctn_pd_atent.csv",
        "dur_mdctn_pd_atent",
        {
            **_INGREDIENT_RULE_HEAD,
            "CLASS_NAME": "class_name",
            "FORM_NAME": "form_name",
            "MAX_DOSAGE_TERM": "max_dosage_term",
            "NOTIFICATION_DATE": "notification_date",
            **_INGREDIENT_RULE_TAIL,
        },
    ),
    _Export(
        "dur_cpcty_atent.csv",
        "dur_cpcty_atent",
        {
            **_INGREDIENT_RULE_HEAD,
            "CLASS_NAME": "class_name",
            "FORM_NAME": "form_name",
            "MAX_QTY": "max_qty",
            "NOTIFICATION_DATE": "notification_date",
            **_INGREDIENT_RULE_TAIL,
        },
    ),
    _Export(
        "dur_efcy_dplct.csv",
        "dur_efcy_dplct",
        {
            **_INGREDIENT_RULE_HEAD,
            "CLASS_NAME": "class_name",
            "EFFECT_CODE": "effect_code",
            "NOTIFICATION_DATE": "notification_date",
            **_INGREDIENT_RULE_TAIL,
            "SERS_NAME": "sers_name",
        },
    ),
    _Export(
        # 밑줄 접두어 = `ai_worker/ingest/sources.py`의 `_is_source_file`이 RAG 색인 대상에서
        # 제외한다(`_tuning.yaml`과 같은 규칙). 이 파일은 RAG 문서가 아니라 제품명->성분명
        # 조회용 사전 데이터라(`retrieve_service._load_product_ingredient_map` 참고),
        # source/ 드롭 폴더의 "여기엔 RAG 재료만 넣는다" 원칙을 어기지 않으면서도 같은
        # export 스크립트/디렉터리를 공유하려고 이 접두어를 쓴다.
        "_item_ingredient_map.csv",
        # T-LLM-2-rag-brand-name-bridge(2026-07-27): drugs_data(e약은요 부분집합, ~4,758건)
        # 대신 drug_prdt_prmsn_list(전체 허가목록, 43,017건)와 조인한다. 이전엔 "이 CSV의
        # ITEM_NAME이 retrieve_service.db_holder["drug_names"](drugs_data 기준)의 표기와
        # 어긋나면 안 된다"는 이유로 drugs_data를 고집했는데, 실측 버그("인데놀"이 e약은요엔
        # 없어 검색이 통째로 생략됨)로 그 좁은 범위 자체가 문제였다. 이제
        # `retrieve_service.cache_searchable_names`가 이 브릿지의 ITEM_NAME 전체를
        # `drug_names` 인덱스에도 병합하므로(호출부의 `extra_item_names` 참고), 여기서
        # 표기를 좁게 맞출 필요가 없다 — 오히려 인덱스 쪽이 이 넓은 사전을 따라간다.
        #
        # 주의: item_ingredient_map.ingr_name은 종종 염(鹽) 형태("프로프라놀롤염산염")인데
        # Chroma에 적재된 DUR 문서는 염을 뗀 원형("프로프라놀롤")으로 저장돼 있다. 이 표기
        # 차이는 여기서 정리하지 않는다 — `retrieve_service._build_filters`가 쿼리 시점에
        # `db_holder["ingr_names"].resolve()`로 정규화한다(이미 사용자 질의에도 쓰는 것과
        # 같은 접두사 매칭). 여기서 미리 다듬으면 오히려 그 정규화 로직과 중복/불일치 위험이 있다.
        "item_ingredient_map m JOIN drug_prdt_prmsn_list d ON m.item_seq = d.item_seq",
        {"ITEM_NAME": "d.item_name", "INGR_NAME": "m.ingr_name"},
    ),
    _Export(
        "dur_usjnt_taboo.csv",
        "dur_usjnt_taboo",
        {
            "TYPE_NAME": "type_name",
            "MIX_TYPE": "mix_type",
            "INGR_CODE": "ingr_code",
            "INGR_ENG_NAME": "ingr_eng_name",
            "INGR_KOR_NAME": "ingr_kor_name",
            "MIX": "mix",
            "ORI": "ori",
            "CLASS": "class",
            "MIXTURE_MIX_TYPE": "mixture_mix_type",
            "MIXTURE_INGR_CODE": "mixture_ingr_code",
            "MIXTURE_INGR_ENG_NAME": "mixture_ingr_eng_name",
            "MIXTURE_INGR_KOR_NAME": "mixture_ingr_kor_name",
            "MIXTURE_MIX": "mixture_mix",
            "MIXTURE_ORI": "mixture_ori",
            "MIXTURE_CLASS": "mixture_class",
            "NOTIFICATION_DATE": "notification_date",
            "PROHBT_CONTENT": "prohbt_content",
            "REMARK": "remark",
            "DEL_YN": "del_yn",
        },
    ),
]


def _mysql_url() -> str:
    return f"mysql+asyncmy://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"


def _write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


async def export_all(dest_dir: Path = SOURCE_DIR) -> dict[str, int]:
    """MySQL 8개 테이블을 각각 CSV로 내려쓴다. 파일마다 통째로 덮어쓴다(참조 데이터라
    증분 개념이 없다 — `seed_dur.py`와 같은 정책)."""
    engine = create_async_engine(_mysql_url())
    counts: dict[str, int] = {}
    try:
        async with engine.connect() as conn:
            for export in EXPORTS:
                result = await conn.execute(text(export.query))
                rows = [dict(row) for row in result.mappings().all()]
                _write_csv(dest_dir / export.filename, list(export.columns.keys()), rows)
                counts[export.filename] = len(rows)
    finally:
        await engine.dispose()
    return counts


async def _main() -> None:
    counts = await export_all()
    for filename, count in counts.items():
        print(f"{filename}: {count:,}건 내보내기 완료")
    print(f"\nMySQL -> CSV 내보내기 완료: 총 {sum(counts.values()):,}건 ({len(counts)}개 파일)")


if __name__ == "__main__":
    asyncio.run(_main())
