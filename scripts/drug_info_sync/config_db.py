import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

DEFAULT_WORKERS = 8
DB_PATH = "../../app/database/drugs_full.db" # 전역 DB 파일 경로 설정

@dataclass
class APISpec:
    name: str
    base_url: str
    output_filename: str
    db_table: str
    primary_keys: List[str] = field(default_factory=list) # 동적 UNIQUE 제약조건 생성용 진정한 복합키(True PK)
    index_columns: List[str] = field(default_factory=list) # 동적 INDEX 생성용 핵심 검색 컬럼

    extra_params: Dict[str, Any] = field(default_factory=dict)
    xml_item_path: str = ".//item"
    xml_total_count_path: str = ".//totalCount"
    start_page: int = 1
    num_of_rows: int = 500
    is_prescription: bool = False

API_SPECS: Dict[str, APISpec] = {
    "e_drug": APISpec(
        name="e_drug",
        base_url="http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList",
        output_filename="drugs_data",
        db_table="drugs_data",
        primary_keys=["itemSeq", "itemImage"],
        index_columns=["itemSeq", "itemName"]
    ),
    "drug_identification": APISpec(
        name="drug_identification",
        base_url="http://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03/getMdcinGrnIdntfcInfoList03",
        output_filename="drug_identification",
        db_table="drug_identification",
        primary_keys=["ITEM_SEQ", "ITEM_IMAGE"],
        index_columns=["ITEM_SEQ", "ITEM_NAME"]
    ),
    "medicine_recalls": APISpec(
        name="medicine_recalls",
        base_url="https://apis.data.go.kr/1471000/MdcinRtrvlSleStpgeInfoService04/getMdcinRtrvlSleStpgelList03",
        output_filename="medicine_recalls",
        db_table="medicine_recalls",
        primary_keys=["PRDUCT", "ENTRPS", "RTRVL_CMMND_DT", "RECALL_COMMAND_DATE", "RTRVL_RESN"],
        index_columns=["PRDUCT"]
    ),
    "drug_max_dosage": APISpec(
        name="drug_max_dosage",
        base_url="https://apis.data.go.kr/1471000/DayMaxDosgQyByIngdService/getDayMaxDosgQyByIngdInq",
        output_filename="drug_max_dosage",
        db_table="drug_max_dosage",
        primary_keys=["CPNT_CD", "DOSAGE_ROUTE_CODE", "FOML_CD"],
        index_columns=["CPNT_CD"]
    ),
    "drug_bundle_info": APISpec(
        name="drug_bundle_info",
        base_url="https://apis.data.go.kr/1471000/DrbBundleInfoService02/getDrbBundleList02",
        output_filename="drug_bundle_info",
        db_table="drug_bundle_info",
        primary_keys=["cnsgnItemSeq", "trustItemName", "trustIndutyCode"],
        index_columns=["cnsgnItemSeq", "trustItemSeq"]
    ),
    "dur_usjnt_taboo": APISpec(
        name="dur_usjnt_taboo",
        base_url="https://apis.data.go.kr/1471000/DURIrdntInfoService03/getUsjntTabooInfoList02",
        output_filename="dur_usjnt_taboo",
        db_table="dur_usjnt_taboo",
        primary_keys=["INGR_CODE", "MIXTURE_INGR_CODE", "MIXTURE_MIX_TYPE", "MIX_TYPE", "NOTIFICATION_DATE", "MIXTURE_MIX", "MIX", "MIXTURE_CLASS", "DEL_YN", "CLASS", "PROHBT_CONTENT"],
        index_columns=["INGR_CODE"]
    ),
    "dur_spcify_agrde_taboo": APISpec(
        name="dur_spcify_agrde_taboo",
        base_url="https://apis.data.go.kr/1471000/DURIrdntInfoService03/getSpcifyAgrdeTabooInfoList02",
        output_filename="dur_spcify_agrde_taboo",
        db_table="dur_spcify_agrde_taboo",
        primary_keys=["INGR_CODE", "MIX_TYPE", "NOTIFICATION_DATE", "DUR_SEQ"],
        index_columns=["INGR_CODE"]
    ),
    "dur_pwnm_taboo": APISpec(
        name="dur_pwnm_taboo",
        base_url="https://apis.data.go.kr/1471000/DURIrdntInfoService03/getPwnmTabooInfoList02",
        output_filename="dur_pwnm_taboo",
        db_table="dur_pwnm_taboo",
        primary_keys=["INGR_CODE", "MIX_TYPE", "NOTIFICATION_DATE", "DUR_SEQ"],
        index_columns=["INGR_CODE"]
    ),
    "dur_cpcty_atent": APISpec(
        name="dur_cpcty_atent",
        base_url="https://apis.data.go.kr/1471000/DURIrdntInfoService03/getCpctyAtentInfoList02",
        output_filename="dur_cpcty_atent",
        db_table="dur_cpcty_atent",
        primary_keys=["INGR_CODE", "MIX_TYPE", "NOTIFICATION_DATE", "DUR_SEQ"],
        index_columns=["INGR_CODE"]
    ),
    "dur_mdctn_pd_atent": APISpec(
        name="dur_mdctn_pd_atent",
        base_url="https://apis.data.go.kr/1471000/DURIrdntInfoService03/getMdctnPdAtentInfoList02",
        output_filename="dur_mdctn_pd_atent",
        db_table="dur_mdctn_pd_atent",
        primary_keys=["INGR_CODE", "MIX_TYPE", "NOTIFICATION_DATE", "DUR_SEQ"],
        index_columns=["INGR_CODE"]
    ),
    "dur_odsn_atent": APISpec(
        name="dur_odsn_atent",
        base_url="https://apis.data.go.kr/1471000/DURIrdntInfoService03/getOdsnAtentInfoList02",
        output_filename="dur_odsn_atent",
        db_table="dur_odsn_atent",
        primary_keys=["INGR_CODE", "MIX_TYPE", "DUR_SEQ"],
        index_columns=["INGR_CODE"]
    ),
    "dur_efcy_dplct": APISpec(
        name="dur_efcy_dplct",
        base_url="https://apis.data.go.kr/1471000/DURIrdntInfoService03/getEfcyDplctInfoList02",
        output_filename="dur_efcy_dplct",
        db_table="dur_efcy_dplct",
        primary_keys=["INGR_CODE", "NOTIFICATION_DATE", "DUR_SEQ"],
        index_columns=["INGR_CODE"]
    ),
    "dur_prod_usjnt_taboo": APISpec(
        name="dur_prod_usjnt_taboo",
        base_url="https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getUsjntTabooInfoList03",
        output_filename="dur_prod_usjnt_taboo",
        db_table="dur_prod_usjnt_taboo",
        primary_keys=["ITEM_SEQ", "MIXTURE_ITEM_SEQ", "MIXTURE_CHANGE_DATE", "MIXTURE_DUR_SEQ", "MIXTURE_INGR_KOR_NAME", "INGR_KOR_NAME"],
        index_columns=["ITEM_SEQ"]
    ),
    "dur_prod_odsn_atent": APISpec(
        name="dur_prod_odsn_atent",
        base_url="https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getOdsnAtentInfoList03",
        output_filename="dur_prod_odsn_atent",
        db_table="dur_prod_odsn_atent",
        primary_keys=["ITEM_SEQ", "INGR_CODE"],
        index_columns=["ITEM_SEQ", "INGR_CODE"]
    ),
    "dur_prod_master_list": APISpec(
        name="dur_prod_master_list",
        base_url="https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getDurPrdlstInfoList03",
        output_filename="dur_prod_master_list",
        db_table="dur_prod_master_list",
        primary_keys=["ITEM_SEQ"],
        index_columns=["ITEM_SEQ"]
    ),
    "dur_prod_spcify_agrde_taboo": APISpec(
        name="dur_prod_spcify_agrde_taboo",
        base_url="https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getSpcifyAgrdeTabooInfoList03",
        output_filename="dur_prod_spcify_agrde_taboo",
        db_table="dur_prod_spcify_agrde_taboo",
        primary_keys=["ITEM_SEQ", "INGR_CODE", "NOTIFICATION_DATE", "PROHBT_CONTENT"],
        index_columns=["ITEM_SEQ", "INGR_CODE"]
    ),
    "dur_prod_cpcty_atent": APISpec(
        name="dur_prod_cpcty_atent",
        base_url="https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getCpctyAtentInfoList03",
        output_filename="dur_prod_cpcty_atent",
        db_table="dur_prod_cpcty_atent",
        primary_keys=["ITEM_SEQ", "INGR_CODE", "NOTIFICATION_DATE", "MIX_INGR", "PROHBT_CONTENT"],
        index_columns=["ITEM_SEQ", "INGR_CODE"]
    ),
    "dur_prod_mdctn_pd_atent": APISpec(
        name="dur_prod_mdctn_pd_atent",
        base_url="https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getMdctnPdAtentInfoList03",
        output_filename="dur_prod_mdctn_pd_atent",
        db_table="dur_prod_mdctn_pd_atent",
        primary_keys=["ITEM_SEQ", "INGR_CODE", "NOTIFICATION_DATE", "MIX_INGR"],
        index_columns=["ITEM_SEQ", "INGR_CODE"]
    ),
    "dur_prod_efcy_dplct": APISpec(
        name="dur_prod_efcy_dplct",
        base_url="https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getEfcyDplctInfoList03",
        output_filename="dur_prod_efcy_dplct",
        db_table="dur_prod_efcy_dplct",
        primary_keys=["ITEM_SEQ", "INGR_CODE", "DUR_SEQ", "INGR_ENG_NAME_FULL"],
        index_columns=["ITEM_SEQ", "INGR_CODE"]
    ),
    "dur_prod_seobang_partition": APISpec(
        name="dur_prod_seobang_partition",
        base_url="https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getSeobangjeongPartitnAtentInfoList03",
        output_filename="dur_prod_seobang_partition",
        db_table="dur_prod_seobang_partition",
        primary_keys=["ITEM_SEQ"],
        index_columns=["ITEM_SEQ"]
    ),
    "dur_prod_pwnm_taboo": APISpec(
        name="dur_prod_pwnm_taboo",
        base_url="https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getPwnmTabooInfoList03",
        output_filename="dur_prod_pwnm_taboo",
        db_table="dur_prod_pwnm_taboo",
        primary_keys=["ITEM_SEQ", "INGR_CODE", "NOTIFICATION_DATE", "MIX_INGR", "REMARK", "PROHBT_CONTENT"],
        index_columns=["ITEM_SEQ", "INGR_CODE"]
    )
}
