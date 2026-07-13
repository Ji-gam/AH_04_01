import os
import json
import time
import requests
import xml.etree.ElementTree as ET
import csv
from celery.utils.log import get_task_logger
from batch_worker.celery_app import celery_app
from batch_worker.config import settings
from datetime import datetime

logger = get_task_logger(__name__)

EASY_DRUG_URL = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
NUM_OF_ROWS = 500

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

@celery_app.task(bind=True, max_retries=3)
def fetch_easy_drug_info(self):
    """
    e약은요 단일 공공데이터 API 수집기 PoC
    """
    task_id = "easy_drug"
    today = datetime.now().strftime("%y%m%d")
    csv_filename = f"{today}-easy_drug.csv"
    csv_filepath = os.path.join(settings.DATA_DIR, csv_filename)
    
    checkpoint = load_checkpoint()
    task_state = checkpoint.get(task_id, {})
    
    last_success_page = task_state.get("last_success_page", 0)
    current_page = last_success_page + 1
    
    logger.info(f"Starting {task_id} from page {current_page}")
    
    # Check if this task was already completed today
    if task_state.get("status") == "COMPLETED" and task_state.get("date") == today:
        logger.info(f"Task {task_id} already completed for {today}")
        return {"status": "COMPLETED", "message": "Already up to date"}

    # CSV Open in Append mode if resuming, else write headers
    mode = "a" if current_page > 1 and os.path.exists(csv_filepath) else "w"
    
    try:
        with open(csv_filepath, mode, newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            headers_written = mode == "a"
            
            while True:
                params = {
                    "serviceKey": settings.DATA_GV_KR,
                    "pageNo": current_page,
                    "numOfRows": NUM_OF_ROWS
                }
                
                logger.info(f"Fetching page {current_page}...")
                start_time = time.time()
                response = requests.get(EASY_DRUG_URL, params=params, timeout=30)
                
                if response.status_code != 200:
                    logger.error(f"HTTP Error {response.status_code}")
                    raise self.retry(countdown=60)
                
                if "INVALID_KEY" in response.text or ("SERVICE_KEY" in response.text and "REGISTERED" not in response.text):
                    logger.error("API Key Error")
                    raise Exception("API Key Error")
                
                try:
                    root = ET.fromstring(response.content)
                except Exception as e:
                    logger.error(f"XML Parse Error: {e}")
                    raise self.retry(countdown=60)
                
                items = root.findall(".//item")
                if not items:
                    logger.info("No more items found. Finished!")
                    break
                
                for item in items:
                    row_data = {}
                    for child in item:
                        row_data[child.tag] = child.text
                    
                    if not headers_written:
                        writer.writerow(row_data.keys())
                        headers_written = True
                    
                    writer.writerow(row_data.values())
                
                f.flush()
                os.fsync(f.fileno()) # Force write to disk
                
                # Update checkpoint
                task_state["last_success_page"] = current_page
                task_state["date"] = today
                task_state["status"] = "IN_PROGRESS"
                checkpoint[task_id] = task_state
                save_checkpoint(checkpoint)
                
                # Simulate error for testing
                if current_page == 3 and os.getenv("SIMULATE_ERROR") == "1":
                    logger.warning("SIMULATED ERROR at page 3")
                    raise Exception("Simulated error for checkpoint test")
                
                total_elem = root.find(".//totalCount")
                total_count = int(total_elem.text) if total_elem is not None and total_elem.text else 0
                
                logger.info(f"Saved {len(items)} items from page {current_page}. (Total: {total_count}) Took {time.time() - start_time:.2f}s")
                
                if current_page * NUM_OF_ROWS >= total_count:
                    logger.info("Reached end of data based on totalCount.")
                    break
                    
                current_page += 1
                time.sleep(0.5) # Gentle rate limiting
                
    except Exception as e:
        logger.error(f"Failed during fetch: {e}")
        raise e
        
    # Mark as completed
    task_state["status"] = "COMPLETED"
    task_state["last_success_page"] = current_page
    checkpoint[task_id] = task_state
    save_checkpoint(checkpoint)
    
    return {"status": "COMPLETED", "pages_fetched": current_page}
