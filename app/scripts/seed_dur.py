"""`app/database/drugs_full.db`(SQLite, `scripts/drug_info_sync/` 파이프라인이 공공데이터포털
API 24종을 전수 수집해 만든 산출물, 이 리포지토리가 만든 게 아니라 그대로 둔다)를 읽어 MySQL의
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
    DrugBundleInfo,
    DrugIdentification,
    DrugMaster,
    DrugMaxDosage,
    DrugPrdtMcpnDetail,
    DrugPrdtPrmsnDetail,
    DrugPrdtPrmsnList,
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

SQLITE_PATH = Path(__file__).parent.parent / "database" / "drugs_full.db"

CHUNK_SIZE = 5000

# sqlite 테이블명 -> (모델, {sqlite 컬럼명: 모델 속성명}). SQLite 원본(drugs_full.db) 컬럼을
# 전부 옮긴다(app/models/dur.py 모듈 docstring 참고) - 병용확인 API가 안 쓰는 컬럼이라도 CSV/API
# 원본에 있으면 유지한다.
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
            "openDe": "open_de",
            "updateDe": "update_de",
            "bizrno": "bizrno",
        },
    ),
    (
        "dur_prod_master_list",
        DurProdMasterList,
        {
            "ITEM_SEQ": "item_seq",
            "ITEM_NAME": "item_name",
            "ENTP_NAME": "entp_name",
            "ITEM_PERMIT_DATE": "item_permit_date",
            "ETC_OTC_CODE": "etc_otc_code",
            "CLASS_NO": "class_no",
            "CHART": "chart",
            "BAR_CODE": "bar_code",
            "MATERIAL_NAME": "material_name",
            "EE_DOC_ID": "ee_doc_id",
            "UD_DOC_ID": "ud_doc_id",
            "NB_DOC_ID": "nb_doc_id",
            "INSERT_FILE": "insert_file",
            "STORAGE_METHOD": "storage_method",
            "VALID_TERM": "valid_term",
            "REEXAM_TARGET": "reexam_target",
            "REEXAM_DATE": "reexam_date",
            "PACK_UNIT": "pack_unit",
            "EDI_CODE": "edi_code",
            "CANCEL_DATE": "cancel_date",
            "CANCEL_NAME": "cancel_name",
            "TYPE_CODE": "type_code",
            "TYPE_NAME": "type_name",
            "CHANGE_DATE": "change_date",
            "BIZRNO": "bizrno",
        },
    ),
    (
        "drug_identification",
        DrugIdentification,
        {
            "ITEM_SEQ": "item_seq",
            "ITEM_NAME": "item_name",
            "ENTP_SEQ": "entp_seq",
            "ENTP_NAME": "entp_name",
            "CHART": "chart",
            "ITEM_IMAGE": "item_image",
            "PRINT_FRONT": "print_front",
            "PRINT_BACK": "print_back",
            "DRUG_SHAPE": "drug_shape",
            "COLOR_CLASS1": "color_class1",
            "COLOR_CLASS2": "color_class2",
            "LINE_FRONT": "line_front",
            "LINE_BACK": "line_back",
            "LENG_LONG": "leng_long",
            "LENG_SHORT": "leng_short",
            "THICK": "thick",
            "IMG_REGIST_TS": "img_regist_ts",
            "CLASS_NO": "class_no",
            "CLASS_NAME": "class_name",
            "ETC_OTC_NAME": "etc_otc_name",
            "ITEM_PERMIT_DATE": "item_permit_date",
            "FORM_CODE_NAME": "form_code_name",
            "MARK_CODE_FRONT_ANAL": "mark_code_front_anal",
            "MARK_CODE_BACK_ANAL": "mark_code_back_anal",
            "MARK_CODE_FRONT_IMG": "mark_code_front_img",
            "MARK_CODE_BACK_IMG": "mark_code_back_img",
            "ITEM_ENG_NAME": "item_eng_name",
            "CHANGE_DATE": "change_date",
            "MARK_CODE_FRONT": "mark_code_front",
            "MARK_CODE_BACK": "mark_code_back",
            "EDI_CODE": "edi_code",
            "BIZRNO": "bizrno",
            "STD_CD": "std_cd",
        },
    ),
    (
        "drug_prdt_prmsn_detail",
        DrugPrdtPrmsnDetail,
        {
            "ITEM_SEQ": "item_seq",
            "ITEM_NAME": "item_name",
            "ENTP_NAME": "entp_name",
            "ITEM_PERMIT_DATE": "item_permit_date",
            "CNSGN_MANUF": "cnsgn_manuf",
            "ETC_OTC_CODE": "etc_otc_code",
            "CHART": "chart",
            "BAR_CODE": "bar_code",
            "MATERIAL_NAME": "material_name",
            "EE_DOC_ID": "ee_doc_id",
            "UD_DOC_ID": "ud_doc_id",
            "NB_DOC_ID": "nb_doc_id",
            "INSERT_FILE": "insert_file",
            "STORAGE_METHOD": "storage_method",
            "VALID_TERM": "valid_term",
            "REEXAM_TARGET": "reexam_target",
            "REEXAM_DATE": "reexam_date",
            "PACK_UNIT": "pack_unit",
            "EDI_CODE": "edi_code",
            "PERMIT_KIND_NAME": "permit_kind_name",
            "ENTP_NO": "entp_no",
            "MAKE_MATERIAL_FLAG": "make_material_flag",
            "NEWDRUG_CLASS_NAME": "newdrug_class_name",
            "INDUTY_TYPE": "induty_type",
            "CANCEL_DATE": "cancel_date",
            "CANCEL_NAME": "cancel_name",
            "CHANGE_DATE": "change_date",
            "NARCOTIC_KIND_CODE": "narcotic_kind_code",
            "GBN_NAME": "gbn_name",
            "TOTAL_CONTENT": "total_content",
            "EE_DOC_DATA": "ee_doc_data",
            "UD_DOC_DATA": "ud_doc_data",
            "NB_DOC_DATA": "nb_doc_data",
            "PN_DOC_DATA": "pn_doc_data",
            "MAIN_ITEM_INGR": "main_item_ingr",
            "INGR_NAME": "ingr_name",
            "ATC_CODE": "atc_code",
            "ITEM_ENG_NAME": "item_eng_name",
            "ENTP_ENG_NAME": "entp_eng_name",
            "MAIN_INGR_ENG": "main_ingr_eng",
            "BIZRNO": "bizrno",
            "RARE_DRUG_YN": "rare_drug_yn",
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
            "RTRVL_CMMND_DT": "rtrvl_cmmnd_dt",
            "BIZRNO": "bizrno",
            "STD_CD": "std_cd",
            "MAPPED_ITEM_SEQ": "mapped_item_seq",
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
    (
        "drug_max_dosage",
        DrugMaxDosage,
        {
            "CPNT_CD": "cpnt_cd",
            "DRUG_CPNT_KOR_NM": "drug_cpnt_kor_nm",
            "DRUG_CPNT_ENG_NM": "drug_cpnt_eng_nm",
            "FOML_CD": "foml_cd",
            "FOML_NM": "foml_nm",
            "DOSAGE_ROUTE_CODE": "dosage_route_code",
            "DAY_MAX_DOSG_QY_UNIT": "day_max_dosg_qy_unit",
            "DAY_MAX_DOSG_QY": "day_max_dosg_qy",
        },
    ),
    (
        "drug_bundle_info",
        DrugBundleInfo,
        {
            "trustIndutyCode": "trust_induty_code",
            "trustItemName": "trust_item_name",
            "trustMainingr": "trust_mainingr",
            "trustQntList": "trust_qnt_list",
            "trustEntpName": "trust_entp_name",
            "trustManuf": "trust_manuf",
            "trustItemPermitDate": "trust_item_permit_date",
            "trustHiraMainingrCode": "trust_hira_mainingr_code",
            "trustHiraPrductCode": "trust_hira_prduct_code",
            "trustAtcCode": "trust_atc_code",
            "trustCancelName": "trust_cancel_name",
            "cnsgnItemSeq": "cnsgn_item_seq",
            "cnsgnItemName": "cnsgn_item_name",
            "cnsgnEntpName": "cnsgn_entp_name",
            "cnsgnManuf": "cnsgn_manuf",
            "cnsgnItemPermitDate": "cnsgn_item_permit_date",
            "cnsgnHiraPrductCode": "cnsgn_hira_prduct_code",
            "cnsgnCancelName": "cnsgn_cancel_name",
        },
    ),
    (
        "drug_prdt_prmsn_list",
        DrugPrdtPrmsnList,
        {
            "ITEM_SEQ": "item_seq",
            "ITEM_NAME": "item_name",
            "ITEM_ENG_NAME": "item_eng_name",
            "ENTP_NAME": "entp_name",
            "ENTP_ENG_NAME": "entp_eng_name",
            "ENTP_SEQ": "entp_seq",
            "ENTP_NO": "entp_no",
            "ITEM_PERMIT_DATE": "item_permit_date",
            "INDUTY": "induty",
            "PRDLST_STDR_CODE": "prdlst_stdr_code",
            "SPCLTY_PBLC": "spclty_pblc",
            "PRDUCT_TYPE": "prduct_type",
            "PRDUCT_PRMISN_NO": "prduct_prmisn_no",
            "ITEM_INGR_NAME": "item_ingr_name",
            "ITEM_INGR_CNT": "item_ingr_cnt",
            "BIG_PRDT_IMG_URL": "big_prdt_img_url",
            "PERMIT_KIND_CODE": "permit_kind_code",
            "CANCEL_DATE": "cancel_date",
            "CANCEL_NAME": "cancel_name",
            "EDI_CODE": "edi_code",
            "BIZRNO": "bizrno",
        },
    ),
    (
        "drug_prdt_mcpn_detail",
        DrugPrdtMcpnDetail,
        {
            "ENTRPS_PRMISN_NO": "entrps_prmisn_no",
            "ENTRPS": "entrps",
            "PRDUCT": "prduct",
            "MTRAL_SN": "mtral_sn",
            "MTRAL_CODE": "mtral_code",
            "MTRAL_NM": "mtral_nm",
            "QNT": "qnt",
            "INGD_UNIT_CD": "ingd_unit_cd",
            "ITEM_SEQ": "item_seq",
            "MAIN_INGR_ENG": "main_ingr_eng",
            "BIZRNO": "bizrno",
            "CPNT_CTNT_CONT": "cpnt_ctnt_cont",
            "TAMT_SEQ": "tamt_seq",
        },
    ),
]

_PRODUCT_RULE_COLS = {"ITEM_SEQ": "item_seq", "PROHBT_CONTENT": "prohbt_content", "REMARK": "remark"}
_INGR_CODE_COLS = {"INGR_CODE": "ingr_code", "INGR_NAME": "ingr_name"}
_PRODUCT_RULE_EXTRA_COLS = {
    "TYPE_NAME": "type_name",
    "MIX_TYPE": "mix_type",
    "INGR_ENG_NAME": "ingr_eng_name",
    "MIX_INGR": "mix_ingr",
    "FORM_NAME": "form_name",
    "ITEM_NAME": "item_name",
    "ITEM_PERMIT_DATE": "item_permit_date",
    "ENTP_NAME": "entp_name",
    "CHART": "chart",
    "CLASS_CODE": "class_code",
    "CLASS_NAME": "class_name",
    "ETC_OTC_NAME": "etc_otc_name",
    "MAIN_INGR": "main_ingr",
    "NOTIFICATION_DATE": "notification_date",
    "INGR_ENG_NAME_FULL": "ingr_eng_name_full",
    "CHANGE_DATE": "change_date",
}

for _table, _model in [
    ("dur_prod_pwnm_taboo", DurProdPwnmTaboo),
    ("dur_prod_odsn_atent", DurProdOdsnAtent),
    ("dur_prod_spcify_agrde_taboo", DurProdSpcifyAgrdeTaboo),
    ("dur_prod_mdctn_pd_atent", DurProdMdctnPdAtent),
    ("dur_prod_cpcty_atent", DurProdCpctyAtent),
]:
    _TABLE_SPECS.append((_table, _model, {**_PRODUCT_RULE_COLS, **_INGR_CODE_COLS, **_PRODUCT_RULE_EXTRA_COLS}))

_TABLE_SPECS.append(
    (
        "dur_prod_seobang_partition",
        DurProdSeobangPartition,
        {
            **_PRODUCT_RULE_COLS,
            "TYPE_NAME": "type_name",
            "ITEM_NAME": "item_name",
            "ITEM_PERMIT_DATE": "item_permit_date",
            "FORM_CODE_NAME": "form_code_name",
            "ENTP_NAME": "entp_name",
            "CHART": "chart",
            "CLASS_CODE": "class_code",
            "CLASS_NAME": "class_name",
            "ETC_OTC_NAME": "etc_otc_name",
            "MIX": "mix",
            "MAIN_INGR": "main_ingr",
            "CHANGE_DATE": "change_date",
            "BIZRNO": "bizrno",
        },
    )
)
_TABLE_SPECS.append(
    (
        "dur_prod_efcy_dplct",
        DurProdEfcyDplct,
        {
            **_PRODUCT_RULE_COLS,
            **_INGR_CODE_COLS,
            "ITEM_NAME": "item_name",
            "DUR_SEQ": "dur_seq",
            "EFFECT_NAME": "effect_name",
            "TYPE_NAME": "type_name",
            "INGR_ENG_NAME": "ingr_eng_name",
            "FORM_CODE_NAME": "form_code_name",
            "MIX": "mix",
            "MIX_INGR": "mix_ingr",
            "ITEM_PERMIT_DATE": "item_permit_date",
            "CHART": "chart",
            "ENTP_NAME": "entp_name",
            "FORM_CODE": "form_code",
            "FORM_NAME": "form_name",
            "ETC_OTC_CODE": "etc_otc_code",
            "ETC_OTC_NAME": "etc_otc_name",
            "CLASS_CODE": "class_code",
            "CLASS_NAME": "class_name",
            "MAIN_INGR": "main_ingr",
            "NOTIFICATION_DATE": "notification_date",
            "INGR_ENG_NAME_FULL": "ingr_eng_name_full",
            "CHANGE_DATE": "change_date",
            "BIZRNO": "bizrno",
            "SERS_NAME": "sers_name",
        },
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
            "DUR_SEQ": "dur_seq",
            "TYPE_CODE": "type_code",
            "TYPE_NAME": "type_name",
            "MIX": "mix",
            "INGR_ENG_NAME": "ingr_eng_name",
            "MIX_INGR": "mix_ingr",
            "ENTP_NAME": "entp_name",
            "CHART": "chart",
            "FORM_CODE": "form_code",
            "ETC_OTC_CODE": "etc_otc_code",
            "CLASS_CODE": "class_code",
            "FORM_NAME": "form_name",
            "ETC_OTC_NAME": "etc_otc_name",
            "CLASS_NAME": "class_name",
            "MAIN_INGR": "main_ingr",
            "MIXTURE_DUR_SEQ": "mixture_dur_seq",
            "MIXTURE_MIX": "mixture_mix",
            "MIXTURE_INGR_ENG_NAME": "mixture_ingr_eng_name",
            "MIXTURE_ENTP_NAME": "mixture_entp_name",
            "MIXTURE_FORM_CODE": "mixture_form_code",
            "MIXTURE_ETC_OTC_CODE": "mixture_etc_otc_code",
            "MIXTURE_CLASS_CODE": "mixture_class_code",
            "MIXTURE_FORM_NAME": "mixture_form_name",
            "MIXTURE_ETC_OTC_NAME": "mixture_etc_otc_name",
            "MIXTURE_CLASS_NAME": "mixture_class_name",
            "MIXTURE_MAIN_INGR": "mixture_main_ingr",
            "NOTIFICATION_DATE": "notification_date",
            "ITEM_PERMIT_DATE": "item_permit_date",
            "MIXTURE_ITEM_PERMIT_DATE": "mixture_item_permit_date",
            "MIXTURE_CHART": "mixture_chart",
            "CHANGE_DATE": "change_date",
            "MIXTURE_CHANGE_DATE": "mixture_change_date",
            "BIZRNO": "bizrno",
        },
    )
)

_INGREDIENT_RULE_COLS = {
    "INGR_CODE": "ingr_code",
    "INGR_NAME": "ingr_name",
    "PROHBT_CONTENT": "prohbt_content",
    "REMARK": "remark",
}
_INGREDIENT_RULE_EXTRA_COLS = {
    "DUR_SEQ": "dur_seq",
    "TYPE_NAME": "type_name",
    "MIX_TYPE": "mix_type",
    "INGR_ENG_NAME": "ingr_eng_name",
    "MIX_INGR": "mix_ingr",
    "ORI_INGR": "ori_ingr",
    "NOTIFICATION_DATE": "notification_date",
    "DEL_YN": "del_yn",
}

_TABLE_SPECS.append(
    (
        "dur_pwnm_taboo",
        DurPwnmTaboo,
        {
            **_INGREDIENT_RULE_COLS,
            **_INGREDIENT_RULE_EXTRA_COLS,
            "CLASS_NAME": "class_name",
            "FORM_NAME": "form_name",
            "GRADE": "grade",
        },
    )
)
_TABLE_SPECS.append(
    (
        "dur_odsn_atent",
        DurOdsnAtent,
        {**_INGREDIENT_RULE_COLS, **_INGREDIENT_RULE_EXTRA_COLS, "FORM_NAME": "form_name"},
    )
)
_TABLE_SPECS.append(
    (
        "dur_spcify_agrde_taboo",
        DurSpcifyAgrdeTaboo,
        {
            **_INGREDIENT_RULE_COLS,
            **_INGREDIENT_RULE_EXTRA_COLS,
            "CLASS_NAME": "class_name",
            "FORM_NAME": "form_name",
            "AGE_BASE": "age_base",
        },
    )
)
_TABLE_SPECS.append(
    (
        "dur_cpcty_atent",
        DurCpctyAtent,
        {
            **_INGREDIENT_RULE_COLS,
            **_INGREDIENT_RULE_EXTRA_COLS,
            "CLASS_NAME": "class_name",
            "FORM_NAME": "form_name",
            "MAX_QTY": "max_qty",
        },
    )
)
_TABLE_SPECS.append(
    (
        "dur_efcy_dplct",
        DurEfcyDplct,
        {
            **_INGREDIENT_RULE_COLS,
            **_INGREDIENT_RULE_EXTRA_COLS,
            "CLASS_NAME": "class_name",
            "EFFECT_CODE": "effect_code",
            "SERS_NAME": "sers_name",
        },
    )
)
_TABLE_SPECS.append(
    (
        "dur_mdctn_pd_atent",
        DurMdctnPdAtent,
        {
            **_INGREDIENT_RULE_COLS,
            **_INGREDIENT_RULE_EXTRA_COLS,
            "CLASS_NAME": "class_name",
            "FORM_NAME": "form_name",
            "MAX_DOSAGE_TERM": "max_dosage_term",
        },
    )
)

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
            "TYPE_NAME": "type_name",
            "MIX_TYPE": "mix_type",
            "INGR_ENG_NAME": "ingr_eng_name",
            "MIX": "mix",
            "ORI": "ori",
            "CLASS": "class_",
            "MIXTURE_MIX_TYPE": "mixture_mix_type",
            "MIXTURE_INGR_ENG_NAME": "mixture_ingr_eng_name",
            "MIXTURE_MIX": "mixture_mix",
            "MIXTURE_ORI": "mixture_ori",
            "MIXTURE_CLASS": "mixture_class",
            "NOTIFICATION_DATE": "notification_date",
            "DEL_YN": "del_yn",
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
