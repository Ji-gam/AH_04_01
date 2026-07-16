"""`app/database/drugs_full.db`(SQLite, `scripts/drug_info_sync/` 파이프라인이 공공데이터포털
API 22종을 전수 수집해 만든 산출물, 이 리포지토리가 만든 게 아니라 그대로 둔다)를 읽어 MySQL의
`app/models/dur.py` 테이블들에 시딩한다.

`app/scripts/seed_food_drug_interaction.py`와 동일 정책: 참조 데이터라 매 실행 시 대상 테이블을
전부 지우고 SQLite 원본 내용으로 재생성한다. 다만 최대 테이블(`dur_prod_usjnt_taboo`)이 80만
행대라 ORM 객체를 하나씩 `session.add`하지 않고, SQLite에서 청크(5,000행) 단위로 읽어 SQLAlchemy
Core `insert()`를 `executemany` 스타일로 반복 실행한다.

실행: uv run python -m app.scripts.seed_dur
"""

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.databases import AsyncSessionLocal
from app.models.dur import (
    DrugIdentification,
    DrugMaster,
    DrugPrdtPrmsnDetail,
    DurCpctyAtent,
    DurEfcyDplct,
    DurMdctnPdAtent,
    DurOdsnAtent,
    DurProdCpctyAtent,
    DurProdEfcyDplct,
    DurProdMdctnPdAtent,
    DurProdOdsnAtent,
    DurProdPwnmTaboo,
    DurProdSeobangPartition,
    DurProdSpcifyAgrdeTaboo,
    DurProdUsjntTaboo,
    DurPwnmTaboo,
    DurSpcifyAgrdeTaboo,
    DurUsjntTaboo,
    ItemIngredientMap,
    MedicineRecall,
)

SQLITE_PATH = Path(__file__).parent.parent / "database" / "drugs_full.db"

CHUNK_SIZE = 5000

# sqlite 테이블명 -> (모델, {sqlite 컬럼명: 모델 속성명}). 두 리포지토리가 실제로 쓰는
# 컬럼만 옮긴다(app/models/dur.py 모듈 docstring 참고).
_TABLE_SPECS: list[tuple[str, type, dict[str, str]]] = [
    (
        "drugs_data",
        DrugMaster,
        {
            "itemSeq": "item_seq",
            "itemName": "item_name",
            "entpName": "entp_name",
            "efcyQesitm": "efcy_qesitm",
            "useMethodQesitm": "use_method_qesitm",
            "atpnWarnQesitm": "atpn_warn_qesitm",
            "atpnQesitm": "atpn_qesitm",
            "intrcQesitm": "intrc_qesitm",
            "seQesitm": "se_qesitm",
            "depositMethodQesitm": "deposit_method_qesitm",
            "itemImage": "item_image",
        },
    ),
    (
        "drug_identification",
        DrugIdentification,
        {
            "ITEM_SEQ": "item_seq",
            "CHART": "chart",
            "DRUG_SHAPE": "drug_shape",
            "COLOR_CLASS1": "color_class1",
            "COLOR_CLASS2": "color_class2",
            "MARK_CODE_FRONT": "mark_code_front",
            "ETC_OTC_NAME": "etc_otc_name",
            "FORM_CODE_NAME": "form_code_name",
            "ITEM_IMAGE": "item_image",
        },
    ),
    (
        "drug_prdt_prmsn_detail",
        DrugPrdtPrmsnDetail,
        {
            "ITEM_SEQ": "item_seq",
            "ATC_CODE": "atc_code",
            "RARE_DRUG_YN": "rare_drug_yn",
            "NARCOTIC_KIND_CODE": "narcotic_kind_code",
        },
    ),
    (
        "medicine_recalls",
        MedicineRecall,
        {
            "ITEM_SEQ": "item_seq",
            "PRDUCT": "prduct",
            "ENTRPS": "entrps",
            "RTRVL_RESN": "rtrvl_resn",
            "RECALL_COMMAND_DATE": "recall_command_date",
            "ENFRC_YN": "enfrc_yn",
        },
    ),
    (
        "item_ingredient_map",
        ItemIngredientMap,
        {
            "ITEM_SEQ": "item_seq",
            "INGR_CODE": "ingr_code",
            "INGR_NAME": "ingr_name",
            "QNT": "qnt",
            "INGD_UNIT_CD": "ingd_unit_cd",
        },
    ),
]

_PRODUCT_RULE_COLS = {"ITEM_SEQ": "item_seq", "PROHBT_CONTENT": "prohbt_content", "REMARK": "remark"}
_INGR_CODE_COLS = {"INGR_CODE": "ingr_code", "INGR_NAME": "ingr_name"}

for _table, _model in [
    ("dur_prod_pwnm_taboo", DurProdPwnmTaboo),
    ("dur_prod_odsn_atent", DurProdOdsnAtent),
    ("dur_prod_spcify_agrde_taboo", DurProdSpcifyAgrdeTaboo),
    ("dur_prod_mdctn_pd_atent", DurProdMdctnPdAtent),
    ("dur_prod_cpcty_atent", DurProdCpctyAtent),
]:
    _TABLE_SPECS.append((_table, _model, {**_PRODUCT_RULE_COLS, **_INGR_CODE_COLS}))

_TABLE_SPECS.append(("dur_prod_seobang_partition", DurProdSeobangPartition, dict(_PRODUCT_RULE_COLS)))
_TABLE_SPECS.append(
    (
        "dur_prod_efcy_dplct",
        DurProdEfcyDplct,
        {**_PRODUCT_RULE_COLS, **_INGR_CODE_COLS, "ITEM_NAME": "item_name"},
    )
)

_TABLE_SPECS.append(
    (
        "dur_prod_usjnt_taboo",
        DurProdUsjntTaboo,
        {
            "ITEM_SEQ": "item_seq",
            "ITEM_NAME": "item_name",
            "MIXTURE_ITEM_SEQ": "mixture_item_seq",
            "MIXTURE_ITEM_NAME": "mixture_item_name",
            "INGR_CODE": "ingr_code",
            "INGR_KOR_NAME": "ingr_kor_name",
            "MIXTURE_INGR_CODE": "mixture_ingr_code",
            "MIXTURE_INGR_KOR_NAME": "mixture_ingr_kor_name",
            "PROHBT_CONTENT": "prohbt_content",
            "REMARK": "remark",
        },
    )
)

_INGREDIENT_RULE_COLS = {
    "INGR_CODE": "ingr_code",
    "INGR_NAME": "ingr_name",
    "PROHBT_CONTENT": "prohbt_content",
    "REMARK": "remark",
}
for _table, _model in [
    ("dur_pwnm_taboo", DurPwnmTaboo),
    ("dur_odsn_atent", DurOdsnAtent),
    ("dur_spcify_agrde_taboo", DurSpcifyAgrdeTaboo),
    ("dur_cpcty_atent", DurCpctyAtent),
    ("dur_efcy_dplct", DurEfcyDplct),
    ("dur_mdctn_pd_atent", DurMdctnPdAtent),
]:
    _TABLE_SPECS.append((_table, _model, dict(_INGREDIENT_RULE_COLS)))

_TABLE_SPECS.append(
    (
        "dur_usjnt_taboo",
        DurUsjntTaboo,
        {
            "INGR_CODE": "ingr_code",
            "INGR_KOR_NAME": "ingr_kor_name",
            "MIXTURE_INGR_CODE": "mixture_ingr_code",
            "MIXTURE_INGR_KOR_NAME": "mixture_ingr_kor_name",
            "PROHBT_CONTENT": "prohbt_content",
            "REMARK": "remark",
        },
    )
)


def _iter_sqlite_chunks(conn: sqlite3.Connection, table: str, columns: list[str], chunk_size: int):
    cursor = conn.cursor()
    quoted = ", ".join(f'"{c}"' for c in columns)
    cursor.execute(f'SELECT {quoted} FROM "{table}"')
    while True:
        rows = cursor.fetchmany(chunk_size)
        if not rows:
            break
        yield rows


async def seed_dur(
    sqlite_path: Path = SQLITE_PATH,
    session_factory: Callable[[], AsyncSession] | async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> dict[str, int]:
    """`session_factory`는 기본적으로 운영 MySQL 세션이지만, 테스트 스위트가 격리된 테스트 DB에
    같은 참조 데이터를 시딩할 때도 재사용한다(`app/tests/conftest.py`)."""
    conn = sqlite3.connect(sqlite_path)
    counts: dict[str, int] = {}
    try:
        async with session_factory() as session:
            # 참조 데이터라 증분 갱신할 이유가 없다 - 매번 전부 지우고 재적재(음식-약물과 동일 정책).
            for _table, model, _cols in reversed(_TABLE_SPECS):
                await session.execute(delete(model))
            await session.commit()

            for table, model, col_map in _TABLE_SPECS:
                sqlite_cols = list(col_map.keys())
                total = 0
                for rows in _iter_sqlite_chunks(conn, table, sqlite_cols, CHUNK_SIZE):
                    payload = [
                        {
                            col_map[col]: (value if value != "" else None)
                            for col, value in zip(sqlite_cols, row, strict=True)
                        }
                        for row in rows
                    ]
                    await session.execute(insert(model), payload)
                    total += len(payload)
                await session.commit()
                counts[table] = total
                print(f"{table}: {total:,}건 시딩 완료")
    finally:
        conn.close()

    return counts


async def _main() -> None:
    counts = await seed_dur()
    total = sum(counts.values())
    print(f"\nDUR 데이터 MySQL 시딩 완료: 총 {total:,}건 ({len(counts)}개 테이블)")


if __name__ == "__main__":
    asyncio.run(_main())
