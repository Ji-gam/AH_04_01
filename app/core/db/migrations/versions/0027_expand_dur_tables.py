"""expand DUR tables to full API/CSV原本 columns, add missing raw tables

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 품목기준(ITEM_SEQ) 규칙 5종(dur_prod_pwnm_taboo/odsn_atent/spcify_agrde_taboo/mdctn_pd_atent/
# cpcty_atent)이 공유하는 추가 컬럼 - 전부 0026에서 빠졌던 원본 컬럼.
_PRODUCT_RULE_EXTRA_COLUMNS = [
    "type_name",
    "mix_type",
    "ingr_eng_name",
    "mix_ingr",
    "form_name",
    "item_name",
    "item_permit_date",
    "entp_name",
    "chart",
    "class_code",
    "class_name",
    "etc_otc_name",
    "main_ingr",
    "notification_date",
    "ingr_eng_name_full",
    "change_date",
]

# 성분기준(INGR_CODE) 규칙 6종이 공통으로 공유하는 추가 컬럼.
_INGREDIENT_RULE_EXTRA_COLUMNS = [
    "dur_seq",
    "type_name",
    "mix_type",
    "ingr_eng_name",
    "mix_ingr",
    "ori_ingr",
    "notification_date",
    "del_yn",
]


def _add_text_columns(table: str, columns: list[str]) -> None:
    for column in columns:
        op.add_column(table, sa.Column(column, sa.Text(), nullable=True))


def upgrade() -> None:
    # --- 1) 기존 21개 테이블에 CSV/API 원본에는 있으나 0026에서 빠졌던 컬럼 추가 ---
    _add_text_columns("drugs_data", ["open_de", "update_de", "bizrno"])

    _add_text_columns(
        "dur_prod_master_list",
        [
            "item_permit_date",
            "etc_otc_code",
            "class_no",
            "chart",
            "bar_code",
            "material_name",
            "ee_doc_id",
            "ud_doc_id",
            "nb_doc_id",
            "insert_file",
            "storage_method",
            "valid_term",
            "reexam_target",
            "reexam_date",
            "pack_unit",
            "edi_code",
            "cancel_date",
            "cancel_name",
            "type_code",
            "type_name",
            "change_date",
            "bizrno",
        ],
    )

    _add_text_columns(
        "drug_identification",
        [
            "item_name",
            "entp_seq",
            "entp_name",
            "print_front",
            "print_back",
            "line_front",
            "line_back",
            "leng_long",
            "leng_short",
            "thick",
            "img_regist_ts",
            "class_no",
            "class_name",
            "item_permit_date",
            "mark_code_front_anal",
            "mark_code_back_anal",
            "mark_code_front_img",
            "mark_code_back_img",
            "item_eng_name",
            "change_date",
            "mark_code_back",
            "edi_code",
            "bizrno",
            "std_cd",
        ],
    )

    _add_text_columns(
        "drug_prdt_prmsn_detail",
        [
            "item_name",
            "entp_name",
            "item_permit_date",
            "cnsgn_manuf",
            "etc_otc_code",
            "chart",
            "bar_code",
            "material_name",
            "ee_doc_id",
            "ud_doc_id",
            "nb_doc_id",
            "insert_file",
            "storage_method",
            "valid_term",
            "reexam_target",
            "reexam_date",
            "pack_unit",
            "edi_code",
            "permit_kind_name",
            "entp_no",
            "make_material_flag",
            "newdrug_class_name",
            "induty_type",
            "cancel_date",
            "cancel_name",
            "change_date",
            "gbn_name",
            "total_content",
            "ee_doc_data",
            "ud_doc_data",
            "nb_doc_data",
            "pn_doc_data",
            "main_item_ingr",
            "ingr_name",
            "item_eng_name",
            "entp_eng_name",
            "main_ingr_eng",
            "bizrno",
        ],
    )

    _add_text_columns(
        "medicine_recalls",
        ["rtrvl_cmmnd_dt", "bizrno", "std_cd", "mapped_item_seq"],
    )

    for table in [
        "dur_prod_pwnm_taboo",
        "dur_prod_odsn_atent",
        "dur_prod_spcify_agrde_taboo",
        "dur_prod_mdctn_pd_atent",
        "dur_prod_cpcty_atent",
    ]:
        _add_text_columns(table, _PRODUCT_RULE_EXTRA_COLUMNS)

    _add_text_columns(
        "dur_prod_seobang_partition",
        [
            "type_name",
            "item_name",
            "item_permit_date",
            "form_code_name",
            "entp_name",
            "chart",
            "class_code",
            "class_name",
            "etc_otc_name",
            "mix",
            "main_ingr",
            "change_date",
            "bizrno",
        ],
    )

    _add_text_columns(
        "dur_prod_efcy_dplct",
        [
            "dur_seq",
            "effect_name",
            "type_name",
            "ingr_eng_name",
            "form_code_name",
            "mix",
            "mix_ingr",
            "item_permit_date",
            "chart",
            "entp_name",
            "form_code",
            "form_name",
            "etc_otc_code",
            "etc_otc_name",
            "class_code",
            "class_name",
            "main_ingr",
            "notification_date",
            "ingr_eng_name_full",
            "change_date",
            "bizrno",
            "sers_name",
        ],
    )

    _add_text_columns(
        "dur_prod_usjnt_taboo",
        [
            "dur_seq",
            "type_code",
            "type_name",
            "mix",
            "ingr_eng_name",
            "mix_ingr",
            "entp_name",
            "chart",
            "form_code",
            "etc_otc_code",
            "class_code",
            "form_name",
            "etc_otc_name",
            "class_name",
            "main_ingr",
            "mixture_dur_seq",
            "mixture_mix",
            "mixture_ingr_eng_name",
            "mixture_entp_name",
            "mixture_form_code",
            "mixture_etc_otc_code",
            "mixture_class_code",
            "mixture_form_name",
            "mixture_etc_otc_name",
            "mixture_class_name",
            "mixture_main_ingr",
            "notification_date",
            "item_permit_date",
            "mixture_item_permit_date",
            "mixture_chart",
            "change_date",
            "mixture_change_date",
            "bizrno",
        ],
    )

    _add_text_columns("dur_pwnm_taboo", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "form_name", "grade"])
    _add_text_columns("dur_odsn_atent", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "form_name"])
    _add_text_columns(
        "dur_spcify_agrde_taboo", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "form_name", "age_base"]
    )
    _add_text_columns("dur_cpcty_atent", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "form_name", "max_qty"])
    _add_text_columns("dur_efcy_dplct", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "effect_code", "sers_name"])
    _add_text_columns(
        "dur_mdctn_pd_atent", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "form_name", "max_dosage_term"]
    )

    _add_text_columns(
        "dur_usjnt_taboo",
        [
            "type_name",
            "mix_type",
            "ingr_eng_name",
            "mix",
            "ori",
            "class",
            "mixture_mix_type",
            "mixture_ingr_eng_name",
            "mixture_mix",
            "mixture_ori",
            "mixture_class",
            "notification_date",
            "del_yn",
        ],
    )

    # --- 2) 지금까지 통째로 빠졌던 4개 원본 테이블 추가 ---
    op.create_table(
        "drug_max_dosage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cpnt_cd", sa.String(length=20), nullable=True),
        sa.Column("drug_cpnt_kor_nm", sa.Text(), nullable=True),
        sa.Column("drug_cpnt_eng_nm", sa.Text(), nullable=True),
        sa.Column("foml_cd", sa.Text(), nullable=True),
        sa.Column("foml_nm", sa.Text(), nullable=True),
        sa.Column("dosage_route_code", sa.Text(), nullable=True),
        sa.Column("day_max_dosg_qy_unit", sa.Text(), nullable=True),
        sa.Column("day_max_dosg_qy", sa.Text(), nullable=True),
    )
    op.create_index("ix_drug_max_dosage_cpnt_cd", "drug_max_dosage", ["cpnt_cd"])

    op.create_table(
        "drug_bundle_info",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trust_induty_code", sa.Text(), nullable=True),
        sa.Column("trust_item_name", sa.Text(), nullable=True),
        sa.Column("trust_mainingr", sa.Text(), nullable=True),
        sa.Column("trust_qnt_list", sa.Text(), nullable=True),
        sa.Column("trust_entp_name", sa.Text(), nullable=True),
        sa.Column("trust_manuf", sa.Text(), nullable=True),
        sa.Column("trust_item_permit_date", sa.Text(), nullable=True),
        sa.Column("trust_hira_mainingr_code", sa.Text(), nullable=True),
        sa.Column("trust_hira_prduct_code", sa.Text(), nullable=True),
        sa.Column("trust_atc_code", sa.Text(), nullable=True),
        sa.Column("trust_cancel_name", sa.Text(), nullable=True),
        sa.Column("cnsgn_item_seq", sa.String(length=20), nullable=True),
        sa.Column("cnsgn_item_name", sa.Text(), nullable=True),
        sa.Column("cnsgn_entp_name", sa.Text(), nullable=True),
        sa.Column("cnsgn_manuf", sa.Text(), nullable=True),
        sa.Column("cnsgn_item_permit_date", sa.Text(), nullable=True),
        sa.Column("cnsgn_hira_prduct_code", sa.Text(), nullable=True),
        sa.Column("cnsgn_cancel_name", sa.Text(), nullable=True),
    )
    op.create_index("ix_drug_bundle_info_cnsgn_item_seq", "drug_bundle_info", ["cnsgn_item_seq"])

    op.create_table(
        "drug_prdt_prmsn_list",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_seq", sa.String(length=20), nullable=True),
        sa.Column("item_name", sa.Text(), nullable=True),
        sa.Column("item_eng_name", sa.Text(), nullable=True),
        sa.Column("entp_name", sa.Text(), nullable=True),
        sa.Column("entp_eng_name", sa.Text(), nullable=True),
        sa.Column("entp_seq", sa.Text(), nullable=True),
        sa.Column("entp_no", sa.Text(), nullable=True),
        sa.Column("item_permit_date", sa.Text(), nullable=True),
        sa.Column("induty", sa.Text(), nullable=True),
        sa.Column("prdlst_stdr_code", sa.Text(), nullable=True),
        sa.Column("spclty_pblc", sa.Text(), nullable=True),
        sa.Column("prduct_type", sa.Text(), nullable=True),
        sa.Column("prduct_prmisn_no", sa.Text(), nullable=True),
        sa.Column("item_ingr_name", sa.Text(), nullable=True),
        sa.Column("item_ingr_cnt", sa.Text(), nullable=True),
        sa.Column("big_prdt_img_url", sa.Text(), nullable=True),
        sa.Column("permit_kind_code", sa.Text(), nullable=True),
        sa.Column("cancel_date", sa.Text(), nullable=True),
        sa.Column("cancel_name", sa.Text(), nullable=True),
        sa.Column("edi_code", sa.Text(), nullable=True),
        sa.Column("bizrno", sa.Text(), nullable=True),
    )
    op.create_index("ix_drug_prdt_prmsn_list_item_seq", "drug_prdt_prmsn_list", ["item_seq"])

    op.create_table(
        "drug_prdt_mcpn_detail",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entrps_prmisn_no", sa.Text(), nullable=True),
        sa.Column("entrps", sa.Text(), nullable=True),
        sa.Column("prduct", sa.Text(), nullable=True),
        sa.Column("mtral_sn", sa.Text(), nullable=True),
        sa.Column("mtral_code", sa.String(length=20), nullable=True),
        sa.Column("mtral_nm", sa.Text(), nullable=True),
        sa.Column("qnt", sa.Text(), nullable=True),
        sa.Column("ingd_unit_cd", sa.Text(), nullable=True),
        sa.Column("item_seq", sa.String(length=20), nullable=True),
        sa.Column("main_ingr_eng", sa.Text(), nullable=True),
        sa.Column("bizrno", sa.Text(), nullable=True),
        sa.Column("cpnt_ctnt_cont", sa.Text(), nullable=True),
        sa.Column("tamt_seq", sa.Text(), nullable=True),
    )
    op.create_index("ix_drug_prdt_mcpn_detail_item_seq", "drug_prdt_mcpn_detail", ["item_seq"])
    op.create_index("ix_drug_prdt_mcpn_detail_mtral_code", "drug_prdt_mcpn_detail", ["mtral_code"])


def downgrade() -> None:
    op.drop_table("drug_prdt_mcpn_detail")
    op.drop_table("drug_prdt_prmsn_list")
    op.drop_table("drug_bundle_info")
    op.drop_table("drug_max_dosage")

    _drop_columns(
        "dur_usjnt_taboo",
        [
            "type_name",
            "mix_type",
            "ingr_eng_name",
            "mix",
            "ori",
            "class",
            "mixture_mix_type",
            "mixture_ingr_eng_name",
            "mixture_mix",
            "mixture_ori",
            "mixture_class",
            "notification_date",
            "del_yn",
        ],
    )

    _drop_columns("dur_mdctn_pd_atent", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "form_name", "max_dosage_term"])
    _drop_columns("dur_efcy_dplct", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "effect_code", "sers_name"])
    _drop_columns("dur_cpcty_atent", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "form_name", "max_qty"])
    _drop_columns("dur_spcify_agrde_taboo", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "form_name", "age_base"])
    _drop_columns("dur_odsn_atent", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "form_name"])
    _drop_columns("dur_pwnm_taboo", [*_INGREDIENT_RULE_EXTRA_COLUMNS, "class_name", "form_name", "grade"])

    _drop_columns(
        "dur_prod_usjnt_taboo",
        [
            "dur_seq",
            "type_code",
            "type_name",
            "mix",
            "ingr_eng_name",
            "mix_ingr",
            "entp_name",
            "chart",
            "form_code",
            "etc_otc_code",
            "class_code",
            "form_name",
            "etc_otc_name",
            "class_name",
            "main_ingr",
            "mixture_dur_seq",
            "mixture_mix",
            "mixture_ingr_eng_name",
            "mixture_entp_name",
            "mixture_form_code",
            "mixture_etc_otc_code",
            "mixture_class_code",
            "mixture_form_name",
            "mixture_etc_otc_name",
            "mixture_class_name",
            "mixture_main_ingr",
            "notification_date",
            "item_permit_date",
            "mixture_item_permit_date",
            "mixture_chart",
            "change_date",
            "mixture_change_date",
            "bizrno",
        ],
    )

    _drop_columns(
        "dur_prod_efcy_dplct",
        [
            "dur_seq",
            "effect_name",
            "type_name",
            "ingr_eng_name",
            "form_code_name",
            "mix",
            "mix_ingr",
            "item_permit_date",
            "chart",
            "entp_name",
            "form_code",
            "form_name",
            "etc_otc_code",
            "etc_otc_name",
            "class_code",
            "class_name",
            "main_ingr",
            "notification_date",
            "ingr_eng_name_full",
            "change_date",
            "bizrno",
            "sers_name",
        ],
    )

    _drop_columns(
        "dur_prod_seobang_partition",
        [
            "type_name",
            "item_name",
            "item_permit_date",
            "form_code_name",
            "entp_name",
            "chart",
            "class_code",
            "class_name",
            "etc_otc_name",
            "mix",
            "main_ingr",
            "change_date",
            "bizrno",
        ],
    )

    for table in [
        "dur_prod_cpcty_atent",
        "dur_prod_mdctn_pd_atent",
        "dur_prod_spcify_agrde_taboo",
        "dur_prod_odsn_atent",
        "dur_prod_pwnm_taboo",
    ]:
        _drop_columns(table, _PRODUCT_RULE_EXTRA_COLUMNS)

    _drop_columns("medicine_recalls", ["rtrvl_cmmnd_dt", "bizrno", "std_cd", "mapped_item_seq"])

    _drop_columns(
        "drug_prdt_prmsn_detail",
        [
            "item_name",
            "entp_name",
            "item_permit_date",
            "cnsgn_manuf",
            "etc_otc_code",
            "chart",
            "bar_code",
            "material_name",
            "ee_doc_id",
            "ud_doc_id",
            "nb_doc_id",
            "insert_file",
            "storage_method",
            "valid_term",
            "reexam_target",
            "reexam_date",
            "pack_unit",
            "edi_code",
            "permit_kind_name",
            "entp_no",
            "make_material_flag",
            "newdrug_class_name",
            "induty_type",
            "cancel_date",
            "cancel_name",
            "change_date",
            "gbn_name",
            "total_content",
            "ee_doc_data",
            "ud_doc_data",
            "nb_doc_data",
            "pn_doc_data",
            "main_item_ingr",
            "ingr_name",
            "item_eng_name",
            "entp_eng_name",
            "main_ingr_eng",
            "bizrno",
        ],
    )

    _drop_columns(
        "drug_identification",
        [
            "item_name",
            "entp_seq",
            "entp_name",
            "print_front",
            "print_back",
            "line_front",
            "line_back",
            "leng_long",
            "leng_short",
            "thick",
            "img_regist_ts",
            "class_no",
            "class_name",
            "item_permit_date",
            "mark_code_front_anal",
            "mark_code_back_anal",
            "mark_code_front_img",
            "mark_code_back_img",
            "item_eng_name",
            "change_date",
            "mark_code_back",
            "edi_code",
            "bizrno",
            "std_cd",
        ],
    )

    _drop_columns(
        "dur_prod_master_list",
        [
            "item_permit_date",
            "etc_otc_code",
            "class_no",
            "chart",
            "bar_code",
            "material_name",
            "ee_doc_id",
            "ud_doc_id",
            "nb_doc_id",
            "insert_file",
            "storage_method",
            "valid_term",
            "reexam_target",
            "reexam_date",
            "pack_unit",
            "edi_code",
            "cancel_date",
            "cancel_name",
            "type_code",
            "type_name",
            "change_date",
            "bizrno",
        ],
    )

    _drop_columns("drugs_data", ["open_de", "update_de", "bizrno"])


def _drop_columns(table: str, columns: list[str]) -> None:
    for column in columns:
        op.drop_column(table, column)
