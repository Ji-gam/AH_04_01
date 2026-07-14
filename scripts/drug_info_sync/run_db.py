import argparse
import os
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

from config_db import API_SPECS, DB_PATH, DEFAULT_WORKERS
from dotenv import load_dotenv
from pipeline_db import APIPipeline

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
load_dotenv(os.path.join(REPO_ROOT, ".env"))


def get_api_key() -> str:
    """.env(리포 루트) 또는 환경변수에서 공공데이터포털 API 인증키를 조회합니다.

    app/core/config.py의 PUBLIC_DATA_API_KEY(T-MED-4)와 동일한 데이터포털 서비스키를 공유한다.
    """

    api_key = os.getenv("PUBLIC_DATA_API_KEY")
    if not api_key:
        raise RuntimeError("PUBLIC_DATA_API_KEY가 설정되지 않았습니다 (.env 또는 환경변수를 확인하세요).")

    return api_key


def run_single_pipeline_wrapper(name: str, spec: Any, api_key: str, once: bool) -> tuple:
    """멀티프로세싱 병렬 실행을 위한 전역 래퍼 함수"""
    try:
        pipeline = APIPipeline(spec, api_key, multiprocess_mode=True)
        downloaded, total = pipeline.run(once=once)
        return name, True, downloaded, total, None
    except Exception:
        import traceback

        return name, False, 0, 0, traceback.format_exc()


def write_final_summary_report(results: list, once: bool, workers: int):
    """모든 병렬 실행이 끝난 후 최종 DB 적재 건수 및 매칭 현황을 progress_db.log 하단에 대시보드로 남깁니다."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    mode_str = "1회성 테스트 모드 (Light Run)" if once else "전수 수집 모드 (Full Sync)"

    total_apis = len(results)
    success_count = sum(1 for r in results if r[1] and r[2] > 0)
    skipped_count = sum(1 for r in results if r[1] and r[2] == 0)
    failed_count = sum(1 for r in results if not r[1])
    total_downloaded = sum(r[2] for r in results if r[1])

    summary_lines = []
    summary_lines.append("=" * 80)
    summary_lines.append("🏆  ALL DB SYNCHRONIZATION COMPLETED SUCCESSFULLY!  🏆")
    summary_lines.append("=" * 80)
    summary_lines.append(f"📅 완료 일시 : {timestamp}")
    summary_lines.append(f"⚙️ 실행 모드 : {mode_str}")
    summary_lines.append(f"🚀 병렬 채널 : 멀티프로세스 ({workers}개)")
    summary_lines.append(f"📁 대상 DB   : {DB_PATH}")
    summary_lines.append("-" * 80)
    summary_lines.append("📊 [수집 결과 상세 집계 - 테이블명 (DB 적재수 / API 총 갯수)]")

    for name, success, downloaded, total, _err_msg in sorted(results, key=lambda x: x[0]):
        spec = API_SPECS.get(name)
        if not spec:
            continue
        table_name = spec.db_table

        if success:
            if downloaded == 0:
                status_str = f"⏭️ 건너뜀 (0 / {total:,})"
            elif once:
                # 1회성 테스트 모드에서는 일부만 가져오므로 무조건 성공으로 취급
                status_str = f"✅ 테스트 완료 ({downloaded:,} / {total:,})"
            elif downloaded >= total:
                # 전수 수집 모드: 데이터 제공처의 총수(total) 이상 다운로드 시 진정한 '성공'
                status_str = f"✅ 성공 ({downloaded:,} / {total:,})"
            else:
                # 총 수보다 적게 다운로드 된 경우 '경고(정합성 위배)' 처리
                status_str = f"⚠️ 데이터 누락 ({downloaded:,} / {total:,})"
        else:
            status_str = "❌ 실패 (오류 발생)"

        summary_lines.append(f"   - {table_name:<32} : {status_str}")

    summary_lines.append("-" * 80)
    summary_lines.append("📊 [수집 결과 집계 요약]")
    summary_lines.append(f"   - 총 가동 API : {total_apis}개")
    summary_lines.append(f"   - 성공 (DB 적재) : {success_count}개 API (총 {total_downloaded:,}건 처리)")
    summary_lines.append(f"   - 건너뜀 (데이터0건): {skipped_count}개 API")
    summary_lines.append(f"   - 실패 (오류 보류) : {failed_count}개 API")
    summary_lines.append("=" * 80)

    report_text = "\n".join(summary_lines)

    print(report_text)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(current_dir, "progress_db.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n" + report_text + "\n")
    except Exception as e:
        print(f"⚠️ 요약 보고서 파일 저장 실패: {e}")


def execute_pipeline(target_apis, num_workers, is_once):
    print(f"\n🚀 총 {len(target_apis)}개의 API에 대해 파이프라인(DB-First) 가동을 준비합니다.")
    print(f"⚙️ 병렬 프로세스 워커 수: {num_workers}")
    if is_once:
        print("⚠️ [테스트 모드] 각 API당 1회(한 페이지)만 수집 후 종료됩니다.")
    print("-" * 60)

    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        api_key = get_api_key()
        future_to_api = {
            executor.submit(run_single_pipeline_wrapper, api_name, API_SPECS[api_name], api_key, is_once): api_name
            for api_name in target_apis
        }

        for future in as_completed(future_to_api):
            api_name = future_to_api[future]
            try:
                res = future.result()
                results.append(res)
                name, success, downloaded, total, err_msg = res
                if success:
                    print(f"✅ [{name}] 파이프라인 DB 동기화 완료! ({downloaded} / {total})")
                else:
                    print(f"❌ [{name}] DB 수집 중 에러 발생:\n{err_msg}")
            except Exception as exc:
                print(f"❌ [{api_name}] 파이프라인 처리 중 치명적 예외 발생: {exc}")
                results.append((api_name, False, 0, 0, str(exc)))
            print("-" * 60)

    write_final_summary_report(results, is_once, num_workers)

    # 21개 API 수집이 완료된 직후 경량화 버전 DB 생성
    create_lightweight_db()

    return results


# drugs_data(빈용 약품 목록)에 있는 품목만 남기기 위한 테이블별 필터 WHERE절.
# 주의: drugs_data의 품목기준코드 컬럼명은 camelCase(itemSeq)라 다른 테이블들의 ITEM_SEQ와
# 다르다 - 예전 버전은 이 차이를 놓쳐서 서브쿼리가 SELECT ITEM_SEQ FROM drugs_data가 아니라
# 바깥 테이블 자기 자신의 ITEM_SEQ로 상관 서브쿼리 처리되어(SQLite가 컬럼을 못 찾으면 바깥
# 스코프로 올라가서 찾는다) WHERE절이 사실상 "항상 참"이 되어 필터링이 전혀 안 먹혔었다
# (dur_prod_usjnt_taboo가 798,696건 그대로 복사됨, 2026-07-15 확인). itemSeq로 고쳐서 반영.
_LIGHT_DB_ITEM_SEQ_SUBQUERY = "(SELECT itemSeq FROM drugs_data)"
_LIGHT_DB_INGR_CODE_SUBQUERY = (
    f"(SELECT DISTINCT INGR_CODE FROM item_ingredient_map WHERE ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY})"
)

_LIGHT_DB_TABLE_FILTERS: dict[str, str] = {
    # 품목기준코드(ITEM_SEQ) 보유 테이블
    "medicine_recalls": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "drug_identification": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "dur_prod_master_list": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "dur_prod_odsn_atent": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "dur_prod_spcify_agrde_taboo": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "dur_prod_mdctn_pd_atent": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "dur_prod_seobang_partition": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "dur_prod_pwnm_taboo": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "dur_prod_efcy_dplct": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "dur_prod_cpcty_atent": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "drug_prdt_prmsn_list": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "drug_prdt_prmsn_detail": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "drug_prdt_mcpn_detail": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    "item_ingredient_map": f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    # 병용금기(양쪽 다 ITEM_SEQ/MIXTURE_ITEM_SEQ) - 어느 한쪽이라도 drugs_data에 있으면 유지
    "dur_prod_usjnt_taboo": (
        f"ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY} OR MIXTURE_ITEM_SEQ IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}"
    ),
    # 위탁생산 묶음정보 - cnsgnItemSeq(camelCase)가 품목기준코드
    "drug_bundle_info": f"cnsgnItemSeq IN {_LIGHT_DB_ITEM_SEQ_SUBQUERY}",
    # 성분(INGR_CODE) 기준 테이블 - item_ingredient_map으로 drugs_data 품목의 성분코드만 역산해서 필터
    "dur_pwnm_taboo": f"INGR_CODE IN {_LIGHT_DB_INGR_CODE_SUBQUERY}",
    "dur_odsn_atent": f"INGR_CODE IN {_LIGHT_DB_INGR_CODE_SUBQUERY}",
    "dur_spcify_agrde_taboo": f"INGR_CODE IN {_LIGHT_DB_INGR_CODE_SUBQUERY}",
    "dur_cpcty_atent": f"INGR_CODE IN {_LIGHT_DB_INGR_CODE_SUBQUERY}",
    "dur_efcy_dplct": f"INGR_CODE IN {_LIGHT_DB_INGR_CODE_SUBQUERY}",
    "dur_mdctn_pd_atent": f"INGR_CODE IN {_LIGHT_DB_INGR_CODE_SUBQUERY}",
    "dur_usjnt_taboo": (
        f"INGR_CODE IN {_LIGHT_DB_INGR_CODE_SUBQUERY} OR MIXTURE_INGR_CODE IN {_LIGHT_DB_INGR_CODE_SUBQUERY}"
    ),
    # drugs_data 자신은 이미 목표 범위 그 자체라 필터 불필요(아래 루프에서 전체 복사로 처리)
    # drug_max_dosage는 CPNT_CD(별도 코드 체계)만 있어 ITEM_SEQ/INGR_CODE로 못 이어서 전체 복사
}

# CREATE TABLE ... AS SELECT는 원본 테이블의 인덱스/제약조건을 가져오지 않는다 - API_SPECS의
# index_columns를 그대로 재사용해서 light DB에도 동일하게 인덱스를 건다. item_ingredient_map은
# API 소스가 아니라 파생 테이블이라 API_SPECS에 없어서 별도로 추가.
_LIGHT_DB_EXTRA_INDEX_COLUMNS: dict[str, list[str]] = {
    "item_ingredient_map": ["ITEM_SEQ"],
}


def _light_db_index_columns() -> dict[str, list[str]]:
    columns_by_table = {spec.db_table: spec.index_columns for spec in API_SPECS.values() if spec.index_columns}
    columns_by_table.update(_LIGHT_DB_EXTRA_INDEX_COLUMNS)
    return columns_by_table


def create_lightweight_db():
    print("\n" + "=" * 80)
    print("🚀 [Step 2] 경량화 DB(drug_light.db) 생성 시작")
    print("=" * 80)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    full_db_path = os.path.join(current_dir, DB_PATH)
    light_db_path = os.path.join(current_dir, "../../app/database/drug_light.db")

    if os.path.exists(light_db_path):
        os.remove(light_db_path)

    conn = sqlite3.connect(full_db_path)
    cursor = conn.cursor()

    try:
        # ATTACH를 사용하여 두 DB를 연결
        cursor.execute(f"ATTACH DATABASE '{light_db_path}' AS light_db")

        # 원본 DB의 전체 테이블 목록 조회
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        index_columns_by_table = _light_db_index_columns()

        for table in tables:
            where_clause = _LIGHT_DB_TABLE_FILTERS.get(table)
            try:
                if where_clause:
                    print(f"   - {table:<32} : 필터링 복사 중 (drugs_data 기준)...", end=" ", flush=True)
                    cursor.execute(f"CREATE TABLE light_db.{table} AS SELECT * FROM {table} WHERE {where_clause}")
                else:
                    print(f"   - {table:<32} : 전체 복사 중...", end=" ", flush=True)
                    cursor.execute(f"CREATE TABLE light_db.{table} AS SELECT * FROM {table}")

                for idx_col in index_columns_by_table.get(table, []):
                    idx_name = f"idx_{table}_{idx_col}"
                    cursor.execute(f'CREATE INDEX IF NOT EXISTS light_db."{idx_name}" ON {table}("{idx_col}")')
                print("완료!")
            except Exception as e:
                print(f"실패({e})")

        cursor.execute("DETACH DATABASE light_db")
        print("\n✅ 경량화 DB(drug_light.db) 생성이 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f"\n❌ 경량화 DB 생성 중 오류 발생: {e}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="ReMedi 공공데이터 API 수집 -> DB 자동 적재 실행 도구")
    parser.add_argument(
        "api_name", nargs="?", help="단일 API 실행 시 API 이름을 입력 (예: e_drug). 입력하지 않으면 전체 실행"
    )
    parser.add_argument("--all", action="store_true", help="config_db.py에 정의된 모든 API를 대상으로 파이프라인 실행")
    parser.add_argument(
        "--once", action="store_true", help="테스트용: 전체를 순회하지 않고 단 1회(1페이지만) 호출 후 종료"
    )
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS, help=f"병렬 처리할 워커 프로세스 수 (기본값: {DEFAULT_WORKERS})"
    )
    parser.add_argument("--list", action="store_true", help="지원하는 모든 API의 키 목록을 출력합니다.")
    args = parser.parse_args()

    if args.list:
        print("🎯 지원 가능한 API 키 목록:")
        for idx, key in enumerate(API_SPECS.keys(), 1):
            spec = API_SPECS[key]
            print(f"  {idx:02d}. {key:<30} | {spec.db_table:<30} | {spec.base_url}")
        return

    if args.all:
        target_apis = list(API_SPECS.keys())
    elif args.api_name:
        if args.api_name not in API_SPECS:
            print(f"❌ 오류: '{args.api_name}'는 config_db.py에 정의되지 않은 API입니다.")
            import sys

            sys.exit(1)
        target_apis = [args.api_name]
    else:
        print("⚠️ 실행 대상을 지정해주세요. (단일 API 이름 또는 --all)")
        parser.print_help()
        import sys

        sys.exit(1)

    execute_pipeline(target_apis, args.workers, args.once)


if __name__ == "__main__":
    main()
