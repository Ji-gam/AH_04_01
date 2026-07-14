"""T-MED-14: `app/database/drugs_full.db`(우선) / `drug_light.db`(폴백) 조회 전용 리포지토리.

`app/repositories/dur_drug_repository.py`(T-LLM-2, 단일 약품명 조회 + MySQL 캐시/외부 API
폴백 게이트웨이)와는 목적이 다르다 — 이 리포지토리는 여러 약품명을 한 번에(SQL IN) 처리하는
DUR 스크리닝 3단계 API 전용이며, 그 파일은 건드리지 않는다.

DUR 규칙 테이블은 22개 원본 API 테이블 중 "품목 기준(prod, ITEM_SEQ 보유)" 8개와 "성분 기준
(ITEM_SEQ 없이 INGR_CODE만 보유, prod보다 완성도 높음)" 7개로 나뉜다. 1~2단계는 품목 기준
테이블을, 3단계는 성분 기준 테이블을 조회한다 — 품목 기준 데이터가 비어 있어도 성분 기준에는
DUR 이슈가 남아있을 수 있기 때문이다.

3단계의 item_seq -> INGR_CODE 변환(`get_ingredient_codes_for_items`)은 T-MED-14-1에서 추가된
`item_ingredient_map`(파생 테이블, `scripts/drug_info_sync/mapping_ingredients.py` 참고)을
우선 조회하고, 거기 없는 품목만 품목 기준 히트 테이블 역추적으로 폴백한다 — 후자만으로는 품목
기준 규칙이 0건인 약이 3단계에서도 항상 빈 결과였기 때문.
"""

import sqlite3
from typing import Any

# 1단계: 품목(ITEM_SEQ) 기준 단일 약품 DUR 규칙 6종. (테이블명, rule_code, 한글 라벨)
# 순서가 곧 프론트 pill 고정 노출 순서 - dur_simple 응답이 항상 이 순서 6개를 그대로 유지한다.
SINGLE_DRUG_RULE_TABLES: list[tuple[str, str, str]] = [
    ("dur_prod_pwnm_taboo", "PWNM", "임부금기"),
    ("dur_prod_odsn_atent", "ODSN", "노인주의"),
    ("dur_prod_spcify_agrde_taboo", "SPCIFY_AGRDE", "특정연령대금기"),
    ("dur_prod_mdctn_pd_atent", "MDCTN", "투여기간주의"),
    ("dur_prod_seobang_partition", "SEOBANG", "분할주의"),
    ("dur_prod_cpcty_atent", "CPCTY", "용량주의"),
]

# 3단계 성분 코드 역추적에 쓰는 품목 기준 테이블 6종(INGR_CODE 보유). dur_prod_seobang_partition은
# INGR_CODE 컬럼 자체가 없어(제형 속성이라 성분 무관) 제외.
INGREDIENT_SOURCE_TABLES: list[str] = [
    "dur_prod_pwnm_taboo",
    "dur_prod_odsn_atent",
    "dur_prod_spcify_agrde_taboo",
    "dur_prod_mdctn_pd_atent",
    "dur_prod_cpcty_atent",
    "dur_prod_efcy_dplct",
]

# 3단계: 성분(INGR_CODE) 기준 DUR 규칙 테이블. (테이블명, 한글 라벨)
INGREDIENT_RULE_TABLES: list[tuple[str, str]] = [
    ("dur_pwnm_taboo", "임부금기"),
    ("dur_odsn_atent", "노인주의"),
    ("dur_spcify_agrde_taboo", "특정연령대금기"),
    ("dur_cpcty_atent", "용량주의"),
    ("dur_efcy_dplct", "효능군중복주의"),
    ("dur_mdctn_pd_atent", "투여기간주의"),
]


class DurScreeningRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def resolve_item_seqs(self, item_names: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
        """약품명 목록을 itemSeq 등 기본정보로 변환한다. 정확일치 IN 쿼리 1개 + (남은 이름이
        있을 때만) LIKE 쿼리 1개, 최대 2쿼리로 N과 무관하게 끝난다."""
        if not item_names:
            return [], []

        matched: list[dict[str, Any]] = []
        unmatched = list(dict.fromkeys(item_names))

        placeholders = ",".join(["?"] * len(item_names))
        rows = self.conn.execute(
            f"""
            SELECT itemSeq AS item_seq, itemName AS item_name, entpName AS entp_name,
                   efcyQesitm AS efcy_qesitm, useMethodQesitm AS use_method_qesitm,
                   atpnWarnQesitm AS atpn_warn_qesitm, seQesitm AS se_qesitm,
                   depositMethodQesitm AS deposit_method_qesitm, itemImage AS item_image
            FROM drugs_data
            WHERE itemName IN ({placeholders})
            """,
            item_names,
        ).fetchall()

        for row in rows:
            matched.append(dict(row))
            if row["item_name"] in unmatched:
                unmatched.remove(row["item_name"])

        if unmatched:
            like_placeholders = " OR ".join(["itemName LIKE ?"] * len(unmatched))
            like_params = [f"%{name}%" for name in unmatched]
            like_rows = self.conn.execute(
                f"""
                SELECT itemSeq AS item_seq, itemName AS item_name, entpName AS entp_name,
                       efcyQesitm AS efcy_qesitm, useMethodQesitm AS use_method_qesitm,
                       atpnWarnQesitm AS atpn_warn_qesitm, seQesitm AS se_qesitm,
                       depositMethodQesitm AS deposit_method_qesitm, itemImage AS item_image
                FROM drugs_data
                WHERE {like_placeholders}
                """,
                like_params,
            ).fetchall()

            for row in like_rows:
                for name in list(unmatched):
                    if name in row["item_name"]:
                        matched.append(dict(row))
                        unmatched.remove(name)
                        break

        return matched, unmatched

    def get_single_drug_rules(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """1단계: 단일 약품의 품목 기준 DUR 규칙(임부/노인/특정연령/장복/분할/용량) 6종 조회."""
        if not item_seqs:
            return []

        placeholders = ",".join(["?"] * len(item_seqs))
        union_query = " UNION ALL ".join(
            f"""
            SELECT ITEM_SEQ AS item_seq, '{code}' AS rule_code, '{label}' AS rule_type,
                   PROHBT_CONTENT AS prohbt_content, REMARK AS remark
            FROM {table}
            WHERE ITEM_SEQ IN ({placeholders})
            """
            for table, code, label in SINGLE_DRUG_RULE_TABLES
        )
        params = item_seqs * len(SINGLE_DRUG_RULE_TABLES)
        rows = self.conn.execute(union_query, params).fetchall()
        return [dict(row) for row in rows]

    def get_interactions_within_set(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """2단계: 입력 약품 집합 내부의 병용금기(USJNT) 상호작용만 조회 (양쪽 다 입력 집합으로
        제한하여 34만 행 테이블 전체가 아니라 해당 페어만 끌어온다)."""
        if not item_seqs or len(item_seqs) < 2:
            return []

        placeholders = ",".join(["?"] * len(item_seqs))
        rows = self.conn.execute(
            f"""
            SELECT ITEM_SEQ AS item_seq, ITEM_NAME AS item_name,
                   MIXTURE_ITEM_SEQ AS mixture_item_seq, MIXTURE_ITEM_NAME AS mixture_item_name,
                   PROHBT_CONTENT AS prohbt_content, REMARK AS remark
            FROM dur_prod_usjnt_taboo
            WHERE ITEM_SEQ IN ({placeholders}) AND MIXTURE_ITEM_SEQ IN ({placeholders})
            """,
            item_seqs + item_seqs,
        ).fetchall()
        return [dict(row) for row in rows]

    def get_efficacy_groups(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """2단계: 효능군중복(EFCY) 데이터 조회."""
        if not item_seqs:
            return []

        placeholders = ",".join(["?"] * len(item_seqs))
        rows = self.conn.execute(
            f"""
            SELECT ITEM_SEQ AS item_seq, ITEM_NAME AS item_name, INGR_CODE AS ingr_code,
                   INGR_NAME AS ingr_name, PROHBT_CONTENT AS prohbt_content, REMARK AS remark
            FROM dur_prod_efcy_dplct
            WHERE ITEM_SEQ IN ({placeholders})
            """,
            item_seqs,
        ).fetchall()
        return [dict(row) for row in rows]

    def get_recalls(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """2단계: 리콜(회수) 정보 조회."""
        if not item_seqs:
            return []

        placeholders = ",".join(["?"] * len(item_seqs))
        rows = self.conn.execute(
            f"""
            SELECT ITEM_SEQ AS item_seq, PRDUCT AS item_name, ENTRPS AS entp_name,
                   RTRVL_RESN AS recall_reason, RECALL_COMMAND_DATE AS recall_command_date,
                   ENFRC_YN AS enforced_yn
            FROM medicine_recalls
            WHERE ITEM_SEQ IN ({placeholders})
            """,
            item_seqs,
        ).fetchall()
        return [dict(row) for row in rows]

    def get_drug_identification(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """1단계: 알약 외형 식별 정보(모양/색상/마크) + 전문·일반 구분/제형 조회."""
        if not item_seqs:
            return []

        placeholders = ",".join(["?"] * len(item_seqs))
        rows = self.conn.execute(
            f"""
            SELECT ITEM_SEQ AS item_seq, DRUG_SHAPE AS shape, COLOR_CLASS1 AS color,
                   MARK_CODE_FRONT AS mark, ETC_OTC_NAME AS etc_otc_name, FORM_CODE_NAME AS form_name
            FROM drug_identification
            WHERE ITEM_SEQ IN ({placeholders})
            """,
            item_seqs,
        ).fetchall()
        return [dict(row) for row in rows]

    def get_ingredient_codes_for_items(self, item_seqs: list[str]) -> dict[str, set[tuple[str, str]]]:
        """3단계 준비: 입력 약품들의 성분 코드를 알아낸다. item_ingredient_map(T-MED-14-1, 품목 마스터의
        MATERIAL_NAME을 성분명 사전과 매칭해 만든 파생 테이블)을 우선 조회하고, 거기 없는 품목만 기존
        품목 기준 DUR 히트 테이블 역추적으로 폴백한다 - 커버리지만 늘어나고 회귀는 없다.
        1개(전부 직접 테이블에서 해결) 또는 2개(폴백 필요) 쿼리로 처리."""
        if not item_seqs:
            return {}

        result: dict[str, set[tuple[str, str]]] = {seq: set() for seq in item_seqs}
        placeholders = ",".join(["?"] * len(item_seqs))

        direct_rows = self.conn.execute(
            f"""
            SELECT ITEM_SEQ AS item_seq, INGR_CODE AS ingr_code, INGR_NAME AS ingr_name
            FROM item_ingredient_map
            WHERE ITEM_SEQ IN ({placeholders})
            """,
            item_seqs,
        ).fetchall()
        for row in direct_rows:
            if row["ingr_code"]:
                result[row["item_seq"]].add((row["ingr_code"], row["ingr_name"] or ""))

        item_seqs = [seq for seq in item_seqs if not result[seq]]
        if not item_seqs:
            return result

        placeholders = ",".join(["?"] * len(item_seqs))
        branches = [
            f"""
            SELECT ITEM_SEQ AS item_seq, INGR_CODE AS ingr_code, INGR_NAME AS ingr_name
            FROM {table}
            WHERE ITEM_SEQ IN ({placeholders})
            """
            for table in INGREDIENT_SOURCE_TABLES
        ]
        branches.append(
            f"""
            SELECT ITEM_SEQ AS item_seq, INGR_CODE AS ingr_code, INGR_KOR_NAME AS ingr_name
            FROM dur_prod_usjnt_taboo
            WHERE ITEM_SEQ IN ({placeholders})
            """
        )
        branches.append(
            f"""
            SELECT MIXTURE_ITEM_SEQ AS item_seq, MIXTURE_INGR_CODE AS ingr_code,
                   MIXTURE_INGR_KOR_NAME AS ingr_name
            FROM dur_prod_usjnt_taboo
            WHERE MIXTURE_ITEM_SEQ IN ({placeholders})
            """
        )
        union_query = " UNION ALL ".join(branches)
        params = item_seqs * (len(INGREDIENT_SOURCE_TABLES) + 2)
        rows = self.conn.execute(union_query, params).fetchall()

        for row in rows:
            ingr_code = row["ingr_code"]
            if not ingr_code:
                continue
            result[row["item_seq"]].add((ingr_code, row["ingr_name"] or ""))
        return result

    def get_ingredient_level_rules(self, ingr_codes: list[str]) -> list[dict[str, Any]]:
        """3단계: 성분(INGR_CODE) 기준 DUR 규칙 조회. 품목 기준 테이블의 모태가 되는 데이터라
        완성도가 더 높다 — 품목 기준에서 놓친 규칙이 여기서 잡힐 수 있다. 1개 쿼리로 처리."""
        if not ingr_codes:
            return []

        placeholders = ",".join(["?"] * len(ingr_codes))
        branches = [
            f"""
            SELECT INGR_CODE AS ingr_code, INGR_NAME AS ingr_name, '{label}' AS rule_type,
                   PROHBT_CONTENT AS prohbt_content, REMARK AS remark
            FROM {table}
            WHERE INGR_CODE IN ({placeholders})
            """
            for table, label in INGREDIENT_RULE_TABLES
        ]
        branches.append(
            f"""
            SELECT INGR_CODE AS ingr_code, INGR_KOR_NAME AS ingr_name, '병용금기' AS rule_type,
                   PROHBT_CONTENT AS prohbt_content, REMARK AS remark
            FROM dur_usjnt_taboo
            WHERE INGR_CODE IN ({placeholders})
            """
        )
        branches.append(
            f"""
            SELECT MIXTURE_INGR_CODE AS ingr_code, MIXTURE_INGR_KOR_NAME AS ingr_name, '병용금기' AS rule_type,
                   PROHBT_CONTENT AS prohbt_content, REMARK AS remark
            FROM dur_usjnt_taboo
            WHERE MIXTURE_INGR_CODE IN ({placeholders})
            """
        )
        union_query = " UNION ALL ".join(branches)
        params = ingr_codes * (len(INGREDIENT_RULE_TABLES) + 2)
        rows = self.conn.execute(union_query, params).fetchall()
        return [dict(row) for row in rows]
