import os
import re
import sqlite3

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(CURRENT_DIR, "../../app/database/drugs_full.db")

# 성분명 -> INGR_CODE 사전을 만드는 데 쓰는 성분 기준 DUR 테이블 6종 (ORI_INGR 보유 여부는 테이블마다 다름)
INGREDIENT_NAME_TABLES = [
    "dur_pwnm_taboo",
    "dur_odsn_atent",
    "dur_spcify_agrde_taboo",
    "dur_cpcty_atent",
    "dur_efcy_dplct",
    "dur_mdctn_pd_atent",
]

_ORI_ENTRY_RE = re.compile(r"\[[A-Za-z0-9]+\](.+)")
_ORI_MCODE_RE = re.compile(r"\[([A-Za-z0-9]+)\]")


def _add_synonym(index: dict[str, str], name: str | None, code: str | None) -> None:
    if name and code and name.strip() not in index:
        index[name.strip()] = code


def _add_ori_synonyms(index: dict[str, str], ori_field: str | None, code: str | None) -> None:
    """ORI_INGR/ORI 필드는 '[성분ID]이형태명/[성분ID]이형태명/...' 형식 - 각 이형태명을 동의어로 등록."""
    if not ori_field or not code:
        return
    for part in ori_field.split("/"):
        match = _ORI_ENTRY_RE.match(part.strip())
        if match:
            _add_synonym(index, match.group(1), code)


def build_ingredient_synonym_index(cursor: sqlite3.Cursor) -> dict[str, str]:
    """성분명(정식명 + ORI_INGR 이형태명) -> INGR_CODE 사전을 성분 기준 DUR 테이블 전체에서 구축."""
    index: dict[str, str] = {}

    for table in INGREDIENT_NAME_TABLES:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cursor.fetchall()}
        has_ori = "ORI_INGR" in columns

        select_cols = "INGR_CODE, INGR_NAME" + (", ORI_INGR" if has_ori else "")
        cursor.execute(f"SELECT {select_cols} FROM {table}")
        for row in cursor.fetchall():
            code, name = row[0], row[1]
            _add_synonym(index, name, code)
            if has_ori:
                _add_ori_synonyms(index, row[2], code)

    cursor.execute(
        """
        SELECT INGR_CODE, INGR_KOR_NAME, ORI, MIXTURE_INGR_CODE, MIXTURE_INGR_KOR_NAME, MIXTURE_ORI
        FROM dur_usjnt_taboo
        """
    )
    for code, name, ori, mixture_code, mixture_name, mixture_ori in cursor.fetchall():
        _add_synonym(index, name, code)
        _add_ori_synonyms(index, ori, code)
        _add_synonym(index, mixture_name, mixture_code)
        _add_ori_synonyms(index, mixture_ori, mixture_code)

    return index


def _add_ori_mcodes(index: dict[str, str], ori_field: str | None, code: str | None) -> None:
    """ORI_INGR/ORI 필드('[M082059]이형태명/...')에서 M코드만 뽑아 index[M코드] = INGR_CODE로 등록."""
    if not ori_field or not code:
        return
    for part in ori_field.split("/"):
        match = _ORI_MCODE_RE.match(part.strip())
        if match and match.group(1) not in index:
            index[match.group(1)] = code


def build_mcode_index(cursor: sqlite3.Cursor) -> dict[str, str]:
    """원료성분코드(M코드, 예: 'M082059') -> INGR_CODE(D코드) 사전을 성분 기준 DUR 테이블의
    ORI_INGR/ORI 필드에서 구축한다. 공공데이터포털 DrugPrdtPrmsnInfoService07의
    getDrugPrdtMcpnDtlInq07이 주는 MTRAL_CODE가 같은 네임스페이스라, 이름 유사매칭이 아니라
    코드 대 코드로 정확히 잇는 경로가 된다(T-MED-14-1 후속, 2026-07-14 확인)."""
    index: dict[str, str] = {}

    for table in INGREDIENT_NAME_TABLES:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cursor.fetchall()}
        if "ORI_INGR" not in columns:
            continue
        cursor.execute(f"SELECT INGR_CODE, ORI_INGR FROM {table}")
        for code, ori in cursor.fetchall():
            _add_ori_mcodes(index, ori, code)

    cursor.execute("SELECT INGR_CODE, ORI, MIXTURE_INGR_CODE, MIXTURE_ORI FROM dur_usjnt_taboo")
    for code, ori, mixture_code, mixture_ori in cursor.fetchall():
        _add_ori_mcodes(index, ori, code)
        _add_ori_mcodes(index, mixture_ori, mixture_code)

    return index


def resolve_mcpn_ingredients(
    cursor: sqlite3.Cursor, mcode_index: dict[str, str], name_index: dict[str, str]
) -> list[tuple[str, str, str, str | None, str | None]]:
    """drug_prdt_mcpn_detail(품목당 성분 단위 row)의 MTRAL_CODE를 mcode_index로 우선 조회하고,
    거기 없으면 MTRAL_NM을 name_index로 폴백 조회해 (item_seq, ingr_code, ingr_name, qnt, unit)을
    만든다. QNT/단위는 이 품목에서 실제 이 성분이 몇 밀리그램 들어있는지(DUR 응답 풍부화용)."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='drug_prdt_mcpn_detail'")
    if not cursor.fetchone():
        return []

    cursor.execute("SELECT ITEM_SEQ, MTRAL_CODE, MTRAL_NM, QNT, INGD_UNIT_CD FROM drug_prdt_mcpn_detail")
    rows: list[tuple[str, str, str, str | None, str | None]] = []
    for item_seq, mtral_code, mtral_name, qnt, unit in cursor.fetchall():
        ingr_code = mcode_index.get(mtral_code) if mtral_code else None
        if not ingr_code and mtral_name:
            ingr_code = name_index.get(mtral_name.strip())
        if ingr_code:
            rows.append((item_seq, ingr_code, mtral_name or "", qnt or None, unit or None))
    return rows


def parse_material_ingredients(material_name: str | None) -> list[str]:
    """MATERIAL_NAME(예: '에날라프릴말레산염,,20,밀리그램,USP,/히드로클로로티아지드,,12.5,밀리그램,KP,')을
    '/'로 성분별 분리 후 각 조각의 첫 토큰(순수 성분명)만 추출한다."""
    if not material_name:
        return []

    names = []
    for segment in material_name.split("/"):
        raw_name = segment.split(",")[0].strip()
        if raw_name:
            names.append(raw_name)
    return names


def resolve_material_name_ingredients(
    cursor: sqlite3.Cursor, name_index: dict[str, str]
) -> list[tuple[str, str, str, str | None, str | None]]:
    """dur_prod_master_list.MATERIAL_NAME을 성분명 사전과 매칭한다 (drug_prdt_mcpn_detail이 놓친
    품목을 위한 폴백 소스 - 텍스트 유사매칭이라 정확도는 mcpn 코드매칭보다 낮음). 이 소스는 정량
    정보가 없어 qnt/unit은 항상 None."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dur_prod_master_list'")
    if not cursor.fetchone():
        return []

    cursor.execute("SELECT ITEM_SEQ, MATERIAL_NAME FROM dur_prod_master_list")
    rows: list[tuple[str, str, str, str | None, str | None]] = []
    for item_seq, material_name in cursor.fetchall():
        for ingr_name in parse_material_ingredients(material_name):
            ingr_code = name_index.get(ingr_name)
            if ingr_code:
                rows.append((item_seq, ingr_code, ingr_name, None, None))
    return rows


def build_item_ingredient_map(conn: sqlite3.Connection) -> int:
    """item_ingredient_map을 재생성한다. 100% 파생 데이터라 매 실행마다 통째로 재계산 - 새 DUR
    데이터 반영 시 항상 최신 상태를 보장한다. 두 소스를 합친다:
    1순위 drug_prdt_mcpn_detail(품목당 성분 row, MTRAL_CODE를 M코드->INGR_CODE로 코드 대 코드 매칭,
       안되면 성분명 폴백) - 공공데이터포털 전체 품목을 커버(T-MED-14-1 후속, 2026-07-14).
    2순위 dur_prod_master_list.MATERIAL_NAME 텍스트 매칭 - 1순위가 놓친 품목만 보충.
    두 소스 모두 없는 품목은 여전히 해결 불가(이 22+3개 테이블 어디에도 성분 흔적이 없다는 뜻)."""
    cursor = conn.cursor()

    name_index = build_ingredient_synonym_index(cursor)
    mcode_index = build_mcode_index(cursor)

    rows = resolve_mcpn_ingredients(cursor, mcode_index, name_index)
    rows += resolve_material_name_ingredients(cursor, name_index)

    cursor.execute("DROP TABLE IF EXISTS item_ingredient_map")
    cursor.execute(
        """
        CREATE TABLE item_ingredient_map (
            ITEM_SEQ TEXT,
            INGR_CODE TEXT,
            INGR_NAME TEXT,
            QNT TEXT,
            INGD_UNIT_CD TEXT,
            UNIQUE(ITEM_SEQ, INGR_CODE)
        )
        """
    )
    cursor.execute("CREATE INDEX idx_item_ingredient_map_item_seq ON item_ingredient_map(ITEM_SEQ)")

    cursor.executemany("INSERT OR IGNORE INTO item_ingredient_map VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM item_ingredient_map")
    return cursor.fetchone()[0]


def main():
    print("🚀 품목-성분(item_seq -> INGR_CODE) 매핑 스크립트 가동")

    if not os.path.exists(DB_PATH):
        print(f"❌ DB 파일을 찾을 수 없습니다: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    row_count = build_item_ingredient_map(conn)
    conn.close()

    print(f"🎉 [item_ingredient_map] 매핑 완료! (총 {row_count}건 적재)")


if __name__ == "__main__":
    main()
