"""DUR(의약품안전사용서비스) 관련 데이터를 SQLite(`app/database/drugs_full.db`, 공공데이터포털
API 24종 전수 수집 산출물, `scripts/drug_info_sync/` 참고)에서 MySQL로 이전한 테이블.

`food_drug_interaction.py`와 같은 패턴: 원본 수집 파이프라인과 SQLite 산출물은 그대로 두고
(`app/scripts/seed_dur.py`가 읽어감), 저장 형식만 SQLite에서 MySQL로 바꿔 앱이 공유 DB에서
조회하도록 한다.

이전에는 `DurScreeningRepository`(`app/repositories/dur_repository.py`)와
`DurDrugRepository`(`app/repositories/dur_drug_repository.py`)가 실제로 쓰는 테이블·컬럼만
옮겼으나, CSV/API 원본 컬럼(AGE_BASE/MAX_QTY/MAX_DOSAGE_TERM/FORM_NAME/GRADE 등)이 통째로
빠지는 문제가 있어 SQLite `drugs_full.db`의 24개 원본 테이블 전체를 컬럼까지 1:1로 옮긴다
(`item_ingredient_map`은 `mapping_ingredients.py`가 만드는 파생 테이블이라 예외).

컬럼 타입: ITEM_SEQ/INGR_CODE류 조인·필터 키만 인덱스가 걸리는 `String`이고, 나머지 원문
텍스트(PROHBT_CONTENT/REMARK 등 포함, 신규로 추가하는 컬럼도 전부)는 SQLite 원본이 TEXT라
길이 제한 없는 `Text`로 옮긴다.
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
    open_de: Mapped[str | None] = mapped_column(Text, nullable=True)
    update_de: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurProdMasterList(Base):
    """DUR 품목 마스터(API: DURPrdlstInfoService03/getDurPrdlstInfoList03) - `DurDrugRepository`의
    이름 검색/조회 기준 품목 마스터(`drugs_data`보다 훨씬 넓은 커버리지)."""

    __tablename__ = "dur_prod_master_list"
    __table_args__ = (Index("ix_dur_prod_master_list_item_name", "item_name", mysql_length=255),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    entp_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    bar_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ee_doc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ud_doc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    nb_doc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    insert_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_term: Mapped[str | None] = mapped_column(Text, nullable=True)
    reexam_target: Mapped[str | None] = mapped_column(Text, nullable=True)
    reexam_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    pack_unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    edi_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    print_front: Mapped[str | None] = mapped_column(Text, nullable=True)
    print_back: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_front: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_back: Mapped[str | None] = mapped_column(Text, nullable=True)
    leng_long: Mapped[str | None] = mapped_column(Text, nullable=True)
    leng_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    thick: Mapped[str | None] = mapped_column(Text, nullable=True)
    img_regist_ts: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    mark_code_front_anal: Mapped[str | None] = mapped_column(Text, nullable=True)
    mark_code_back_anal: Mapped[str | None] = mapped_column(Text, nullable=True)
    mark_code_front_img: Mapped[str | None] = mapped_column(Text, nullable=True)
    mark_code_back_img: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    mark_code_back: Mapped[str | None] = mapped_column(Text, nullable=True)
    edi_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)
    std_cd: Mapped[str | None] = mapped_column(Text, nullable=True)


class DrugPrdtPrmsnDetail(Base):
    """의약품 제품 허가상세(API: DrugPrdtPrmsnInfoService07) - ATC코드/희귀의약품/마약류 구분."""

    __tablename__ = "drug_prdt_prmsn_detail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    atc_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rare_drug_yn: Mapped[str | None] = mapped_column(String(5), nullable=True)
    narcotic_kind_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnsgn_manuf: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    bar_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ee_doc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ud_doc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    nb_doc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    insert_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_term: Mapped[str | None] = mapped_column(Text, nullable=True)
    reexam_target: Mapped[str | None] = mapped_column(Text, nullable=True)
    reexam_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    pack_unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    edi_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    permit_kind_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    make_material_flag: Mapped[str | None] = mapped_column(Text, nullable=True)
    newdrug_class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    induty_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    gbn_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    ee_doc_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    ud_doc_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    nb_doc_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    pn_doc_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_item_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_ingr_eng: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    rtrvl_cmmnd_dt: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)
    std_cd: Mapped[str | None] = mapped_column(Text, nullable=True)
    mapped_item_seq: Mapped[str | None] = mapped_column(Text, nullable=True)


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


class DrugMaxDosage(Base):
    """1일 최대투여량(API: DayMaxDosgQyByIngdService/getDayMaxDosgQyByIngdInq)."""

    __tablename__ = "drug_max_dosage"
    __table_args__ = (Index("ix_drug_max_dosage_cpnt_cd", "cpnt_cd"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cpnt_cd: Mapped[str | None] = mapped_column(String(20), nullable=True)
    drug_cpnt_kor_nm: Mapped[str | None] = mapped_column(Text, nullable=True)
    drug_cpnt_eng_nm: Mapped[str | None] = mapped_column(Text, nullable=True)
    foml_cd: Mapped[str | None] = mapped_column(Text, nullable=True)
    foml_nm: Mapped[str | None] = mapped_column(Text, nullable=True)
    dosage_route_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    day_max_dosg_qy_unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    day_max_dosg_qy: Mapped[str | None] = mapped_column(Text, nullable=True)


class DrugBundleInfo(Base):
    """묶음(위수탁) 제품 정보(API: DrbBundleInfoService02/getDrbBundleList02)."""

    __tablename__ = "drug_bundle_info"
    __table_args__ = (Index("ix_drug_bundle_info_cnsgn_item_seq", "cnsgn_item_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trust_induty_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_mainingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_qnt_list: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_manuf: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_hira_mainingr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_hira_prduct_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_atc_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_cancel_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnsgn_item_seq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cnsgn_item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnsgn_entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnsgn_manuf: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnsgn_item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnsgn_hira_prduct_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    cnsgn_cancel_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class DrugPrdtPrmsnList(Base):
    """의약품 제품 허가목록(API: DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07)."""

    __tablename__ = "drug_prdt_prmsn_list"
    __table_args__ = (Index("ix_drug_prdt_prmsn_list_item_seq", "item_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    induty: Mapped[str | None] = mapped_column(Text, nullable=True)
    prdlst_stdr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    spclty_pblc: Mapped[str | None] = mapped_column(Text, nullable=True)
    prduct_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    prduct_prmisn_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_ingr_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_ingr_cnt: Mapped[str | None] = mapped_column(Text, nullable=True)
    big_prdt_img_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    permit_kind_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    edi_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)


class DrugPrdtMcpnDetail(Base):
    """의약품 품목 원료(성분) 상세(API: DrugPrdtPrmsnInfoService07/getDrugPrdtMcpnDtlInq07) - 원본
    그대로(`item_ingredient_map`은 이 테이블을 소스로 한 파생 매핑 테이블)."""

    __tablename__ = "drug_prdt_mcpn_detail"
    __table_args__ = (
        Index("ix_drug_prdt_mcpn_detail_item_seq", "item_seq"),
        Index("ix_drug_prdt_mcpn_detail_mtral_code", "mtral_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entrps_prmisn_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    entrps: Mapped[str | None] = mapped_column(Text, nullable=True)
    prduct: Mapped[str | None] = mapped_column(Text, nullable=True)
    mtral_sn: Mapped[str | None] = mapped_column(Text, nullable=True)
    mtral_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mtral_nm: Mapped[str | None] = mapped_column(Text, nullable=True)
    qnt: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingd_unit_cd: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_seq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    main_ingr_eng: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)
    cpnt_ctnt_cont: Mapped[str | None] = mapped_column(Text, nullable=True)
    tamt_seq: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurProdPwnmTaboo(Base):
    """품목기준 임부금기(API: DURPrdlstInfoService03/getPwnmTabooInfoList03)."""

    __tablename__ = "dur_prod_pwnm_taboo"
    __table_args__ = (
        Index("ix_dur_prod_pwnm_taboo_item_seq", "item_seq"),
        Index("ix_dur_prod_pwnm_taboo_ingr_code", "ingr_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurProdOdsnAtent(Base):
    """품목기준 노인주의(API: DURPrdlstInfoService03/getOdsnAtentInfoList03)."""

    __tablename__ = "dur_prod_odsn_atent"
    __table_args__ = (
        Index("ix_dur_prod_odsn_atent_item_seq", "item_seq"),
        Index("ix_dur_prod_odsn_atent_ingr_code", "ingr_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurProdSpcifyAgrdeTaboo(Base):
    """품목기준 특정연령대금기(API: DURPrdlstInfoService03/getSpcifyAgrdeTabooInfoList03)."""

    __tablename__ = "dur_prod_spcify_agrde_taboo"
    __table_args__ = (
        Index("ix_dur_prod_spcify_agrde_taboo_item_seq", "item_seq"),
        Index("ix_dur_prod_spcify_agrde_taboo_ingr_code", "ingr_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurProdMdctnPdAtent(Base):
    """품목기준 투여기간주의(API: DURPrdlstInfoService03/getMdctnPdAtentInfoList03)."""

    __tablename__ = "dur_prod_mdctn_pd_atent"
    __table_args__ = (
        Index("ix_dur_prod_mdctn_pd_atent_item_seq", "item_seq"),
        Index("ix_dur_prod_mdctn_pd_atent_ingr_code", "ingr_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurProdCpctyAtent(Base):
    """품목기준 용량주의(API: DURPrdlstInfoService03/getCpctyAtentInfoList03)."""

    __tablename__ = "dur_prod_cpcty_atent"
    __table_args__ = (
        Index("ix_dur_prod_cpcty_atent_item_seq", "item_seq"),
        Index("ix_dur_prod_cpcty_atent_ingr_code", "ingr_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurProdSeobangPartition(Base):
    """품목기준 분할주의(API: DURPrdlstInfoService03/getSeobangjeongPartitnAtentInfoList03) -
    INGR_CODE 컬럼 자체가 없다(제형 속성이라 성분 무관)."""

    __tablename__ = "dur_prod_seobang_partition"
    __table_args__ = (Index("ix_dur_prod_seobang_partition_item_seq", "item_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_code_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurProdEfcyDplct(Base):
    """품목기준 효능군중복주의(API: DURPrdlstInfoService03/getEfcyDplctInfoList03)."""

    __tablename__ = "dur_prod_efcy_dplct"
    __table_args__ = (
        Index("ix_dur_prod_efcy_dplct_item_seq", "item_seq"),
        Index("ix_dur_prod_efcy_dplct_ingr_code", "ingr_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False)
    item_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    dur_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    effect_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_code_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)
    sers_name: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    dur_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    etc_otc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_dur_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_mix: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_entp_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_form_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_etc_otc_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_class_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_etc_otc_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_main_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_item_permit_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_chart: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_change_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    bizrno: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurPwnmTaboo(Base):
    """성분기준 임부금기(API: DURIrdntInfoService03/getPwnmTabooInfoList02)."""

    __tablename__ = "dur_pwnm_taboo"
    __table_args__ = (Index("ix_dur_pwnm_taboo_ingr_code", "ingr_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingr_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    dur_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    ori_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    grade: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    del_yn: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurOdsnAtent(Base):
    """성분기준 노인주의(API: DURIrdntInfoService03/getOdsnAtentInfoList02)."""

    __tablename__ = "dur_odsn_atent"
    __table_args__ = (Index("ix_dur_odsn_atent_ingr_code", "ingr_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingr_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    dur_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    ori_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    del_yn: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurSpcifyAgrdeTaboo(Base):
    """성분기준 특정연령대금기(API: DURIrdntInfoService03/getSpcifyAgrdeTabooInfoList02)."""

    __tablename__ = "dur_spcify_agrde_taboo"
    __table_args__ = (Index("ix_dur_spcify_agrde_taboo_ingr_code", "ingr_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingr_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    dur_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    ori_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    del_yn: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_base: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurCpctyAtent(Base):
    """성분기준 용량주의(API: DURIrdntInfoService03/getCpctyAtentInfoList02)."""

    __tablename__ = "dur_cpcty_atent"
    __table_args__ = (Index("ix_dur_cpcty_atent_ingr_code", "ingr_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingr_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    dur_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    ori_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_qty: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    del_yn: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurEfcyDplct(Base):
    """성분기준 효능군중복주의(API: DURIrdntInfoService03/getEfcyDplctInfoList02)."""

    __tablename__ = "dur_efcy_dplct"
    __table_args__ = (Index("ix_dur_efcy_dplct_ingr_code", "ingr_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingr_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    dur_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    ori_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    effect_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    del_yn: Mapped[str | None] = mapped_column(Text, nullable=True)
    sers_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class DurMdctnPdAtent(Base):
    """성분기준 투여기간주의(API: DURIrdntInfoService03/getMdctnPdAtentInfoList02)."""

    __tablename__ = "dur_mdctn_pd_atent"
    __table_args__ = (Index("ix_dur_mdctn_pd_atent_ingr_code", "ingr_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingr_code: Mapped[str] = mapped_column(String(20), nullable=False)
    ingr_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prohbt_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    dur_seq: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    ori_ingr: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    form_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_dosage_term: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    del_yn: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    type_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mix: Mapped[str | None] = mapped_column(Text, nullable=True)
    ori: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_: Mapped[str | None] = mapped_column("class", Text, nullable=True)
    mixture_mix_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_ingr_eng_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_mix: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_ori: Mapped[str | None] = mapped_column(Text, nullable=True)
    mixture_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    del_yn: Mapped[str | None] = mapped_column(Text, nullable=True)


# seed_dur.py가 SQLite 원본 테이블명 -> (모델, SQLite 컬럼명 -> 모델 속성명) 매핑에 사용.
ALL_DUR_MODELS: list[type[Base]] = [
    DrugMaster,
    DurProdMasterList,
    DrugIdentification,
    DrugPrdtPrmsnDetail,
    MedicineRecall,
    ItemIngredientMap,
    DrugMaxDosage,
    DrugBundleInfo,
    DrugPrdtPrmsnList,
    DrugPrdtMcpnDetail,
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
