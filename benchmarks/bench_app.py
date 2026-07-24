"""T-QUAL-1 비동기 처리 벤치마크용 격리 앱.

`app/main.py`(실서비스)와 완전히 분리된 소형 FastAPI 앱이다. 실제 CLOVA OCR/OpenAI
호출 대신 `asyncio.sleep`/`time.sleep`으로 "외부 I/O 대기시간"을 시뮬레이션해서,
동일한 지연시간 프로파일에서 async 처리 방식에 따라 동시 요청 처리량이 어떻게
달라지는지를 격리된 환경에서 재현 가능하게 측정한다.

왜 시뮬레이션인가 (docs/tasks/T-QUAL-1-async-benchmark.md 참고):
- 실제 CLOVA/OpenAI 호출은 비용이 들고 네트워크 변동성 때문에 재현 가능한 벤치마크가 안 된다.
- OCR+LLM 체인(F-DOC-1)의 지연 구성요소(OCR 호출 1회 + LLM 호출 1회)를 D초 대기 × N회로 근사한다.
- 기본값 D=0.1s, N=3 -> 총 300ms. 실제 CLOVA/OpenAI 호출의 대략적 평균 지연 오더를 반영한 값이며,
  --delay/--steps 로 조정 가능하다.

세 가지 변형:
- /bench/async-io   : async def + await asyncio.sleep(D) x N  -- 올바른 async I/O 패턴
- /bench/blocking   : async def + time.sleep(D) x N            -- 이벤트 루프를 막는 안티패턴
                       (예: async 라우트 안에서 실수로 동기 SDK를 그대로 호출한 경우를 재현)
- /bench/threadpool : def(동기) + time.sleep(D) x N             -- FastAPI가 스레드풀로 위임하는 경우
"""

import asyncio
import os
import time

from fastapi import FastAPI, Query

app = FastAPI(title="T-QUAL-1 Async Benchmark App")

DEFAULT_DELAY = float(os.getenv("BENCH_DELAY_SECONDS", "0.1"))
DEFAULT_STEPS = int(os.getenv("BENCH_STEPS", "3"))


@app.get("/bench/async-io")
async def async_io(
    delay: float = Query(DEFAULT_DELAY, description="스텝당 시뮬레이션 I/O 대기시간(초)"),
    steps: int = Query(DEFAULT_STEPS, description="OCR/LLM 등 순차 I/O 호출 횟수"),
):
    """올바른 async 패턴: 대기 중 이벤트 루프를 다른 요청에 양보한다."""
    for _ in range(steps):
        await asyncio.sleep(delay)
    return {"variant": "async-io", "delay": delay, "steps": steps}


@app.get("/bench/blocking")
async def blocking(
    delay: float = Query(DEFAULT_DELAY, description="스텝당 시뮬레이션 I/O 대기시간(초)"),
    steps: int = Query(DEFAULT_STEPS, description="OCR/LLM 등 순차 I/O 호출 횟수"),
):
    """안티패턴: async 라우트인데 동기 sleep으로 이벤트 루프 자체를 막는다."""
    for _ in range(steps):
        time.sleep(delay)
    return {"variant": "blocking", "delay": delay, "steps": steps}


@app.get("/bench/threadpool")
def threadpool(
    delay: float = Query(DEFAULT_DELAY, description="스텝당 시뮬레이션 I/O 대기시간(초)"),
    steps: int = Query(DEFAULT_STEPS, description="OCR/LLM 등 순차 I/O 호출 횟수"),
):
    """동기 def 라우트: FastAPI가 자동으로 스레드풀(기본 40개)에 위임한다."""
    for _ in range(steps):
        time.sleep(delay)
    return {"variant": "threadpool", "delay": delay, "steps": steps}
