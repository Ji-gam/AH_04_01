import os
import json
import time
import requests
import sqlite3
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from config_db import APISpec, DB_PATH

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(CURRENT_DIR, "download_db_mode")

def write_progress_log(api_name: str, tag: str, message: str):
    log_path = os.path.join(CURRENT_DIR, "progress_db.log")
    timestamp = time.strftime("%H:%M:%S")
    log_line = f"[{timestamp}] | {api_name:<28} | {tag:<7} | {message.strip()}\n"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"⚠️ 로그 파일 쓰기 중 오류 발생: {e}")

class APIPipeline:
    def __init__(self, spec: APISpec, api_key: str, output_dir: Optional[str] = None, multiprocess_mode: bool = False):
        self.spec = spec
        self.api_key = api_key
        self.output_dir = output_dir if output_dir else DEFAULT_OUTPUT_DIR
        self.multiprocess_mode = multiprocess_mode
        self.db_path = os.path.join(CURRENT_DIR, DB_PATH)
        # Flush 버퍼 사이즈 설정 (메모리 절약 및 DB 락 최소화를 위해 5,000건)
        self.chunk_size = 5000

    def _print_progress_bar(self, current: int, total: int, start_time: float, prefix_msg: str = "", bar_length: int = 20):
        if total <= 0: return
        percent = (current / total) * 100
        filled = int(bar_length * current // total)
        bar = '█' * filled + '░' * (bar_length - filled)
        elapsed_time = time.time() - start_time
        
        if current < 1000:
            eta_str = "측정중..."
        else:
            time_per_item = elapsed_time / current
            remaining_seconds = (total - current) * time_per_item
            if remaining_seconds >= 60:
                eta_str = f"{int(remaining_seconds // 60)}분 {int(remaining_seconds % 60)}초"
            else:
                eta_str = f"{int(remaining_seconds)}초"
        
        if self.multiprocess_mode:
            print(f"[{self.spec.name}] {prefix_msg}({percent:.1f}% / {current}건 / 총 {total}건) DB 적재 중... 예상: {eta_str}")
        else:
            msg = f"\r{prefix_msg}[{bar}] ({percent:.1f}% / {current}건 / 총 {total}건) DB 적재 중... 예상: {eta_str}  "
            print(msg, end="", flush=True)

    def _call_api(self, page_no: int, num_of_rows: int, extra_params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        params = {"serviceKey": self.api_key, "pageNo": page_no, "numOfRows": num_of_rows}
        params.update(self.spec.extra_params)
        if extra_params: params.update(extra_params)
            
        try:
            response = requests.get(self.spec.base_url, params=params, timeout=15)
            response_text = response.text
            if response.status_code != 200 or "Error forwarding request" in response_text or "LIMIT_EXCEEDED" in response_text or "TOTAL_TRACK_LIMIT" in response_text:
                return None # 에러 처리는 기존과 동일하게 None 리턴하여 재시도 유도
            return response_text
        except requests.exceptions.RequestException:
            return None

    def _parse_xml(self, xml_data: str) -> Tuple[List[Dict[str, Any]], int]:
        try:
            xml_bytes = xml_data.encode('utf-8', errors='ignore') if isinstance(xml_data, str) else xml_data
            root = ET.fromstring(xml_bytes)
        except Exception as e:
            return [], 0
            
        items_list = []
        total_count_elem = root.find(self.spec.xml_total_count_path)
        total_count = int(total_count_elem.text) if total_count_elem is not None else 0
        
        for item in root.findall(self.spec.xml_item_path):
            item_dict = {}
            for child in item:
                item_dict[child.tag] = child.text.strip() if child.text else ""
            items_list.append(item_dict)
            
        return items_list, total_count

    # --- Checkpoint 엔진 (기존 동일) ---
    def _get_checkpoint_path(self, extra_label: str = "") -> str:
        return os.path.join(self.output_dir, f"checkpoint_{self.spec.name}_{extra_label}.json" if extra_label else f"checkpoint_{self.spec.name}.json")

    def _save_checkpoint(self, page_no: int, extra_label: str = ""):
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self._get_checkpoint_path(extra_label), "w", encoding="utf-8") as f:
            json.dump({"page_no": page_no}, f, ensure_ascii=False)

    def _load_checkpoint(self, extra_label: str = "") -> int:
        path = self._get_checkpoint_path(extra_label)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f).get("page_no", self.spec.start_page)
            except Exception: pass
        return self.spec.start_page

    def _delete_checkpoint(self, extra_label: str = ""):
        try: os.remove(self._get_checkpoint_path(extra_label))
        except Exception: pass

    # --- DB 저장 로직 ---
    def _flush_to_db(self, conn: sqlite3.Connection, records: List[Dict[str, Any]]):
        if not records: return
        
        cursor = conn.cursor()
        columns = list(records[0].keys())
        table_name = self.spec.db_table
        
        # 1. 테이블 존재 여부 확인
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            # 처음 테이블 생성 시 UNIQUE 제약 조건(진정한 복합키) 포함하여 생성
            pks = self.spec.primary_keys
            col_defs = [f'"{c}" TEXT' for c in columns]
            
            # UNIQUE 제약조건 추가
            unique_clause = ""
            if pks:
                # 응답 데이터에 PK 컬럼이 모두 정상적으로 존재하는지 필터링
                valid_pks = [pk for pk in pks if pk in columns]
                if valid_pks:
                    pk_str = ", ".join([f'"{pk}"' for pk in valid_pks])
                    unique_clause = f", UNIQUE({pk_str})"
            
            create_sql = f'CREATE TABLE "{table_name}" ({", ".join(col_defs)}{unique_clause})'
            cursor.execute(create_sql)
            
            # 검색 최적화를 위한 동적 INDEX 자동 생성 (config_db.py 명세 기반)
            idx_cols = getattr(self.spec, "index_columns", [])
            for idx_col in idx_cols:
                if idx_col in columns:
                    idx_name = f"idx_{table_name}_{idx_col}"
                    try:
                        cursor.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}"("{idx_col}")')
                    except Exception as e:
                        print(f"\n⚠️ [{self.spec.name}] 인덱스 생성 실패 ({idx_col}): {e}")
                        
        else:
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            existing_cols = [row[1] for row in cursor.fetchall()]
            
            # API에서 받은 새 컬럼이 있는지 확인하고 로그 남기기 (DB 확장은 하지 않음)
            new_cols = [c for c in columns if c not in existing_cols]
            if new_cols:
                # print(f"\n⚠️ [{self.spec.name}] 예상치 못한 새 컬럼 감지됨 (스키마 확장 불가로 무시됨): {new_cols}")
                write_progress_log(self.spec.name, "WARNING", f"예상치 못한 새 컬럼 감지됨 (무시됨): {new_cols}")
            
            # API에서 받은 columns 목록을 기존 DB 스키마에 정의된 컬럼들로만 제한(교집합)
            columns = [c for c in columns if c in existing_cols]
            
        col_names_str = ",".join([f'"{c}"' for c in columns])
        placeholders = ",".join(["?"] * len(columns))
        values_list = [tuple(record.get(col, "") for col in columns) for record in records]
        
        # INSERT OR REPLACE를 통해 덮어쓰기(Upsert) 수행. 테이블 UNIQUE 제약조건에 따라 무결성 유지 및 최신 반영
        sql = f'INSERT OR REPLACE INTO "{table_name}" ({col_names_str}) VALUES ({placeholders})'
        
        cursor.executemany(sql, values_list)
        conn.commit()

    def _run_single_extraction(self, conn: sqlite3.Connection, once: bool, extra_params: Optional[Dict[str, Any]] = None, prefix_msg: str = "", extra_label: str = "") -> Tuple[int, int]:
        page_no = self._load_checkpoint(extra_label) if not once else self.spec.start_page
        num_of_rows = self.spec.num_of_rows
        start_time = time.time()
        final_total_count = 0
        accumulated_rows = (page_no - 1) * num_of_rows if page_no > self.spec.start_page else 0
        
        # [하트비트 추적 변수 초기화]
        last_heartbeat_time = time.time()
        last_heartbeat_rows = accumulated_rows

        buffer_list = [] # DB Flush 용 버퍼
        
        while True:
            xml_result = self._call_api(page_no, num_of_rows, extra_params)
            
            # ⚠️ API 호출 에러 발생 시 30분 대기 후 끊어진 지점부터 재시도
            if xml_result is None:
                if not once:
                    self._save_checkpoint(page_no, extra_label)
                
                err_msg = f"⚠️ API 연동 실패 - 30분 대기 후 재시도 예정 (실패 페이지: {page_no})"
                print(f"\n⚠️ [{self.spec.name}{extra_label}] {err_msg}")
                write_progress_log(f"{self.spec.name}{extra_label}", "WAITING", err_msg)
                
                time.sleep(1800)  # 30분 대기
                continue
                
            items, total_count = self._parse_xml(xml_result)
            final_total_count = total_count
            
            # API 제공기관 서버 장애 등으로 중간에 뚝 끊기는 경우 방어
            if not items:
                current_offset = (page_no - 1) * num_of_rows
                if total_count > 0 and current_offset >= total_count:
                    break
                
                if accumulated_rows < total_count and total_count > 0:
                    if not once:
                        self._save_checkpoint(page_no, extra_label)
                    mismatch_msg = f"⚠️ 데이터 정합성 불일치 (수집: {accumulated_rows} < 전체: {total_count}) - 30분 대기 후 재시도"
                    print(f"\n⚠️ [{self.spec.name}{extra_label}][정합성 위배 감지] {mismatch_msg}")
                    write_progress_log(f"{self.spec.name}{extra_label}", "WAITING", mismatch_msg)
                    
                    time.sleep(1800)
                    continue
                break
                
            # DB Flush Buffer 적재
            buffer_list.extend(items)
            accumulated_rows += len(items)
            
            # 버퍼가 일정량 차면 DB로 Flush
            if len(buffer_list) >= self.chunk_size:
                try:
                    self._flush_to_db(conn, buffer_list)
                    buffer_list.clear() # 버퍼 비우기
                except Exception as e:
                    print(f"\n❌ [{self.spec.name}] DB Flush 중 오류 발생: {e}")
            
            self._print_progress_bar(accumulated_rows, total_count, start_time, prefix_msg)
            
            # 💡 [하트비트 판정 로직 - 프로덕션 사양 적용]
            # 10분(600초) 경과 또는 50,000건(100페이지) 추가 적재마다 하트비트 로깅
            current_time = time.time()
            elapsed_since_heartbeat = current_time - last_heartbeat_time
            rows_since_heartbeat = accumulated_rows - last_heartbeat_rows
            
            if elapsed_since_heartbeat >= 600 or rows_since_heartbeat >= 50000:
                percent = (accumulated_rows / total_count) * 100 if total_count > 0 else 0
                heartbeat_msg = f"⏳ 전수 수집 진행 중... (현재: {accumulated_rows:,}건 / 총 {total_count:,}건 | {percent:.1f}%)"
                write_progress_log(f"{self.spec.name}{extra_label}", "PROGRESS", heartbeat_msg)
                
                # 하트비트 기록점 갱신
                last_heartbeat_time = current_time
                last_heartbeat_rows = accumulated_rows
            
            if not once: self._save_checkpoint(page_no + 1, extra_label)
            
            # once일 때 최대 10페이지(10회 호출)만 실행하고 중단
            if once and page_no >= self.spec.start_page + 9:
                break
                
            if accumulated_rows >= total_count and total_count > 0:
                break
                
            time.sleep(0.4)
            page_no += 1
            
        # 루프 종료 후 남은 버퍼 Flush
        if buffer_list:
            try:
                self._flush_to_db(conn, buffer_list)
                buffer_list.clear()
            except Exception as e:
                print(f"\n❌ [{self.spec.name}] 마지막 DB Flush 중 오류 발생: {e}")
            
        if not once: self._delete_checkpoint(extra_label)
        return accumulated_rows, final_total_count

    def run(self, once: bool = False) -> Tuple[int, int]:
        start_msg = f"🚀 DB 적재 파이프라인 가동 (테스트모드: {once})"
        print(f"\n🚀 [{self.spec.name}] {start_msg}")
        write_progress_log(self.spec.name, "START", start_msg)
        
        # SQLite 연결 수립 (timeout을 넉넉히 주어 멀티프로세싱 DB Lock 방지)
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        
        total_downloaded = 0
        accumulated_total_count = 0
        
        if self.spec.is_prescription:
            months = [f"2025{m:02d}" for m in range(1, 3)]
            target_months = ['202501'] if once else months
            for month in target_months:
                month_downloaded, month_total = self._run_single_extraction(conn, once, {'yearMonth': month}, f"  ㄴ [{month}] ", extra_label=month)
                total_downloaded += month_downloaded
                accumulated_total_count += month_total
                time.sleep(0.5)
        else:
            total_downloaded, accumulated_total_count = self._run_single_extraction(conn, once)

        conn.close()
        
        if total_downloaded > 0:
            complete_msg = f"✅ DB 저장 완료 -> {self.spec.db_table} 테이블 (총 {total_downloaded}건 적재/갱신)"
            print(f"\n💾 [{self.spec.name}] {complete_msg}")
            write_progress_log(self.spec.name, "SUCCESS", complete_msg)
            return total_downloaded, accumulated_total_count
        else:
            return 0, accumulated_total_count
