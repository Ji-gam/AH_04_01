"""
T-LLM-2-dur-repository: `app/database/dur_drug_light.db`(의약품 제품/성분/DUR 규칙 SQLite)
조회를 캡슐화한다. `chat_service.py`가 raw sqlite3 쿼리를 인라인으로 갖고 있던 것을
여기로 옮긴다. `app/apis/v1/medication.py`(다른 스쿼드 소유)의 조회 로직은 건드리지 않는다.

알려진 한계: 이 DB는 경량화 버전이라 효능 데이터 커버리지가 낮다(전체 제품의 일부만
`drugs_einfo`에 데이터 존재). 스테이징 환경에서 풀버전으로 교체 예정이며, 이 리포지토리의
쿼리 자체는 어느 버전이든 동일한 스키마를 가정하므로 교체 시 코드 변경이 필요 없다.
"""

import os
import sqlite3
from dataclasses import dataclass, field

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
            return [self._build_profile(cursor, item_seq, name, entp_name) for item_seq, name, entp_name in cursor.fetchall()]
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
