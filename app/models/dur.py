"""DUR(의약품안전사용서비스) 관련 데이터를 SQLite(`app/database/drugs_full.db`, 공공데이터포털
API 22종 전수 수집 산출물, `scripts/drug_info_sync/` 참고)에서 MySQL로 이전한 테이블.

`food_drug_interaction.py`와 같은 패턴: 원본 수집 파이프라인과 SQLite 산출물은 그대로 두고
(`app/scripts/seed_dur.py`가 읽어감), 저장 형식만 SQLite에서 MySQL로 바꿔 앱이 공유 DB에서
조회하도록 한다.

`drugs_full.db`는 24개 테이블 전체를 갖고 있지만, 여기서는 `DurScreeningRepository`
(`app/repositories/dur_repository.py`)와 `DurDrugRepository`
(`app/repositories/dur_drug_repository.py`)가 실제로 쓰는 테이블·컬럼만 옮긴다
(`drug_bundle_info`, `drug_max_dosage`, `drug_prdt_prmsn_list`, `dur_prod_master_list`는
두 리포지토리 어디에서도 조회되지 않아 제외).

컬럼 타입: ITEM_SEQ/INGR_CODE류 조인·필터 키만 인덱스가 걸리는 `String`이고, 나머지 원문
텍스트(PROHBT_CONTENT/REMARK 등)는 SQLite 원본이 전부 TEXT라 길이 제한 없는 `Text`로 옮긴다.
"""

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DrugMaster(Base):
    """e약은요(`drugs_data`, API: DrbEasyDrugInfoService) - 품목 마스터."""

    __tablename__ = "drugs_data"
    __table_args__ = (Index("ix_drugs_data_item_name", "item_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entp_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    efcy_qesitm: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_method_qesitm: Mapped[str | None] = mapped_column(Text, nullable=True)
    atpn_warn_qesitm: Mapped[str | None] = mapped_column(Text, nullable=True)
    atpn_qesitm: Mapped[str | None] = mapped_column(Text, nullable=True)
    intrc_qesitm: Mapped[str | None] = mapped_column(Text, nullable=True)
    se_qesitm: Mapped[str | None] = mapped_column(Text, nullable=True)
    deposit_method_qesitm: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_image: Mapped[str | None] = mapped_column(String(500), nullable=True)


class DrugIdentification(Base):
    """낱알식별정보(API: MdcinGrnIdntfcInfoService03)."""

    __tablename__ = "drug_identification"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    drug_shape: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color_class1: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color_class2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mark_code_front: Mapped[str | None] = mapped_column(String(255), nullable=True)
    etc_otc_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    form_code_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    item_image: Mapped[str | None] = mapped_column(String(500), nullable=True)


class DrugPrdtPrmsnDetail(Base):
    """의약품 제품 허가상세(API: DrugPrdtPrmsnInfoService07) - ATC코드/희귀의약품/마약류 구분."""

    __tablename__ = "drug_prdt_prmsn_detail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    atc_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rare_drug_yn: Mapped[str | None] = mapped_column(String(5), nullable=True)
    narcotic_kind_code: Mapped[str | None] = mapped_column(String(100), nullable=True)


class MedicineRecall(Base):
    """의약품 회수·판매중지 정보(API: MdcinRtrvlSleStpgeInfoService04)."""

    __tablename__ = "medicine_recalls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    prduct: Mapped[str | None] = mapped_column(Text, nullable=True)
    entrps: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rtrvl_resn: Mapped[str | None] = mapped_column(Text, nullable=True)
    recall_command_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    enfrc_yn: Mapped[str | None] = mapped_column(String(5), nullable=True)


class ItemIngredientMap(Base):
    """품목-성분 매핑 파생 테이블(`scripts/drug_info_sync/mapping_ingredients.py`가 생성)."""

    __tablename__ = "item_ingredient_map"
    __table_args__ = (Index("ix_item_ingredient_map_ingr_code", "ingr_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ingr_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qnt: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ingd_unit_cd: Mapped[str | None] = mapped_column(String(50), nullable=True)


def _product_rule_table(name: str, *, with_ingr_code: bool, with_item_name: bool = False):
    """품목기준(ITEM_SEQ) DUR 규칙 6종 + efcy_dplct가 공유하는 컬럼 모양을 만들어주는 헬퍼.

    `dur_prod_seobang_partition`만 INGR_CODE 컬럼이 없다(제형 속성이라 성분 무관,
    `app/repositories/dur_repository.py`의 INGREDIENT_SOURCE_TABLES 주석과 동일 이유)."""
    attrs: dict = {
        "__tablename__": name,
        "id": mapped_column(primary_key=True, autoincrement=True),
        "item_seq": mapped_column(String(20), nullable=False, index=True),
        "prohbt_content": mapped_column(Text, nullable=True),
        "remark": mapped_column(Text, nullable=True),
        "__annotations__": {
            "id": Mapped[int],
            "item_seq": Mapped[str],
            "prohbt_content": Mapped[str | None],
            "remark": Mapped[str | None],
        },
    }
    if with_item_name:
        attrs["item_name"] = mapped_column(Text, nullable=True)
        attrs["__annotations__"]["item_name"] = Mapped[str | None]
    if with_ingr_code:
        attrs["ingr_code"] = mapped_column(String(20), nullable=True, index=True)
        attrs["ingr_name"] = mapped_column(String(255), nullable=True)
        attrs["__annotations__"]["ingr_code"] = Mapped[str | None]
        attrs["__annotations__"]["ingr_name"] = Mapped[str | None]
    return type(name, (Base,), attrs)


DurProdPwnmTaboo = _product_rule_table("dur_prod_pwnm_taboo", with_ingr_code=True)
DurProdOdsnAtent = _product_rule_table("dur_prod_odsn_atent", with_ingr_code=True)
DurProdSpcifyAgrdeTaboo = _product_rule_table("dur_prod_spcify_agrde_taboo", with_ingr_code=True)
DurProdMdctnPdAtent = _product_rule_table("dur_prod_mdctn_pd_atent", with_ingr_code=True)
DurProdCpctyAtent = _product_rule_table("dur_prod_cpcty_atent", with_ingr_code=True)
DurProdSeobangPartition = _product_rule_table("dur_prod_seobang_partition", with_ingr_code=False)
DurProdEfcyDplct = _product_rule_table("dur_prod_efcy_dplct", with_ingr_code=True, with_item_name=True)

# 3단계 성분 코드 역추적에 쓰는 품목기준 테이블 6종(INGR_CODE 보유) - dur_repository.py의
# INGREDIENT_SOURCE_TABLES와 동일 목록.
PRODUCT_INGREDIENT_SOURCE_MODELS = [
    DurProdPwnmTaboo,
    DurProdOdsnAtent,
    DurProdSpcifyAgrdeTaboo,
    DurProdMdctnPdAtent,
    DurProdCpctyAtent,
    DurProdEfcyDplct,
]

# 1단계 SINGLE_DRUG_RULE_TABLES와 동일 순서(프론트 pill 고정 노출 순서와 맞춤).
SINGLE_DRUG_RULE_MODELS: list[tuple[type, str, str]] = [
    (DurProdPwnmTaboo, "PWNM", "임부금기"),
    (DurProdOdsnAtent, "ODSN", "노인주의"),
    (DurProdSpcifyAgrdeTaboo, "SPCIFY_AGRDE", "특정연령대금기"),
    (DurProdMdctnPdAtent, "MDCTN", "투여기간주의"),
    (DurProdSeobangPartition, "SEOBANG", "분할주의"),
    (DurProdCpctyAtent, "CPCTY", "용량주의"),
]


class DurProdUsjntTaboo(Base):
    """품목기준 병용금기(API: DURPrdlstInfoService03/getUsjntTabooInfoList03) - 가장 큰 테이블."""

    __tablename__ = "dur_prod_usjnt_taboo"
    __table_args__ = (
        Index("ix_dur_prod_usjnt_taboo_item_seq", "item_seq"),
        Index("ix_dur_prod_usjnt_taboo_mixture_item_seq", "mixture_item_seq"),
        Index("ix_dur_prod_usjnt_taboo_ingr_code", "ingr_code"),
        Index("ix_dur_prod_usjnt_taboo_mixture_ingr_code", "mixture_ingr_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_item_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    mixture_item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ingr_kor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mixture_ingr_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mixture_ingr_kor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


def _ingredient_rule_table(name: str):
    """성분기준(INGR_CODE) DUR 규칙 6종이 공유하는 컬럼 모양."""
    attrs = {
        "__tablename__": name,
        "id": mapped_column(primary_key=True, autoincrement=True),
        "ingr_code": mapped_column(String(20), nullable=False, index=True),
        "ingr_name": mapped_column(String(255), nullable=True),
        "prohbt_content": mapped_column(Text, nullable=True),
        "remark": mapped_column(Text, nullable=True),
        "__annotations__": {
            "id": Mapped[int],
            "ingr_code": Mapped[str],
            "ingr_name": Mapped[str | None],
            "prohbt_content": Mapped[str | None],
            "remark": Mapped[str | None],
        },
    }
    return type(name, (Base,), attrs)


DurPwnmTaboo = _ingredient_rule_table("dur_pwnm_taboo")
DurOdsnAtent = _ingredient_rule_table("dur_odsn_atent")
DurSpcifyAgrdeTaboo = _ingredient_rule_table("dur_spcify_agrde_taboo")
DurCpctyAtent = _ingredient_rule_table("dur_cpcty_atent")
DurEfcyDplct = _ingredient_rule_table("dur_efcy_dplct")
DurMdctnPdAtent = _ingredient_rule_table("dur_mdctn_pd_atent")

# 3단계 INGREDIENT_RULE_TABLES와 동일 순서.
INGREDIENT_RULE_MODELS: list[tuple[type, str]] = [
    (DurPwnmTaboo, "임부금기"),
    (DurOdsnAtent, "노인주의"),
    (DurSpcifyAgrdeTaboo, "특정연령대금기"),
    (DurCpctyAtent, "용량주의"),
    (DurEfcyDplct, "효능군중복주의"),
    (DurMdctnPdAtent, "투여기간주의"),
]


class DurUsjntTaboo(Base):
    """성분기준 병용금기(API: DURIrdntInfoService03/getUsjntTabooInfoList02)."""

    __tablename__ = "dur_usjnt_taboo"
    __table_args__ = (
        Index("ix_dur_usjnt_taboo_ingr_code", "ingr_code"),
        Index("ix_dur_usjnt_taboo_mixture_ingr_code", "mixture_ingr_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingr_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_kor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mixture_ingr_code: Mapped[str] = mapped_column(String(20), nullable=False)
    mixture_ingr_kor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


# seed_dur.py가 SQLite 원본 테이블명 -> (모델, SQLite 컬럼명 -> 모델 속성명) 매핑에 사용.
ALL_DUR_MODELS: list[type] = [
    DrugMaster,
    DrugIdentification,
    DrugPrdtPrmsnDetail,
    MedicineRecall,
    ItemIngredientMap,
    DurProdPwnmTaboo,
    DurProdOdsnAtent,
    DurProdSpcifyAgrdeTaboo,
    DurProdMdctnPdAtent,
    DurProdCpctyAtent,
    DurProdSeobangPartition,
    DurProdEfcyDplct,
    DurProdUsjntTaboo,
    DurPwnmTaboo,
    DurOdsnAtent,
    DurSpcifyAgrdeTaboo,
    DurCpctyAtent,
    DurEfcyDplct,
    DurMdctnPdAtent,
    DurUsjntTaboo,
]
