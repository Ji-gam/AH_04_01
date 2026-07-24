"""
T-LLM-2-dur-repository: `app/models/dur.py`(MySQL, `app/scripts/seed_dur.py`가 `app/database/
drugs_full.db` SQLite - 공공데이터포털 API 22종 전수 수집본 - 에서 이전) 조회를 캡슐화한다.
과거에는 경량화 SQLite(`dur_drug_light.db`, 효능 데이터 커버리지 17%뿐)를 직접 읽었으나, 전수
데이터를 MySQL로 옮기면서 이 리포지토리도 MySQL 조회로 전환했다.

알려진 한계: 1일 최대투여량(`max_dosages`)은 원본이 성분코드(INGR_CODE)가 아니라 별도 코드체계
(CPNT_CD)를 쓰고, 그 사이를 잇던 매핑(`ingredient_mappings`, 예전 dur_drug_light.db 전용
파생 테이블)이 이번 22종 API 전수 수집 범위 밖이라 재구성할 수 없다 - 이 필드는 항상 빈
리스트를 반환한다.

T-LLM-2-drug-gateway: `drug_data()`는 위 MySQL 조회 위에 캐시(같은 MySQL의 `DrugDataCache`
테이블) → 외부 e약은요 API 폴백을 더한 단일 파사드다. 각 단계에서 핵심 필드(효능/용법/주의사항/
부작용)가 비어 있으면 다음 단계로 넘어가 그 필드만 채우고(병합), 1단계 전용 필드(성분/DUR규칙/
식별정보/리콜 — API에는 없음)는 항상 보존한다. API가 실제 내용을 채운 경우에만 MySQL 캐시에
write-back한다(빈 응답을 캐싱하면 나중에 API에 데이터가 채워져도 영영 못 찾으므로).
"""

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drug_data_cache_model import DrugDataCache
from app.repositories.dur_repository import SINGLE_DRUG_RULE_TABLES
from app.services import drug_public_api_client


@dataclass
class DrugProfile:
    item_seq: str
    item_name: str
    entp_name: str
    ingredients: list[str] = field(default_factory=list)
    efficacy: str | None = None
    usage_method: str | None = None
    precautions: str | None = None
    side_effects: str | None = None
    max_dosages: list[dict] = field(default_factory=list)
    identification: dict | None = None
    recalls: list[dict] = field(default_factory=list)
    dur_rules: list[dict] = field(default_factory=list)


class DrugDataProvenance(StrEnum):
    SQLITE = "sqlite"
    CACHE = "cache"
    API = "api"
    MISS = "miss"


@dataclass
class DrugDataResult:
    profiles: list[DrugProfile]
    provenance: DrugDataProvenance


def _has_content(profile: DrugProfile) -> bool:
    return bool(profile.efficacy or profile.usage_method or profile.precautions or profile.side_effects)


def _any_has_content(profiles: list[DrugProfile]) -> bool:
    return any(_has_content(p) for p in profiles)


def _merge_profiles(base: list[DrugProfile], enrich: list[DrugProfile]) -> list[DrugProfile]:
    """`base`(1단계 MySQL)의 빈 필드만 `enrich`(캐시/API)로 채운다. `base`에만 있는 구조화 필드
    (성분/DUR규칙/최대투여량/식별정보/리콜)는 항상 보존한다. 이름이 일치하지 않는 `enrich`
    항목(1단계가 못 찾은 제품)은 새 항목으로 추가한다."""
    if not base:
        return list(enrich)
    if not enrich:
        return list(base)

    enrich_by_name = {p.item_name.strip().lower(): p for p in enrich}
    matched_keys: set[str] = set()
    merged: list[DrugProfile] = []

    for profile in base:
        key = profile.item_name.strip().lower()
        source = enrich_by_name.get(key)
        if source is None:
            merged.append(profile)
            continue
        matched_keys.add(key)
        merged.append(
            DrugProfile(
                item_seq=profile.item_seq or source.item_seq,
                item_name=profile.item_name,
                entp_name=profile.entp_name or source.entp_name,
                ingredients=profile.ingredients or source.ingredients,
                efficacy=profile.efficacy or source.efficacy,
                usage_method=profile.usage_method or source.usage_method,
                precautions=profile.precautions or source.precautions,
                side_effects=profile.side_effects or source.side_effects,
                max_dosages=profile.max_dosages or source.max_dosages,
                identification=profile.identification or source.identification,
                recalls=profile.recalls or source.recalls,
                dur_rules=profile.dur_rules or source.dur_rules,
            )
        )

    merged.extend(source for key, source in enrich_by_name.items() if key not in matched_keys)
    return merged


@dataclass
class _ProfileExtras:
    """`find_drug_info`가 매칭한 제품 전체를 대상으로 한 번에 모아온 성분/식별정보/리콜/DUR규칙을
    item_seq 기준으로 묶어 보관한다."""

    ingredients_by_seq: dict[str, list[str]]
    identification_by_seq: dict[str, dict]
    recalls_by_seq: dict[str, list[dict]]
    dur_rules_by_seq: dict[str, list[dict]]


def _profile_from_api_item(item: dict) -> DrugProfile:
    precaution_parts = [item.get("atpnQesitm"), item.get("atpnWarnQesitm"), item.get("intrcQesitm")]
    precautions = " ".join(p.strip() for p in precaution_parts if p and p.strip()) or None
    return DrugProfile(
        item_seq=str(item.get("itemSeq") or ""),
        item_name=item.get("itemName") or "",
        entp_name=item.get("entpName") or "",
        efficacy=item.get("efcyQesitm") or None,
        usage_method=item.get("useMethodQesitm") or None,
        precautions=precautions,
        side_effects=item.get("seQesitm") or None,
    )


class DurDrugRepository:
    async def search_item_names(self, session: AsyncSession, item_name: str, limit: int) -> list[tuple[str, str]]:
        """(#108) 이름 부분일치로 (item_seq, item_name)만 가볍게 조회한다. `find_drug_info`는
        성분/DUR규칙 등 여러 조회를 동반해 이름 매칭용으로 쓰기엔 무겁다.

        `dur_prod_master_list`(품목 마스터, 23,417건)를 기준으로 검색한다 - `drugs_data`(e약은요
        API)는 4,758건뿐이라 그것만 쓰면 e약은요에 없는 약이 아예 검색 자체가 안 된다."""
        result = await session.execute(
            text("SELECT item_seq, item_name FROM dur_prod_master_list WHERE item_name LIKE :q LIMIT :limit"),
            {"q": f"%{item_name}%", "limit": limit},
        )
        return [(row.item_seq, row.item_name) for row in result.all()]

    async def search_item_names_by_prefix(
        self, session: AsyncSession, prefix: str, limit: int
    ) -> list[tuple[str, str]]:
        """(#108) 27,000여 개 전체를 매번 스캔하지 않도록, OCR 텍스트 앞 몇 글자를 접두어로
        후보를 좁힌 뒤(인덱스 활용) 그 안에서만 유사도 비교를 하기 위한 조회."""
        result = await session.execute(
            text("SELECT item_seq, item_name FROM dur_prod_master_list WHERE item_name LIKE :q LIMIT :limit"),
            {"q": f"{prefix}%", "limit": limit},
        )
        return [(row.item_seq, row.item_name) for row in result.all()]

    async def get_names_by_item_seqs(self, session: AsyncSession, item_seqs: set[str]) -> dict[str, str]:
        """(T-MED-16) 복약 스케줄 목록 등에서 여러 item_seq를 이름으로 한 번에 변환한다(N+1 방지).
        `dur_prod_master_list`가 커버리지가 가장 넓어(23,417건) 기준으로 쓴다 - `search_item_names`
        와 동일한 이유(모듈 docstring 참고). AUTO_ 더미 등 마스터 데이터에 없는 item_seq는
        결과에서 그냥 빠진다(호출부가 `display_name`으로 보완)."""
        if not item_seqs:
            return {}
        stmt = text("SELECT item_seq, item_name FROM dur_prod_master_list WHERE item_seq IN :seqs").bindparams(
            bindparam("seqs", expanding=True)
        )
        result = await session.execute(stmt, {"seqs": list(item_seqs)})
        return {row.item_seq: row.item_name for row in result.all()}

    async def find_drug_info(self, session: AsyncSession, item_name: str) -> list[DrugProfile]:
        """제품명 부분 일치로 검색해, 매칭된 제품마다 관련 데이터를 모두 모아 반환한다.
        품목 마스터(`dur_prod_master_list`)로 이름을 찾고, 효능/용법 텍스트는 있으면(`drugs_data`,
        e약은요 API 커버리지 4,758건뿐) LEFT JOIN으로 보완한다.

        (#N+1) 매칭된 제품이 여러 건이면(부분일치라 흔함) 예전엔 제품마다 성분/식별정보/리콜/
        DUR규칙 6테이블을 순차 조회해(행당 9회 왕복) 매칭 건수에 비례해 느려졌다. AsyncSession은
        커넥션 하나를 물고 있어 같은 세션에서 쿼리를 동시에(asyncio.gather 등으로) 실행할 수
        없으므로 - 진짜 병렬화 대신 이 4종을 `item_seq IN (...)`으로 한 번에 모아 조회하고
        (`_fetch_profile_extras`), 매칭 건수와 무관하게 항상 고정 9회 왕복으로 끝낸다."""
        result = await session.execute(
            text(
                """
                SELECT m.item_seq, m.item_name, m.entp_name,
                       d.efcy_qesitm, d.use_method_qesitm,
                       d.atpn_qesitm, d.atpn_warn_qesitm, d.intrc_qesitm, d.se_qesitm
                FROM dur_prod_master_list m
                LEFT JOIN drugs_data d ON m.item_seq = d.item_seq
                WHERE m.item_name LIKE :q
                """
            ),
            {"q": f"%{item_name}%"},
        )
        rows = result.mappings().all()
        if not rows:
            return []

        item_seqs = [row["item_seq"] for row in rows]
        extras = await self._fetch_profile_extras(session, item_seqs)
        return [self._assemble_profile(row, extras) for row in rows]

    async def _fetch_profile_extras(self, session: AsyncSession, item_seqs: list[str]) -> "_ProfileExtras":
        """`find_drug_info`가 찾은 제품 전체(item_seqs)를 대상으로 성분/식별정보/리콜/DUR규칙을
        `IN (...)`으로 한 번씩만 조회해 item_seq별로 묶어 돌려준다."""
        seqs_param = {"seqs": item_seqs}

        ingr_result = await session.execute(
            text("SELECT item_seq, ingr_name FROM item_ingredient_map WHERE item_seq IN :seqs").bindparams(
                bindparam("seqs", expanding=True)
            ),
            seqs_param,
        )
        ingredients_by_seq: dict[str, list[str]] = defaultdict(list)
        for row in ingr_result.all():
            if row.ingr_name:
                ingredients_by_seq[row.item_seq].append(row.ingr_name)

        ident_result = await session.execute(
            text(
                "SELECT item_seq, chart, form_code_name, color_class1, color_class2, item_image "
                "FROM drug_identification WHERE item_seq IN :seqs"
            ).bindparams(bindparam("seqs", expanding=True)),
            seqs_param,
        )
        identification_by_seq: dict[str, dict] = {}
        for row in ident_result.all():
            # 원래 코드(.first())와 동일하게 item_seq당 첫 행만 채택한다.
            identification_by_seq.setdefault(
                row.item_seq,
                {
                    "chart": row.chart,
                    "form_name": row.form_code_name,
                    "color_class1": row.color_class1,
                    "color_class2": row.color_class2,
                    "drug_image_url": row.item_image,
                },
            )

        recalls_result = await session.execute(
            text(
                "SELECT item_seq, rtrvl_resn, recall_command_date FROM medicine_recalls WHERE item_seq IN :seqs"
            ).bindparams(bindparam("seqs", expanding=True)),
            seqs_param,
        )
        recalls_by_seq: dict[str, list[dict]] = defaultdict(list)
        for row in recalls_result.all():
            recalls_by_seq[row.item_seq].append({"reason": row.rtrvl_resn, "recall_date": row.recall_command_date})

        dur_rules_by_seq: dict[str, list[dict]] = defaultdict(list)
        for table, _code, label in SINGLE_DRUG_RULE_TABLES:
            # dur_prod_seobang_partition은 ingr_name 컬럼이 없다(제형 속성이라 성분 무관,
            # dur_repository.py의 INGREDIENT_SOURCE_TABLES 주석과 동일 이유).
            ingr_name_col = "NULL" if table == "dur_prod_seobang_partition" else "ingr_name"
            rule_result = await session.execute(
                text(
                    f"SELECT item_seq, {ingr_name_col} AS ingr_name, prohbt_content FROM {table} "
                    "WHERE item_seq IN :seqs"
                ).bindparams(bindparam("seqs", expanding=True)),
                seqs_param,
            )
            for row in rule_result.all():
                dur_rules_by_seq[row.item_seq].append(
                    {
                        "rule_type": label,
                        "ingr_name": row.ingr_name,
                        "prohbt_content": row.prohbt_content,
                        # 1일최대투여량(max_dosage/max_term)은 모듈 docstring에 적은 대로
                        # 성분코드<->CPNT_CD 매핑이 없어 재구성 불가 - 항상 None.
                        "max_dosage": None,
                        "max_term": None,
                    }
                )

        return _ProfileExtras(
            ingredients_by_seq=ingredients_by_seq,
            identification_by_seq=identification_by_seq,
            recalls_by_seq=recalls_by_seq,
            dur_rules_by_seq=dur_rules_by_seq,
        )

    def _assemble_profile(self, row, extras: "_ProfileExtras") -> DrugProfile:
        item_seq = row["item_seq"]
        precaution_parts = [row["atpn_qesitm"], row["atpn_warn_qesitm"], row["intrc_qesitm"]]
        precautions = " ".join(p.strip() for p in precaution_parts if p and p.strip()) or None

        return DrugProfile(
            item_seq=item_seq,
            item_name=row["item_name"],
            entp_name=row["entp_name"] or "",
            ingredients=extras.ingredients_by_seq.get(item_seq, []),
            efficacy=row["efcy_qesitm"] or None,
            usage_method=row["use_method_qesitm"] or None,
            precautions=precautions,
            side_effects=row["se_qesitm"] or None,
            max_dosages=[],
            identification=extras.identification_by_seq.get(item_seq),
            recalls=extras.recalls_by_seq.get(item_seq, []),
            dur_rules=extras.dur_rules_by_seq.get(item_seq, []),
        )

    async def find_food_intrc_text(self, session: AsyncSession, item_name: str) -> str | None:
        """(T-DOC-5) `drugs_data`(e약은요 스냅샷, 4,758건)에서 `intrc_qesitm`만 가볍게 조회한다.
        `find_drug_info`는 성분/DUR규칙 등을 동반 조회해 음식 상호작용 카드 용도로는 무겁다.
        반환값이 None이면 이 약이 `drugs_data`에 아예 없다는 뜻(실시간 e약은요 API 폴백 필요) —
        행은 있는데 텍스트가 비어있는 경우와 구분해야 하므로 빈 문자열("")과 None을 구분해서 돌려준다."""
        result = await session.execute(
            text("SELECT intrc_qesitm FROM drugs_data WHERE item_name LIKE :q LIMIT 1"),
            {"q": f"%{item_name}%"},
        )
        row = result.first()
        if row is None:
            return None
        return row[0] or ""

    async def find_dur_warnings(
        self, session: AsyncSession, item_name: str, *, pregnant: bool, geriatric: bool
    ) -> list[str]:
        """임부(PWNM)/노인(ODSN) 주의 경고 문구만 필요한 좁은 조회(chat_service 용도)."""
        if not (pregnant or geriatric):
            return []

        warnings: list[str] = []
        if pregnant:
            warnings.extend(await self._collect_rule_warnings(session, "dur_prod_pwnm_taboo", item_name, "임부금기"))
        if geriatric:
            warnings.extend(await self._collect_rule_warnings(session, "dur_prod_odsn_atent", item_name, "노인주의"))
        return list(set(warnings))

    async def _collect_rule_warnings(self, session: AsyncSession, table: str, item_name: str, label: str) -> list[str]:
        # {table}(dur_prod_pwnm_taboo/dur_prod_odsn_atent)은 item_seq만 갖고 item_name이
        # 없어(app/models/dur.py) 품목 마스터(dur_prod_master_list)와 조인해야 이름으로 매칭할
        # 수 있다. drugs_data(e약은요, 4,758건)는 커버리지가 좁아 여기 쓰면 안 된다 -
        # find_drug_info/search_item_names와 동일한 이유(모듈 docstring 참고).
        result = await session.execute(
            text(
                f"""
                SELECT m.item_name, r.prohbt_content
                FROM {table} r
                JOIN dur_prod_master_list m ON r.item_seq = m.item_seq
                WHERE m.item_name LIKE :like_q OR :q LIKE CONCAT('%', m.item_name, '%')
                """
            ),
            {"like_q": f"%{item_name}%", "q": item_name},
        )
        return [f"[{label} 경고] {matched_name}: {content}" for matched_name, content in result.all()]

    async def drug_data(self, session: AsyncSession, item_name: str) -> DrugDataResult:
        """`request(약품명) -> response(약품 상세 + 주의 정보)` 단일 파사드.
        MySQL(1단계) → MySQL 캐시(쿼리 문자열 정확매치) → 외부 e약은요 API 순으로 캐스케이드하며,
        각 단계는 이전 단계가 채우지 못한 필드만 보완한다."""
        query_name = item_name.strip()

        base_profiles = await self.find_drug_info(session, query_name)
        if base_profiles and _any_has_content(base_profiles):
            return DrugDataResult(profiles=base_profiles, provenance=DrugDataProvenance.SQLITE)

        cached = await self._get_cached(session, query_name)
        if cached is not None:
            cached_profiles = [DrugProfile(**p) for p in cached.profiles]
            merged = _merge_profiles(base_profiles, cached_profiles)
            return DrugDataResult(profiles=merged, provenance=DrugDataProvenance.CACHE)

        api_items = await drug_public_api_client.fetch_drug_summary(query_name)
        api_profiles = [_profile_from_api_item(item) for item in api_items]
        merged = _merge_profiles(base_profiles, api_profiles)

        if _any_has_content(api_profiles):
            await self._write_back(session, query_name, api_profiles)
            return DrugDataResult(profiles=merged, provenance=DrugDataProvenance.API)

        if base_profiles:
            return DrugDataResult(profiles=base_profiles, provenance=DrugDataProvenance.SQLITE)

        return DrugDataResult(profiles=[], provenance=DrugDataProvenance.MISS)

    async def _get_cached(self, session: AsyncSession, query_name: str) -> DrugDataCache | None:
        result = await session.execute(select(DrugDataCache).where(DrugDataCache.query_name == query_name))
        return result.scalar_one_or_none()

    async def _write_back(self, session: AsyncSession, query_name: str, profiles: list[DrugProfile]) -> None:
        """캐시 쓰기는 best-effort다 — 실패해도 이미 계산된 응답 회신을 막지 않는다."""
        try:
            session.add(DrugDataCache(query_name=query_name, profiles=[asdict(p) for p in profiles]))
            await session.commit()
        except Exception:
            await session.rollback()
