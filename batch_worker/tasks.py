import os
import json
import time
import requests
import xml.etree.ElementTree as ET
import csv
from celery.utils.log import get_task_logger
from celery import chord
from batch_worker.celery_app import celery_app
from batch_worker.config import settings
from datetime import datetime

logger = get_task_logger(__name__)

NUM_OF_ROWS = 500

API_CONFIGS = {
    "drugs_einfo": "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList",
    "drug_identification_v3": "http://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03/getMdcinGrnIdntfcInfoList03",
    "drug_recalls_final": "https://apis.data.go.kr/1471000/MdcinRtrvlSleStpgeInfoService04/getMdcinRtrvlSleStpgelList03",
    "drug_max_dosage": "https://apis.data.go.kr/1471000/DayMaxDosgQyByIngdService/getDayMaxDosgQyByIngdInq",
    "drug_bundle_info": "https://apis.data.go.kr/1471000/DrbBundleInfoService02/getDrbBundleList02",
    "dur_usjnt_taboo": "https://apis.data.go.kr/1471000/DURIrdntInfoService03/getUsjntTabooInfoList02",
    "dur_spcify_agrde_taboo": "https://apis.data.go.kr/1471000/DURIrdntInfoService03/getSpcifyAgrdeTabooInfoList02",
    "dur_pwnm_taboo": "https://apis.data.go.kr/1471000/DURIrdntInfoService03/getPwnmTabooInfoList02",
    "dur_cpcty_atent": "https://apis.data.go.kr/1471000/DURIrdntInfoService03/getCpctyAtentInfoList02",
    "dur_mdctn_pd_atent": "https://apis.data.go.kr/1471000/DURIrdntInfoService03/getMdcinPdAtentInfoList02",
    "dur_odsn_atent": "https://apis.data.go.kr/1471000/DURIrdntInfoService03/getOdsnAtentInfoList02",
    "dur_efcy_dplct": "https://apis.data.go.kr/1471000/DURIrdntInfoService03/getEfcyDplctInfoList02",
    "dur_prod_usjnt_taboo": "https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getUsjntTabooInfoList03",
}

def get_checkpoint_path():
    return os.path.join(settings.DATA_DIR, "checkpoint.json")

def load_checkpoint():
    path = get_checkpoint_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_checkpoint(data):
    path = get_checkpoint_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def handle_public_api_errors(response):
    """
    공공데이터포털 XML 에러 메시지 분석
    """
    if response.status_code != 200:
        return f"HTTP Error {response.status_code}"
    
    text = response.text
    if "API not found" in text: return "404 API not found"
    if "Forbidden" in text: return "403 Forbidden"
    if "Unauthorized" in text: return "401 Unauthorized"
    if "Error forwarding request" in text: return "Gateway Error"
    if "LIMIT_EXCEEDED" in text or "rate limit" in text: return "Rate Limit Exceeded"
    if "TOTAL_TRACK_LIMIT" in text or "quota exceeded" in text: return "Quota Exceeded"
    if "INVALID_KEY" in text or "SERVICE_KEY_IS_NOT_REGISTERED" in text: return "API Key Error"
    
    return None

def fetch_public_api_data(task_instance, task_id: str, url: str):
    """
    공통 API 수집 로직
    """
    today = datetime.now().strftime("%y%m%d")
    csv_filename = f"{task_id}.temp.csv" # 임시 파일명으로 저장
    csv_filepath = os.path.join(settings.DATA_DIR, csv_filename)
    
    checkpoint = load_checkpoint()
    task_state = checkpoint.get(task_id, {})
    
    last_success_page = task_state.get("last_success_page", 0)
    
    if task_state.get("date") != today:
        # 새로운 날짜의 배치가 시작되면 페이지 초기화
        last_success_page = 0
        task_state = {}

    current_page = last_success_page + 1
    
    logger.info(f"Starting {task_id} from page {current_page}")
    
    if task_state.get("status") == "COMPLETED" and task_state.get("date") == today:
        logger.info(f"Task {task_id} already completed for {today}")
        return {"task_id": task_id, "status": "COMPLETED", "message": "Already up to date"}

    mode = "a" if current_page > 1 and os.path.exists(csv_filepath) else "w"
    
    try:
        with open(csv_filepath, mode, newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            headers_written = mode == "a"
            
            while True:
                params = {
                    "serviceKey": settings.DATA_GV_KR,
                    "pageNo": current_page,
                    "numOfRows": NUM_OF_ROWS
                }
                
                logger.info(f"[{task_id}] Fetching page {current_page}...")
                start_time = time.time()
                response = requests.get(url, params=params, timeout=30)
                
                err_msg = handle_public_api_errors(response)
                if err_msg:
                    logger.error(f"[{task_id}] Error: {err_msg}")
                    # API Key 에러 등은 재시도하지 않음
                    if "API Key Error" in err_msg or "Unauthorized" in err_msg:
                        raise Exception(err_msg)
                    raise task_instance.retry(countdown=60)
                
                try:
                    root = ET.fromstring(response.content)
                except Exception as e:
                    logger.error(f"[{task_id}] XML Parse Error: {e}")
                    raise task_instance.retry(countdown=60)
                
                items = root.findall(".//item")
                if not items:
                    logger.info(f"[{task_id}] No more items found. Finished!")
                    break
                
                for item in items:
                    row_data = {}
                    for child in item:
                        row_data[child.tag] = child.text if child.text else ""
                    
                    if not headers_written:
                        writer.writerow(row_data.keys())
                        headers_written = True
                    
                    writer.writerow(row_data.values())
                
                f.flush()
                os.fsync(f.fileno())
                
                task_state["last_success_page"] = current_page
                task_state["date"] = today
                task_state["status"] = "IN_PROGRESS"
                checkpoint[task_id] = task_state
                save_checkpoint(checkpoint)
                
                total_elem = root.find(".//totalCount")
                total_count = int(total_elem.text) if total_elem is not None and total_elem.text else 0
                
                logger.info(f"[{task_id}] Saved {len(items)} items from page {current_page}. (Total: {total_count}) Took {time.time() - start_time:.2f}s")
                
                if current_page * NUM_OF_ROWS >= total_count:
                    logger.info(f"[{task_id}] Reached end of data based on totalCount.")
                    break
                    
                current_page += 1
                time.sleep(0.5)
                
    except Exception as e:
        logger.error(f"[{task_id}] Failed during fetch: {e}")
        raise e
        
    task_state["status"] = "COMPLETED"
    task_state["last_success_page"] = current_page
    checkpoint[task_id] = task_state
    save_checkpoint(checkpoint)
    
    return {"task_id": task_id, "status": "COMPLETED", "pages_fetched": current_page}

# ==========================================
# 13종 개별 Task 정의
# ==========================================
@celery_app.task(bind=True, max_retries=3)
def fetch_api_task(self, task_id: str):
    url = API_CONFIGS.get(task_id)
    if not url:
        raise ValueError(f"Unknown task_id: {task_id}")
    return fetch_public_api_data(self, task_id, url)


# ==========================================
# 봉인(Seal) 검증 코디네이터 (Chord Callback)
# ==========================================
@celery_app.task
def check_all_sealed_callback(results):
    """
    모든 13개 Task가 완료(COMPLETED)되었는지 검증하고 봉인 해제.
    """
    logger.info(f"Coordinator triggered with {len(results)} results.")
    checkpoint = load_checkpoint()
    today = datetime.now().strftime("%y%m%d")
    
    all_completed = True
    for task_id in API_CONFIGS.keys():
        state = checkpoint.get(task_id, {})
        if state.get("status") != "COMPLETED" or state.get("date") != today:
            all_completed = False
            logger.warning(f"Task {task_id} is not yet completed for today.")
            break
            
    if all_completed:
        logger.info("All 13 APIs successfully fetched. Unlocking SEAL!")
        checkpoint["ALL_SEAL_UNLOCKED"] = True
        checkpoint["SEAL_DATE"] = today
        
        # 템프 파일을 정규 파일로 리네임 (Sealing)
        for task_id in API_CONFIGS.keys():
            temp_file = os.path.join(settings.DATA_DIR, f"{task_id}.temp.csv")
            final_file = os.path.join(settings.DATA_DIR, f"{today}-{task_id}.csv")
            if os.path.exists(temp_file):
                os.rename(temp_file, final_file)
                logger.info(f"Renamed {temp_file} to {final_file}")
                
        save_checkpoint(checkpoint)
        
        # TODO: Trigger next phase (Delta Parsing & DB Transaction)
        return {"status": "SEAL_UNLOCKED", "date": today}
    else:
        logger.info("Not all APIs are completed yet. Keeping SEAL locked.")
        return {"status": "SEAL_LOCKED"}

@celery_app.task
def trigger_daily_batch():
    """
    일간 13종 API 동기화 배치 트리거
    """
    tasks = [fetch_api_task.s(task_id) for task_id in API_CONFIGS.keys()]
    # Celery Chord를 이용하여 모든 task가 끝나면 콜백 실행
    workflow = chord(tasks)(check_all_sealed_callback.s())
    return {"status": "WORKFLOW_STARTED", "workflow_id": workflow.id}
