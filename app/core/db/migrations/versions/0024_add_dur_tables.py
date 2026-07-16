"""add DUR tables (migrate reference data from SQLite drugs_full.db to MySQL)

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _product_rule_columns(with_ingr_code: bool, with_item_name: bool = False) -> list[sa.Column]:
    cols = [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_seq", sa.String(length=20), nullable=False),
    ]
    if with_item_name:
        cols.append(sa.Column("item_name", sa.String(length=255), nullable=True))
    if with_ingr_code:
        cols.append(sa.Column("ingr_code", sa.String(length=20), nullable=True))
        cols.append(sa.Column("ingr_name", sa.String(length=255), nullable=True))
    cols.append(sa.Column("prohbt_content", sa.Text(), nullable=True))
    cols.append(sa.Column("remark", sa.Text(), nullable=True))
    return cols


def _ingredient_rule_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ingr_code", sa.String(length=20), nullable=False),
        sa.Column("ingr_name", sa.String(length=255), nullable=True),
        sa.Column("prohbt_content", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "drugs_data",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_seq", sa.String(length=20), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("entp_name", sa.String(length=255), nullable=True),
        sa.Column("efcy_qesitm", sa.Text(), nullable=True),
        sa.Column("use_method_qesitm", sa.Text(), nullable=True),
        sa.Column("atpn_warn_qesitm", sa.Text(), nullable=True),
        sa.Column("atpn_qesitm", sa.Text(), nullable=True),
        sa.Column("intrc_qesitm", sa.Text(), nullable=True),
        sa.Column("se_qesitm", sa.Text(), nullable=True),
        sa.Column("deposit_method_qesitm", sa.Text(), nullable=True),
        sa.Column("item_image", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_drugs_data_item_seq", "drugs_data", ["item_seq"])
    op.create_index("ix_drugs_data_item_name", "drugs_data", ["item_name"])

    op.create_table(
        "drug_identification",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_seq", sa.String(length=20), nullable=False),
        sa.Column("chart", sa.String(length=255), nullable=True),
        sa.Column("drug_shape", sa.String(length=100), nullable=True),
        sa.Column("color_class1", sa.String(length=100), nullable=True),
        sa.Column("color_class2", sa.String(length=100), nullable=True),
        sa.Column("mark_code_front", sa.String(length=255), nullable=True),
        sa.Column("etc_otc_name", sa.String(length=100), nullable=True),
        sa.Column("form_code_name", sa.String(length=100), nullable=True),
        sa.Column("item_image", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_drug_identification_item_seq", "drug_identification", ["item_seq"])

    op.create_table(
        "drug_prdt_prmsn_detail",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_seq", sa.String(length=20), nullable=False),
        sa.Column("atc_code", sa.String(length=50), nullable=True),
        sa.Column("rare_drug_yn", sa.String(length=5), nullable=True),
        sa.Column("narcotic_kind_code", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_drug_prdt_prmsn_detail_item_seq", "drug_prdt_prmsn_detail", ["item_seq"])

    op.create_table(
        "medicine_recalls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_seq", sa.String(length=20), nullable=True),
        sa.Column("prduct", sa.String(length=255), nullable=True),
        sa.Column("entrps", sa.String(length=255), nullable=True),
        sa.Column("rtrvl_resn", sa.Text(), nullable=True),
        sa.Column("recall_command_date", sa.String(length=20), nullable=True),
        sa.Column("enfrc_yn", sa.String(length=5), nullable=True),
    )
    op.create_index("ix_medicine_recalls_item_seq", "medicine_recalls", ["item_seq"])

    op.create_table(
        "item_ingredient_map",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_seq", sa.String(length=20), nullable=False),
        sa.Column("ingr_code", sa.String(length=20), nullable=False),
        sa.Column("ingr_name", sa.String(length=255), nullable=True),
        sa.Column("qnt", sa.String(length=50), nullable=True),
        sa.Column("ingd_unit_cd", sa.String(length=50), nullable=True),
    )
    op.create_index("ix_item_ingredient_map_item_seq", "item_ingredient_map", ["item_seq"])
    op.create_index("ix_item_ingredient_map_ingr_code", "item_ingredient_map", ["ingr_code"])

    # 품목기준(ITEM_SEQ) DUR 규칙 6종 - 1단계 SINGLE_DRUG_RULE_TABLES와 3단계 성분코드 역추적용.
    for table in [
        "dur_prod_pwnm_taboo",
        "dur_prod_odsn_atent",
        "dur_prod_spcify_agrde_taboo",
        "dur_prod_mdctn_pd_atent",
        "dur_prod_cpcty_atent",
    ]:
        op.create_table(table, *_product_rule_columns(with_ingr_code=True))
        op.create_index(f"ix_{table}_item_seq", table, ["item_seq"])
        op.create_index(f"ix_{table}_ingr_code", table, ["ingr_code"])

    # dur_prod_seobang_partition은 INGR_CODE 컬럼 자체가 없다(제형 속성이라 성분 무관).
    op.create_table("dur_prod_seobang_partition", *_product_rule_columns(with_ingr_code=False))
    op.create_index("ix_dur_prod_seobang_partition_item_seq", "dur_prod_seobang_partition", ["item_seq"])

    op.create_table("dur_prod_efcy_dplct", *_product_rule_columns(with_ingr_code=True, with_item_name=True))
    op.create_index("ix_dur_prod_efcy_dplct_item_seq", "dur_prod_efcy_dplct", ["item_seq"])
    op.create_index("ix_dur_prod_efcy_dplct_ingr_code", "dur_prod_efcy_dplct", ["ingr_code"])

    op.create_table(
        "dur_prod_usjnt_taboo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("item_seq", sa.String(length=20), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=True),
        sa.Column("mixture_item_seq", sa.String(length=20), nullable=False),
        sa.Column("mixture_item_name", sa.String(length=255), nullable=True),
        sa.Column("ingr_code", sa.String(length=20), nullable=True),
        sa.Column("ingr_kor_name", sa.String(length=255), nullable=True),
        sa.Column("mixture_ingr_code", sa.String(length=20), nullable=True),
        sa.Column("mixture_ingr_kor_name", sa.String(length=255), nullable=True),
        sa.Column("prohbt_content", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
    )
    op.create_index("ix_dur_prod_usjnt_taboo_item_seq", "dur_prod_usjnt_taboo", ["item_seq"])
    op.create_index("ix_dur_prod_usjnt_taboo_mixture_item_seq", "dur_prod_usjnt_taboo", ["mixture_item_seq"])
    op.create_index("ix_dur_prod_usjnt_taboo_ingr_code", "dur_prod_usjnt_taboo", ["ingr_code"])
    op.create_index("ix_dur_prod_usjnt_taboo_mixture_ingr_code", "dur_prod_usjnt_taboo", ["mixture_ingr_code"])

    # 성분기준(INGR_CODE) DUR 규칙 6종 - 3단계 INGREDIENT_RULE_TABLES.
    for table in [
        "dur_pwnm_taboo",
        "dur_odsn_atent",
        "dur_spcify_agrde_taboo",
        "dur_cpcty_atent",
        "dur_efcy_dplct",
        "dur_mdctn_pd_atent",
    ]:
        op.create_table(table, *_ingredient_rule_columns())
        op.create_index(f"ix_{table}_ingr_code", table, ["ingr_code"])

    op.create_table(
        "dur_usjnt_taboo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ingr_code", sa.String(length=20), nullable=False),
        sa.Column("ingr_kor_name", sa.String(length=255), nullable=True),
        sa.Column("mixture_ingr_code", sa.String(length=20), nullable=False),
        sa.Column("mixture_ingr_kor_name", sa.String(length=255), nullable=True),
        sa.Column("prohbt_content", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
    )
    op.create_index("ix_dur_usjnt_taboo_ingr_code", "dur_usjnt_taboo", ["ingr_code"])
    op.create_index("ix_dur_usjnt_taboo_mixture_ingr_code", "dur_usjnt_taboo", ["mixture_ingr_code"])


def downgrade() -> None:
    op.drop_table("dur_usjnt_taboo")
    for table in [
        "dur_mdctn_pd_atent",
        "dur_efcy_dplct",
        "dur_cpcty_atent",
        "dur_spcify_agrde_taboo",
        "dur_odsn_atent",
        "dur_pwnm_taboo",
    ]:
        op.drop_table(table)
    op.drop_table("dur_prod_usjnt_taboo")
    op.drop_table("dur_prod_efcy_dplct")
    op.drop_table("dur_prod_seobang_partition")
    for table in [
        "dur_prod_cpcty_atent",
        "dur_prod_mdctn_pd_atent",
        "dur_prod_spcify_agrde_taboo",
        "dur_prod_odsn_atent",
        "dur_prod_pwnm_taboo",
    ]:
        op.drop_table(table)
    op.drop_table("item_ingredient_map")
    op.drop_table("medicine_recalls")
    op.drop_table("drug_prdt_prmsn_detail")
    op.drop_table("drug_identification")
    op.drop_table("drugs_data")
