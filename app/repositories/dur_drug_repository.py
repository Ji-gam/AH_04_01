"""
T-LLM-2-dur-repository: `app/database/dur_drug_light.db`(의약품 제품/성분/DUR 규칙 SQLite)
조회를 캡슐화한다. `chat_service.py`가 raw sqlite3 쿼리를 인라인으로 갖고 있던 것을
여기로 옮긴다. `app/apis/v1/medication.py`(다른 스쿼드 소유)의 조회 로직은 건드리지 않는다.

알려진 한계: 이 DB는 경량화 버전이라 효능 데이터 커버리지가 낮다(전체 제품의 일부만
`drugs_einfo`에 데이터 존재). 스테이징 환경에서 풀버전으로 교체 예정이며, 이 리포지토리의
쿼리 자체는 어느 버전이든 동일한 스키마를 가정하므로 교체 시 코드 변경이 필요 없다.

T-LLM-2-drug-gateway: `drug_data()`는 위 SQLite 조회 위에 MySQL 캐시 → 외부 e약은요 API
폴백을 더한 단일 파사드다. 각 단계에서 핵심 필드(효능/용법/주의사항/부작용)가 비어 있으면
다음 단계로 넘어가 그 필드만 채우고(병합), SQLite 전용 필드(성분/DUR규칙/최대투여량/식별
정보/리콜 — API에는 없음)는 항상 보존한다. API가 실제 내용을 채운 경우에만 MySQL 캐시에
write-back한다(빈 응답을 캐싱하면 나중에 API에 데이터가 채워져도 영영 못 찾으므로).
"""

import asyncio
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drug_data_cache_model import DrugDataCache
from app.services import drug_public_api_client

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "dur_drug_light.db")


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
    """`base`(SQLite)의 빈 필드만 `enrich`(캐시/API)로 채운다. `base`에만 있는 구조화 필드
    (성분/DUR규칙/최대투여량/식별정보/리콜)는 항상 보존한다. 이름이 일치하지 않는 `enrich`
    항목(SQLite가 못 찾은 제품)은 새 항목으로 추가한다."""
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
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or DB_PATH

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def find_drug_info(self, item_name: str) -> list[DrugProfile]:
        """제품명 부분 일치로 검색해, 매칭된 제품마다 관련 데이터를 모두 모아 반환한다."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT item_seq, item_name, entp_name FROM products WHERE item_name LIKE ?",
                (f"%{item_name}%",),
            )
            return [
                self._build_profile(cursor, item_seq, name, entp_name)
                for item_seq, name, entp_name in cursor.fetchall()
            ]
        finally:
            conn.close()

    def _build_profile(self, cursor: sqlite3.Cursor, item_seq: str, item_name: str, entp_name: str) -> DrugProfile:
        cursor.execute(
            """
            SELECT i.ingr_kor_name FROM product_ingredients pi
            JOIN ingredients i ON pi.ingr_code = i.ingr_code
            WHERE pi.item_seq = ?
            """,
            (item_seq,),
        )
        ingredients = [row[0] for row in cursor.fetchall()]

        cursor.execute(
            "SELECT efcy_qesitm, use_method_qesitm, atpn_qesitm, se_qesitm FROM drugs_einfo WHERE item_seq = ?",
            (item_seq,),
        )
        einfo_row = cursor.fetchone()
        efficacy, usage_method, precautions, side_effects = einfo_row if einfo_row else (None, None, None, None)

        cursor.execute(
            "SELECT chart, form_name, color_class1, color_class2, drug_image_url "
            "FROM product_identifications WHERE item_seq = ?",
            (item_seq,),
        )
        ident_row = cursor.fetchone()
        identification = (
            {
                "chart": ident_row[0],
                "form_name": ident_row[1],
                "color_class1": ident_row[2],
                "color_class2": ident_row[3],
                "drug_image_url": ident_row[4],
            }
            if ident_row
            else None
        )

        cursor.execute("SELECT rtrvl_resn, recall_command_date FROM product_recalls WHERE item_seq = ?", (item_seq,))
        recalls = [{"reason": r[0], "recall_date": r[1]} for r in cursor.fetchall()]

        cursor.execute(
            "SELECT rule_type, ingr_name, prohbt_content, max_dosage, max_term "
            "FROM dur_product_rules WHERE item_seq = ?",
            (item_seq,),
        )
        dur_rules = [
            {"rule_type": r[0], "ingr_name": r[1], "prohbt_content": r[2], "max_dosage": r[3], "max_term": r[4]}
            for r in cursor.fetchall()
        ]

        cursor.execute(
            """
            SELECT DISTINCT dm.cpnt_name, dm.day_max_dosg_qy, dm.day_max_dosg_qy_unit
            FROM product_ingredients pi
            JOIN ingredient_mappings im ON pi.ingr_code = im.ingr_code
            JOIN drug_max_dosages dm ON im.cpnt_code = dm.cpnt_code
            WHERE pi.item_seq = ?
            """,
            (item_seq,),
        )
        max_dosages = [{"name": r[0], "max_qty": r[1], "unit": r[2]} for r in cursor.fetchall()]

        return DrugProfile(
            item_seq=item_seq,
            item_name=item_name,
            entp_name=entp_name,
            ingredients=ingredients,
            efficacy=efficacy,
            usage_method=usage_method,
            precautions=precautions,
            side_effects=side_effects,
            max_dosages=max_dosages,
            identification=identification,
            recalls=recalls,
            dur_rules=dur_rules,
        )

    def find_dur_warnings(self, item_name: str, *, pregnant: bool, geriatric: bool) -> list[str]:
        """임부(PWNM)/노인(ODSN) 주의 경고 문구만 필요한 좁은 조회(chat_service 용도)."""
        if not (pregnant or geriatric):
            return []

        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.item_name, r.rule_type, r.prohbt_content
                FROM dur_product_rules r
                JOIN products p ON r.item_seq = p.item_seq
                WHERE (p.item_name LIKE ? OR ? LIKE '%' || p.item_name || '%')
                  AND (
                      (r.rule_type = 'PWNM' AND ? = 1)
                      OR (r.rule_type = 'ODSN' AND ? = 1)
                  )
                """,
                (f"%{item_name}%", item_name, 1 if pregnant else 0, 1 if geriatric else 0),
            )
            warnings = []
            for matched_name, rule_type, content in cursor.fetchall():
                prefix = "[임부금기 경고]" if rule_type == "PWNM" else "[노인주의 경고]"
                warnings.append(f"{prefix} {matched_name}: {content}")
            return list(set(warnings))
        except sqlite3.Error:
            return []
        finally:
            conn.close()

    async def drug_data(self, session: AsyncSession, item_name: str) -> DrugDataResult:
        """`request(약품명) -> response(약품 상세 + 주의 정보)` 단일 파사드.
        SQLite → MySQL 캐시(쿼리 문자열 정확매치) → 외부 e약은요 API 순으로 캐스케이드하며,
        각 단계는 이전 단계가 채우지 못한 필드만 보완한다."""
        query_name = item_name.strip()

        sqlite_profiles = await asyncio.to_thread(self.find_drug_info, query_name)
        if sqlite_profiles and _any_has_content(sqlite_profiles):
            return DrugDataResult(profiles=sqlite_profiles, provenance=DrugDataProvenance.SQLITE)

        cached = await self._get_cached(session, query_name)
        if cached is not None:
            cached_profiles = [DrugProfile(**p) for p in cached.profiles]
            merged = _merge_profiles(sqlite_profiles, cached_profiles)
            return DrugDataResult(profiles=merged, provenance=DrugDataProvenance.CACHE)

        api_items = await drug_public_api_client.fetch_drug_summary(query_name)
        api_profiles = [_profile_from_api_item(item) for item in api_items]
        merged = _merge_profiles(sqlite_profiles, api_profiles)

        if _any_has_content(api_profiles):
            await self._write_back(session, query_name, api_profiles)
            return DrugDataResult(profiles=merged, provenance=DrugDataProvenance.API)

        if sqlite_profiles:
            return DrugDataResult(profiles=sqlite_profiles, provenance=DrugDataProvenance.SQLITE)

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
