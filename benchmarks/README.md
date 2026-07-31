# T-QUAL-1 비동기 처리 벤치마크

`docs/tasks/T-QUAL-1-async-benchmark.md`의 근거 자료. 평가 기준 "5-5 비동기 처리"의
"성능 개선 결과 제시" 요건과, `docs/decision_log/2026-07-10-ai-rag-worker.md`의 F-DOC-1(처방전
OCR+LLM 체인)이 미뤄둔 "실제 지연시간 데이터"를 채우기 위한 벤치마크 도구.

## 구성

- `bench_app.py` — 실서비스(`app/main.py`)와 독립된 소형 FastAPI 앱(포트 8090).
  OCR/LLM 같은 순차 외부 I/O 호출을 `asyncio.sleep`(async 처리 시)/`time.sleep`(blocking 시)으로
  시뮬레이션. 3개 변형(`/bench/async-io`, `/bench/blocking`, `/bench/threadpool`) 제공.
- `run_load.py` — `httpx.AsyncClient`(신규 의존성 없음, 프로젝트에 이미 존재) 기반 부하 드라이버.
  동시성 레벨별 P50/P95/P99/처리량 집계, Markdown 표 + CSV 출력.
- `results/` — 실행 결과 CSV 저장 위치.

## 실행 방법

### 1. A/B 대조 벤치마크 (async-io vs blocking vs threadpool)

```bash
# 터미널 1: 벤치마크용 앱 기동
uv run uvicorn benchmarks.bench_app:app --port 8090

# 터미널 2: 부하 실행
uv run python benchmarks/run_load.py --target bench --concurrency 1,10,50,100 --rounds 3 \
    --delay 0.1 --steps 3 --csv-out benchmarks/results/bench_ab.csv
```

- `--delay`/`--steps`: 시뮬레이션 I/O 지연(초)과 순차 호출 횟수. 기본값(0.1s × 3회 = 300ms)은
  OCR 호출 1회 + LLM 호출 1회 + 여유분을 근사한 값. 실제 CLOVA/OCR 평균 지연을 측정하게 되면
  이 값으로 교체해 재실행하면 된다.
- `--concurrency`: 동시 요청 수 레벨. 낮은 값(1)에서는 세 변형이 거의 동일해야 하고,
  높은 값(50, 100)에서 차이가 극명해져야 정상이다.

### 2. 실제 앱(실행 중인 서비스)의 안전한 읽기 엔드포인트 실측

```bash
# 실제 앱을 Docker(docker compose up) 또는 로컬 uvicorn으로 기동한 뒤
uv run python benchmarks/run_load.py --target live \
    --url "http://localhost:8000/api/v1/<읽기전용-GET-엔드포인트>" \
    --token "Bearer <access_token>" \
    --concurrency 1,10,50,100 --csv-out benchmarks/results/live_endpoint.csv
```

**주의**: 쓰기/과금/외부 API 호출이 발생하는 엔드포인트는 절대 대상으로 삼지 않는다.
인증이 필요한 GET 전용 엔드포인트(예: 복약 스케줄 목록, 프로필 조회)만 사용한다.
인증에 사용할 계정은 벤치마크 전용 테스트 계정을 새로 만들고, 측정 종료 후
`DELETE /api/v1/auth/withdraw`로 즉시 삭제해 운영 DB에 잔여 데이터를 남기지 않는다.

> 2026-07-24 라운드에서는 위 방식대로 EC2 배포 환경(`remdi.duckdns.org`)의
> `GET /api/v1/medications`에 대해 실측을 완료했다(`benchmarks/results/live_endpoint.csv`).
> 부하 전후 `docker stats`로 서버 리소스(CPU/메모리)를 확인해 서비스에 영향이 없음을 검증했다.

## 결과 재현

`benchmarks/results/bench_ab.csv`(시뮬레이션 A/B)와 `benchmarks/results/live_endpoint.csv`
(EC2 실제 엔드포인트)가 이번 라운드의 실측 원본이다. `docs/tasks/T-QUAL-1-async-benchmark.md`의
결과 표는 이 CSV를 그대로 옮긴 것이므로, 동일 커맨드를 재실행하면 (환경에 따른 절대값 편차는
있으나) 같은 경향 — async-io는 동시성이 늘어도 지연시간이 거의 일정, blocking은 동시성에
비례해 급격히 악화 — 을 재현해야 한다.
