"""T-MED-14: `app/models/dur.py`(MySQL, `app/scripts/seed_dur.py`가 `app/database/drugs_full.db`
SQLite에서 이전) 조회 전용 리포지토리.

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

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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

# 3단계 성분 코드 역추적에 쓰는 품목 기준 테이블 6종(ingr_code 보유). dur_prod_seobang_partition은
# ingr_code 컬럼 자체가 없어(제형 속성이라 성분 무관) 제외.
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


def _in_placeholders(prefix: str, count: int) -> str:
    """":p0, :p1, ..." 형태의 named placeholder 목록 문자열을 만든다."""
    return ", ".join(f":{prefix}{i}" for i in range(count))


def _bind(values: list[str], prefix: str) -> dict[str, Any]:
    return {f"{prefix}{i}": v for i, v in enumerate(values)}


class DurScreeningRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve_item_seqs(self, item_names: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
        """약품명 목록을 itemSeq 등 기본정보로 변환한다. 정확일치 IN 쿼리 1개 + (남은 이름이
        있을 때만) LIKE 쿼리 1개, 최대 2쿼리로 N과 무관하게 끝난다."""
        if not item_names:
            return [], []

        matched: list[dict[str, Any]] = []
        unmatched = list(dict.fromkeys(item_names))

        placeholders = _in_placeholders("n", len(item_names))
        params = _bind(item_names, "n")
        result = await self.session.execute(
            text(
                f"""
                SELECT item_seq, item_name, entp_name,
                       efcy_qesitm, use_method_qesitm,
                       atpn_warn_qesitm, se_qesitm,
                       deposit_method_qesitm, item_image
                FROM drugs_data
                WHERE item_name IN ({placeholders})
                """
            ),
            params,
        )
        rows = result.mappings().all()

        for row in rows:
            matched.append(dict(row))
            if row["item_name"] in unmatched:
                unmatched.remove(row["item_name"])

        if unmatched:
            like_params = {f"l{i}": f"%{name}%" for i, name in enumerate(unmatched)}
            like_clause = " OR ".join(f"item_name LIKE :{k}" for k in like_params)
            like_result = await self.session.execute(
                text(
                    f"""
                    SELECT item_seq, item_name, entp_name,
                           efcy_qesitm, use_method_qesitm,
                           atpn_warn_qesitm, se_qesitm,
                           deposit_method_qesitm, item_image
                    FROM drugs_data
                    WHERE {like_clause}
                    """
                ),
                like_params,
            )
            for row in like_result.mappings().all():
                for name in list(unmatched):
                    if name in row["item_name"]:
                        matched.append(dict(row))
                        unmatched.remove(name)
                        break

        return matched, unmatched

    async def get_single_drug_rules(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """1단계: 단일 약품의 품목 기준 DUR 규칙(임부/노인/특정연령/장복/분할/용량) 6종 조회."""
        if not item_seqs:
            return []

        placeholders = _in_placeholders("s", len(item_seqs))
        params = _bind(item_seqs, "s")
        union_query = " UNION ALL ".join(
            f"""
            SELECT item_seq, '{code}' AS rule_code, '{label}' AS rule_type,
                   prohbt_content, remark
            FROM {table}
            WHERE item_seq IN ({placeholders})
            """
            for table, code, label in SINGLE_DRUG_RULE_TABLES
        )
        result = await self.session.execute(text(union_query), params)
        return [dict(row) for row in result.mappings().all()]

    async def get_interactions_within_set(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """2단계: 입력 약품 집합 내부의 병용금기(USJNT) 상호작용만 조회 (양쪽 다 입력 집합으로
        제한하여 80만 행 테이블 전체가 아니라 해당 페어만 끌어온다)."""
        if not item_seqs or len(item_seqs) < 2:
            return []

        placeholders = _in_placeholders("s", len(item_seqs))
        params = _bind(item_seqs, "s")
        result = await self.session.execute(
            text(
                f"""
                SELECT item_seq, item_name,
                       mixture_item_seq, mixture_item_name,
                       prohbt_content, remark
                FROM dur_prod_usjnt_taboo
                WHERE item_seq IN ({placeholders}) AND mixture_item_seq IN ({placeholders})
                """
            ),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_efficacy_groups(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """2단계: 효능군중복(EFCY) 데이터 조회."""
        if not item_seqs:
            return []

        placeholders = _in_placeholders("s", len(item_seqs))
        params = _bind(item_seqs, "s")
        result = await self.session.execute(
            text(
                f"""
                SELECT item_seq, item_name, ingr_code, ingr_name, prohbt_content, remark
                FROM dur_prod_efcy_dplct
                WHERE item_seq IN ({placeholders})
                """
            ),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_recalls(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """2단계: 리콜(회수) 정보 조회."""
        if not item_seqs:
            return []

        placeholders = _in_placeholders("s", len(item_seqs))
        params = _bind(item_seqs, "s")
        result = await self.session.execute(
            text(
                f"""
                SELECT item_seq, prduct AS item_name, entrps AS entp_name,
                       rtrvl_resn AS recall_reason, recall_command_date,
                       enfrc_yn AS enforced_yn
                FROM medicine_recalls
                WHERE item_seq IN ({placeholders})
                """
            ),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_drug_identification(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """1단계: 알약 외형 식별 정보(모양/색상/마크) + 전문·일반 구분/제형 조회."""
        if not item_seqs:
            return []

        placeholders = _in_placeholders("s", len(item_seqs))
        params = _bind(item_seqs, "s")
        result = await self.session.execute(
            text(
                f"""
                SELECT item_seq, drug_shape AS shape, color_class1 AS color,
                       mark_code_front AS mark, etc_otc_name, form_code_name AS form_name
                FROM drug_identification
                WHERE item_seq IN ({placeholders})
                """
            ),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_drug_safety_info(self, item_seqs: list[str]) -> list[dict[str, Any]]:
        """T-MED-14-1 후속: ATC 분류코드/희귀의약품 여부/마약류 구분을 drug_prdt_prmsn_detail에서
        조회한다(DrugPrdtPrmsnInfoService07, item_seq 기준). 1개 쿼리로 처리."""
        if not item_seqs:
            return []

        placeholders = _in_placeholders("s", len(item_seqs))
        params = _bind(item_seqs, "s")
        result = await self.session.execute(
            text(
                f"""
                SELECT item_seq, atc_code, rare_drug_yn,
                       narcotic_kind_code AS narcotic_kind_name
                FROM drug_prdt_prmsn_detail
                WHERE item_seq IN ({placeholders})
                """
            ),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    async def get_ingredient_codes_for_items(
        self, item_seqs: list[str]
    ) -> dict[str, set[tuple[str, str, str | None, str | None]]]:
        """3단계 준비: 입력 약품들의 성분 코드(+ 이 품목에서의 실제 함량/단위)를 알아낸다.
        item_ingredient_map(T-MED-14-1, drug_prdt_mcpn_detail 코드매칭 우선 + MATERIAL_NAME 텍스트
        매칭 폴백으로 만든 파생 테이블)을 우선 조회하고, 거기 없는 품목만 기존 품목 기준 DUR 히트
        테이블 역추적으로 폴백한다 - 커버리지만 늘어나고 회귀는 없다. 폴백 소스는 함량 정보가 없어
        qnt/unit이 항상 None. 1개(전부 직접 테이블에서 해결) 또는 2개(폴백 필요) 쿼리로 처리."""
        if not item_seqs:
            return {}

        result: dict[str, set[tuple[str, str, str | None, str | None]]] = {seq: set() for seq in item_seqs}
        placeholders = _in_placeholders("s", len(item_seqs))
        params = _bind(item_seqs, "s")

        direct_result = await self.session.execute(
            text(
                f"""
                SELECT item_seq, ingr_code, ingr_name, qnt, ingd_unit_cd AS unit
                FROM item_ingredient_map
                WHERE item_seq IN ({placeholders})
                """
            ),
            params,
        )
        for row in direct_result.mappings().all():
            if row["ingr_code"]:
                result[row["item_seq"]].add((row["ingr_code"], row["ingr_name"] or "", row["qnt"], row["unit"]))

        item_seqs = [seq for seq in item_seqs if not result[seq]]
        if not item_seqs:
            return result

        placeholders = _in_placeholders("s", len(item_seqs))
        params = _bind(item_seqs, "s")
        branches = [
            f"""
            SELECT item_seq, ingr_code, ingr_name
            FROM {table}
            WHERE item_seq IN ({placeholders})
            """
            for table in INGREDIENT_SOURCE_TABLES
        ]
        branches.append(
            f"""
            SELECT item_seq, ingr_code, ingr_kor_name AS ingr_name
            FROM dur_prod_usjnt_taboo
            WHERE item_seq IN ({placeholders})
            """
        )
        branches.append(
            f"""
            SELECT mixture_item_seq AS item_seq, mixture_ingr_code AS ingr_code,
                   mixture_ingr_kor_name AS ingr_name
            FROM dur_prod_usjnt_taboo
            WHERE mixture_item_seq IN ({placeholders})
            """
        )
        union_query = " UNION ALL ".join(branches)
        result_rows = await self.session.execute(text(union_query), params)

        for row in result_rows.mappings().all():
            ingr_code = row["ingr_code"]
            if not ingr_code:
                continue
            result[row["item_seq"]].add((ingr_code, row["ingr_name"] or "", None, None))
        return result

    async def get_ingredient_level_rules(self, ingr_codes: list[str]) -> list[dict[str, Any]]:
        """3단계: 성분(INGR_CODE) 기준 DUR 규칙 조회. 품목 기준 테이블의 모태가 되는 데이터라
        완성도가 더 높다 — 품목 기준에서 놓친 규칙이 여기서 잡힐 수 있다. 1개 쿼리로 처리."""
        if not ingr_codes:
            return []

        placeholders = _in_placeholders("c", len(ingr_codes))
        params = _bind(ingr_codes, "c")
        branches = [
            f"""
            SELECT ingr_code, ingr_name, '{label}' AS rule_type, prohbt_content, remark
            FROM {table}
            WHERE ingr_code IN ({placeholders})
            """
            for table, label in INGREDIENT_RULE_TABLES
        ]
        branches.append(
            f"""
            SELECT ingr_code, ingr_kor_name AS ingr_name, '병용금기' AS rule_type, prohbt_content, remark
            FROM dur_usjnt_taboo
            WHERE ingr_code IN ({placeholders})
            """
        )
        branches.append(
            f"""
            SELECT mixture_ingr_code AS ingr_code, mixture_ingr_kor_name AS ingr_name,
                   '병용금기' AS rule_type, prohbt_content, remark
            FROM dur_usjnt_taboo
            WHERE mixture_ingr_code IN ({placeholders})
            """
        )
        union_query = " UNION ALL ".join(branches)
        result = await self.session.execute(text(union_query), params)
        return [dict(row) for row in result.mappings().all()]
