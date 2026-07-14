import os
import sys
import time

# 프로젝트 내 모듈 임포트
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from config_db import API_SPECS, DEFAULT_WORKERS  # noqa: E402
from mapping_recalls import main as map_recalls_main  # noqa: E402
from run_db import execute_pipeline  # noqa: E402


def run_full_orchestration() -> dict:
    """
    1. 22개 공공데이터 API Full Sync (DB 적재 + 자동 INDEX 생성)
    2. 회수정보(PRDUCT) ↔ 마스터(ITEM_SEQ) 이름 기반 후처리 맵핑 스크립트 가동

    향후 Celery 등 비동기 스케줄러에서 이 함수를 단일 엔트리포인트로 호출하면 됩니다.
    """
    print("=" * 80)
    print("🚀 [ReMedi 오케스트레이션] 전체 데이터 파이프라인 가동 시작 🚀")
    print("=" * 80)

    start_time = time.time()
    result_report = {}

    # -------------------------------------------------------------------------
    # 단계 1: 데이터 수집 및 DB 적재 파이프라인 (run_db)
    # -------------------------------------------------------------------------
    print("\n[Phase 1] 22개 API 원시 데이터 수집 및 DB 갱신 (DB-First + INDEXing)")
    target_apis = list(API_SPECS.keys())

    try:
        # workers=8, is_once=False(전수수집)
        pipeline_results = execute_pipeline(target_apis, num_workers=DEFAULT_WORKERS, is_once=False)
        result_report["pipeline_results"] = pipeline_results
        result_report["pipeline_status"] = "SUCCESS"
    except Exception as e:
        print(f"\n❌ [Phase 1 Error] 파이프라인 실행 중 치명적 예외 발생: {e}")
        result_report["pipeline_status"] = "FAILED"
        result_report["error"] = str(e)
        return result_report  # 파이프라인 실패 시 매핑 진행 안 함

    # -------------------------------------------------------------------------
    # 단계 2: 데이터 정제 및 후처리 매핑 (mapping_recalls)
    # -------------------------------------------------------------------------
    print("\n[Phase 2] 데이터 정제 및 후처리 매핑 (ELT)")
    try:
        # mapping_recalls.py 의 main 로직 실행
        map_recalls_main()
        result_report["mapping_status"] = "SUCCESS"
    except Exception as e:
        print(f"\n❌ [Phase 2 Error] 후처리 맵핑 스크립트 실행 중 예외 발생: {e}")
        result_report["mapping_status"] = "FAILED"
        result_report["error"] = str(e)

    # -------------------------------------------------------------------------
    # 마무리
    # -------------------------------------------------------------------------
    elapsed_sec = time.time() - start_time
    hours, rem = divmod(elapsed_sec, 3600)
    minutes, seconds = divmod(rem, 60)

    time_str = f"{int(hours)}시간 {int(minutes)}분 {int(seconds)}초"

    print("\n" + "=" * 80)
    print("🎉 [ReMedi 오케스트레이션] 전체 파이프라인 가동 완료 🎉")
    print(f"⏱️ 총 소요 시간: {time_str}")
    print("=" * 80)

    result_report["elapsed_time"] = time_str
    return result_report


if __name__ == "__main__":
    run_full_orchestration()
