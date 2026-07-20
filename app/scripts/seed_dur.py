"""MySQL(`ai_health`)의 DUR 원본 테이블(운영 데이터, 이미 시딩되어 있음)에서 읽어 `app/models/dur.py`
테이블들을 다른 MySQL 세션(주로 테스트 DB)에 다시 시딩한다.

(T-MED-15) 원래 `app/database/drugs_full.db`(SQLite, `scripts/drug_info_sync/` 파이프라인 산출물)를
읽었으나, SQLite를 더 이상 쓰지 않기로 하면서(원본 데이터는 이미 MySQL에 전량 적재됨) 소스를 MySQL로
바꿨다. 최대 테이블(`dur_prod_usjnt_taboo`)이 80만 행대라, 소스에서 청크(5,000행) 단위로 읽어
SQLAlchemy Core `insert()`를 `executemany` 스타일로 반복 실행한다.

`source_session_factory`(기본: 운영 MySQL `AsyncSessionLocal`, 즉 `ai_health`)와 `session_factory`
(대상, 테스트 DB 등)가 같은 DB를 가리키면 삭제 후 재삽입 과정에서 원본 데이터가 사라지므로 이를 막는다.

실행: 이제 단독 실행 대상이 없다(운영 데이터가 이미 ai_health에 있음) — 테스트 DB 시딩은
`app/tests/conftest.py`가 `session_factory=TestSessionLocal`로 자동 호출한다.
"""

import asyncio
import sys
from collections.abc import AsyncIterator, Callable

from sqlalchemy import delete, insert, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.databases import AsyncSessionLocal
from app.models.dur import (
    ALL_DUR_MODELS,
    DrugIdentification,
    DrugMaster,
    DrugPrdtPrmsnDetail,
    DurCpctyAtent,
    DurEfcyDplct,
    DurMdctnPdAtent,
    DurOdsnAtent,
    DurProdCpctyAtent,
    DurProdEfcyDplct,
    DurProdMasterList,
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

CHUNK_SIZE = 5000


class SameDatabaseError(RuntimeError):
    """소스와 대상이 같은 DB를 가리키면(운영 데이터를 지우고 빈 데이터로 재생성하는 사고를
    막기 위해) 시딩을 거부한다."""


# 소스 MySQL 테이블명 -> (모델, {소스 컬럼명: 모델 속성명}). 두 리포지토리가 실제로 쓰는
# 컬럼만 옮긴다(app/models/dur.py 모듈 docstring 참고). MySQL 컬럼명은 이미 모델 속성명과
# 동일한 snake_case라(과거 SQLite 원본은 API 원본 camelCase/UPPER_SNAKE였다) 매핑이 대부분 항등이다.
_TABLE_SPECS: list[tuple[str, type, dict[str, str]]] = [
    (
        "drugs_data",
        DrugMaster,
        {
            "item_seq": "item_seq",
            "item_name": "item_name",
            "entp_name": "entp_name",
            "efcy_qesitm": "efcy_qesitm",
            "use_method_qesitm": "use_method_qesitm",
            "atpn_warn_qesitm": "atpn_warn_qesitm",
            "atpn_qesitm": "atpn_qesitm",
            "intrc_qesitm": "intrc_qesitm",
            "se_qesitm": "se_qesitm",
            "deposit_method_qesitm": "deposit_method_qesitm",
            "item_image": "item_image",
        },
    ),
    (
        "dur_prod_master_list",
        DurProdMasterList,
        {"item_seq": "item_seq", "item_name": "item_name", "entp_name": "entp_name"},
    ),
    (
        "drug_identification",
        DrugIdentification,
        {
            "item_seq": "item_seq",
            "chart": "chart",
            "drug_shape": "drug_shape",
            "color_class1": "color_class1",
            "color_class2": "color_class2",
            "mark_code_front": "mark_code_front",
            "etc_otc_name": "etc_otc_name",
            "form_code_name": "form_code_name",
            "item_image": "item_image",
        },
    ),
    (
        "drug_prdt_prmsn_detail",
        DrugPrdtPrmsnDetail,
        {
            "item_seq": "item_seq",
            "atc_code": "atc_code",
            "rare_drug_yn": "rare_drug_yn",
            "narcotic_kind_code": "narcotic_kind_code",
        },
    ),
    (
        "medicine_recalls",
        MedicineRecall,
        {
            "item_seq": "item_seq",
            "prduct": "prduct",
            "entrps": "entrps",
            "rtrvl_resn": "rtrvl_resn",
            "recall_command_date": "recall_command_date",
            "enfrc_yn": "enfrc_yn",
        },
    ),
    (
        "item_ingredient_map",
        ItemIngredientMap,
        {
            "item_seq": "item_seq",
            "ingr_code": "ingr_code",
            "ingr_name": "ingr_name",
            "qnt": "qnt",
            "ingd_unit_cd": "ingd_unit_cd",
        },
    ),
]

_PRODUCT_RULE_COLS = {"item_seq": "item_seq", "prohbt_content": "prohbt_content", "remark": "remark"}
_INGR_CODE_COLS = {"ingr_code": "ingr_code", "ingr_name": "ingr_name"}

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
        {**_PRODUCT_RULE_COLS, **_INGR_CODE_COLS, "item_name": "item_name"},
    )
)

_TABLE_SPECS.append(
    (
        "dur_prod_usjnt_taboo",
        DurProdUsjntTaboo,
        {
            "item_seq": "item_seq",
            "item_name": "item_name",
            "mixture_item_seq": "mixture_item_seq",
            "mixture_item_name": "mixture_item_name",
            "ingr_code": "ingr_code",
            "ingr_kor_name": "ingr_kor_name",
            "mixture_ingr_code": "mixture_ingr_code",
            "mixture_ingr_kor_name": "mixture_ingr_kor_name",
            "prohbt_content": "prohbt_content",
            "remark": "remark",
        },
    )
)

_INGREDIENT_RULE_COLS = {
    "ingr_code": "ingr_code",
    "ingr_name": "ingr_name",
    "prohbt_content": "prohbt_content",
    "remark": "remark",
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
            "ingr_code": "ingr_code",
            "ingr_kor_name": "ingr_kor_name",
            "mixture_ingr_code": "mixture_ingr_code",
            "mixture_ingr_kor_name": "mixture_ingr_kor_name",
            "prohbt_content": "prohbt_content",
            "remark": "remark",
        },
    )
)

assert {model for _table, model, _cols in _TABLE_SPECS} == set(ALL_DUR_MODELS)


async def _assert_different_database(source_session: AsyncSession, target_session: AsyncSession) -> None:
    source_db = (await source_session.execute(text("SELECT DATABASE()"))).scalar_one()
    target_db = (await target_session.execute(text("SELECT DATABASE()"))).scalar_one()
    if source_db == target_db:
        raise SameDatabaseError(
            f"소스와 대상이 같은 DB({source_db})입니다 — 운영 데이터를 지우고 재생성하는 사고를 "
            "막기 위해 시딩을 중단합니다. 다른 DB(테스트 DB 등)를 대상으로만 실행하세요."
        )


async def _iter_mysql_chunks(
    source_session: AsyncSession, table: str, columns: list[str], chunk_size: int
) -> AsyncIterator[list]:
    quoted = ", ".join(columns)
    result = await source_session.execute(text(f"SELECT {quoted} FROM {table}"))
    rows = result.fetchmany(chunk_size)
    while rows:
        yield rows
        rows = result.fetchmany(chunk_size)


async def seed_dur(
    session_factory: Callable[[], AsyncSession] | async_sessionmaker[AsyncSession],
    source_session_factory: Callable[[], AsyncSession] | async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> dict[str, int]:
    """`session_factory`(대상, 필수 — 테스트 DB 등)에 `source_session_factory`(기본: 운영
    MySQL `ai_health`)의 DUR 참조 데이터를 복사한다(`app/tests/conftest.py`가 호출)."""
    counts: dict[str, int] = {}
    async with source_session_factory() as source_session, session_factory() as session:
        await _assert_different_database(source_session, session)

        # 참조 데이터라 증분 갱신할 이유가 없다 - 매번 전부 지우고 재적재(음식-약물과 동일 정책).
        for _table, model, _cols in reversed(_TABLE_SPECS):
            await session.execute(delete(model))
        await session.commit()

        for table, model, col_map in _TABLE_SPECS:
            source_cols = list(col_map.keys())
            total = 0
            async for rows in _iter_mysql_chunks(source_session, table, source_cols, CHUNK_SIZE):
                payload = [
                    {col_map[col]: value for col, value in zip(source_cols, row, strict=True)} for row in rows
                ]
                await session.execute(insert(model), payload)
                total += len(payload)
            await session.commit()
            counts[table] = total
            print(f"{table}: {total:,}건 시딩 완료")

    return counts


async def _main() -> None:
    print(
        "이 스크립트는 더 이상 단독 실행 대상이 없습니다 — 원본 데이터가 이미 운영 MySQL(ai_health)에 "
        "있습니다. 테스트 DB 시딩은 app/tests/conftest.py가 session_factory=TestSessionLocal로 "
        "자동 호출합니다.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    asyncio.run(_main())
