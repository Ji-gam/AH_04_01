import argparse
import os
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

from config_db import API_SPECS, DB_PATH, DEFAULT_WORKERS
from pipeline_db import APIPipeline


def get_api_key() -> str:
    """환경변수에서 공공데이터포털 API 인증키를 조회합니다."""

    api_key = os.getenv("DATA_GO_KR_API_KEY")
    if not api_key:
        raise RuntimeError("환경변수 DATA_GO_KR_API_KEY가 설정되지 않았습니다.")

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

        for table in tables:
            if table == "dur_prod_usjnt_taboo":
                # drug_light.db: dur_prod_usjnt_taboo는 drugs_data에 있는 제품만 필터링
                print(f"   - {table:<32} : 필터링 복사 중 (ITEM_SEQ 기반)...", end=" ", flush=True)
                cursor.execute(f"""
                    CREATE TABLE light_db.{table} AS
                    SELECT * FROM {table}
                    WHERE ITEM_SEQ IN (SELECT ITEM_SEQ FROM drugs_data)
                """)
                print("완료!")
            else:
                # 나머지 테이블은 전체 복사
                print(f"   - {table:<32} : 전체 복사 중...", end=" ", flush=True)
                cursor.execute(f"CREATE TABLE light_db.{table} AS SELECT * FROM {table}")
                print("완료!")

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
