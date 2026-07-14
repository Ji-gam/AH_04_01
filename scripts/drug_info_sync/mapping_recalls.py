import os
import re
import sqlite3

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(CURRENT_DIR, "../../app/database/drugs_full.db")


def clean_product_name(name: str) -> str:
    """제품명 매칭률을 높이기 위한 문자열 정제"""
    if not name:
        return ""
    # 1. 괄호와 그 안의 내용 제거 (예: 타이레놀정500밀리그람(아세트아미노펜) -> 타이레놀정500밀리그람)
    name = re.sub(r"\(.*?\)", "", name)
    # 2. 모든 공백 제거
    name = name.replace(" ", "")
    # 3. 영문 소문자화
    return name.lower().strip()


def setup_mapped_columns(cursor: sqlite3.Cursor, table_name: str):
    """MAPPED_ITEM_SEQ 컬럼이 없으면 추가"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    if "MAPPED_ITEM_SEQ" not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN MAPPED_ITEM_SEQ TEXT")
        print(f"✅ [{table_name}] MAPPED_ITEM_SEQ 컬럼 추가 완료")


def build_drug_name_index(cursor: sqlite3.Cursor) -> dict:
    """drugs_data 전체를 로드해 '정제된 약품명 -> itemSeq' 사전을 구축 (매칭 속도 최적화)"""
    cursor.execute("SELECT itemSeq, itemName FROM drugs_data")

    # 중복 이름이 있을 경우 마지막 seq로 덮어써지지만, 공공데이터 특성상 이름이 같으면 동일 약품으로 간주
    drug_dict = {}
    for seq, name in cursor.fetchall():
        if name:
            drug_dict[clean_product_name(name)] = seq
    return drug_dict


def find_matching_item_seq(clean_prduct: str, drug_dict: dict) -> str | None:
    """정제된 PRDUCT 문자열로 완전 일치 -> 포함 관계(LIKE) 순으로 itemSeq를 탐색"""
    mapped_seq = drug_dict.get(clean_prduct)
    if mapped_seq or not clean_prduct or len(clean_prduct) < 4:
        return mapped_seq

    for d_name, d_seq in drug_dict.items():
        if clean_prduct in d_name:
            return d_seq
    return None


def map_recalls_table(conn: sqlite3.Connection, recall_table: str):
    """회수 테이블의 PRDUCT 텍스트 기반으로 drugs_data의 itemSeq를 찾아 MAPPED_ITEM_SEQ 에 업데이트"""
    cursor = conn.cursor()

    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{recall_table}'")
    if not cursor.fetchone():
        print(f"⚠️ [{recall_table}] 테이블이 존재하지 않습니다. 스킵합니다.")
        return

    setup_mapped_columns(cursor, recall_table)

    cursor.execute(f"SELECT rowid, PRDUCT FROM {recall_table} WHERE MAPPED_ITEM_SEQ IS NULL OR MAPPED_ITEM_SEQ = ''")
    recalls = cursor.fetchall()

    if not recalls:
        print(f"✅ [{recall_table}] 맵핑할 새로운 레코드가 없습니다.")
        return

    print(f"🔄 [{recall_table}] 총 {len(recalls)}건의 품목(PRDUCT) 맵핑(Mapping) 시작...")

    drug_dict = build_drug_name_index(cursor)

    match_count = 0
    updates = []
    for rowid, prduct in recalls:
        mapped_seq = find_matching_item_seq(clean_product_name(prduct), drug_dict)
        if mapped_seq:
            updates.append((mapped_seq, rowid))
            match_count += 1

    if updates:
        cursor.executemany(f"UPDATE {recall_table} SET MAPPED_ITEM_SEQ = ? WHERE rowid = ?", updates)
        conn.commit()

    success_rate = (match_count / len(recalls)) * 100 if recalls else 0
    print(f"🎉 [{recall_table}] 맵핑 완료! (성공: {match_count}/{len(recalls)}건, 매칭률: {success_rate:.1f}%)")


def main():
    print("🚀 회수정보(Recalls) ↔ 마스터(drugs_data) 매핑 스크립트 가동")

    if not os.path.exists(DB_PATH):
        print(f"❌ DB 파일을 찾을 수 없습니다: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    # 두 개의 회수 테이블에 대해 맵핑 수행
    map_recalls_table(conn, "medicine_recalls")

    # 맵핑된 키로 인덱스 생성
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_medicine_recalls_mapped ON medicine_recalls(MAPPED_ITEM_SEQ)")
        conn.commit()
    except Exception:
        pass

    conn.close()
    print("✅ 모든 작업이 완료되었습니다.")


if __name__ == "__main__":
    main()
