# AI Healthcare Project Template

이 프로젝트는 AI 모델 추론(Inference) 워커와 FastAPI API 서버를 통합한 서비스 템플릿입니다. 
현대적인 Python 패키지 관리 도구인 `uv`와 컨테이너화 도구인 `Docker`를 활용하여 일관된 개발 및 배포 환경을 제공합니다.

---

## 🚀 주요 특징

- **FastAPI Framework**: 고성능 비동기 API 서버 구현.
- **AI Worker**: 모델 추론 및 학습 작업을 API 서버와 분리하여 처리.
- **UV Package Manager**: 매우 빠른 의존성 설치 및 가상환경 관리.
- **SQLAlchemy(AsyncSession) + Alembic**: 비동기 방식의 데이터베이스 모델링·쿼리 관리 및 마이그레이션.
- **Docker-Compose**: MySQL, Redis, Nginx를 포함한 전체 서비스 스택을 한 번에 실행.
- **CI/CD Scripts**: 코드 포맷팅(Ruff), 타입 체크(Mypy), 테스트(Pytest)를 위한 자동화 스크립트 제공.

---

## 📂 프로젝트 구조

```text
.
├── ai_worker/          # AI 모델 추론 및 학습 관련 코드 (Worker)
│   ├── core/           # 워커 설정 및 로거
│   ├── models/         # AI 모델 파일 보관 (PyTorch 등)
│   ├── tasks/          # 실제 처리할 작업 정의
│   └── main.py         # 워커 진입점
├── app/                # FastAPI 서버 코드
│   ├── apis/           # API 라우터 (v1 버전 관리)
│   ├── core/           # 서버 설정 (pydantic-settings), DB 설정, JWT, Validator 등 핵심 기능
│   ├── dtos/           # 데이터 전송 객체 (Pydantic models)
│   ├── models/         # DB 테이블 정의
│   ├── services/       # 비즈니스 로직
│   └── main.py         # FastAPI 애플리케이션 진입점
├── envs/               # 환경 변수 설정 파일 (.env)
├── infra/              # 인프라 설정 관련 디렉터리
│   ├── docker/         # Docker Compose 설정 (운영용)
│   └── nginx/          # Nginx 설정 파일 (리버스 프록시)
├── scripts/            # 배포 및 CI용 쉘 스크립트
├── docker-compose.yml  # 로컬 개발용 서비스 실행 설정
└── pyproject.toml      # uv 기반 의존성 관리 설정
```

---

## ⚙️ 사전 준비 사항

- **Python**: 3.13 이상 (로컬 개발 환경용)
- **UV**: Python 패키지 매니저 ([설치 가이드](https://github.com/astral-sh/uv))
- **Docker & Docker-Compose**: 전체 서비스 실행용

---

## 🛠️ 설치 및 설정

### 1. 가상환경 구축 및 의존성 설치

`uv`를 사용하여 프로젝트에 필요한 패키지를 설치합니다.

```bash
# 의존성 설치 (가상환경 자동 생성)
uv sync

# 특정 그룹의 의존성만 설치하려는 경우
uv sync --group app  # API 서버용
uv sync --group ai   # AI 워커용
```

### 2. 환경 변수 설정

`envs/` 디렉토리에 있는 예시 파일을 복사하여 `.env` 파일을 생성합니다.
- 로컬용 
    ```bash
    cp envs/example.local.env envs/.local.env
    ```
- 배포용 
    ```bash
    cp envs/example.prod.env envs/.prod.env
    ```

생성된 `env` 파일 내의 환경변수들은 프로젝트 상황에 맞게 수정하세요.

---

## 🏃 실행 방법

### 1. 로컬 및 개발 환경

#### Docker Compose로 전체 스택 실행

모든 서비스(API, Worker, DB, Redis, Nginx)를 한 번에 실행합니다.

```bash
docker-compose up -d --build
```

실행 후 다음 주소로 접속 가능합니다:
- **API 서버**: [http://localhost/api/docs](http://localhost/api/docs) (Swagger UI)
- **Nginx**: 80 포트를 통해 API 서버로 요청을 전달합니다.

#### ⚠️ 데이터 시딩 (최초 1회)

`docker compose up`은 `alembic upgrade head`로 테이블만 생성할 뿐, 그 안의 데이터까지 채워주지는
않습니다. `mysql_data` 볼륨이 없는 새 환경(신규 팀원 로컬, 새 dev/prod DB)에서는 필요에 따라
아래 스크립트를 한 번 실행하세요. 볼륨이 살아있는 한(`docker compose down -v`로 지우지 않는 한)
컨테이너를 껐다 켜도 다시 실행할 필요는 없습니다.

```bash
# 음식-약물 상호작용 참조 테이블 (식약처 가이드북 기반) — 매칭 기능이 실제로 동작하려면 필수
docker compose exec fastapi uv run python -m app.scripts.seed_food_drug_interaction

# DUR(의약품안전사용서비스) 참조 테이블 — app/database/drugs_full.db(공공데이터포털 API 24종
# 전수 수집본, scripts/drug_info_sync/orchestrate_pipeline.py)가 있어야 실행 가능
docker compose exec fastapi uv run python -m app.scripts.seed_dur

# 개발/테스트용 데모 계정 3개 + 습관·복약·알림·AI상담 더미 데이터 — 기능 화면을 바로 확인하고 싶을 때(선택)
docker compose exec fastapi uv run python -m app.scripts.seed_demo_data
```

세 스크립트 모두 재실행해도 안전합니다(이미 있는 데이터는 건너뜀 — 단, `seed_food_drug_interaction`과
`seed_dur`은 참조 테이블 전체를 지우고 다시 채우는 방식으로 "안전"합니다. 데모 계정과 달리 정적
참조 데이터라 증분 갱신할 이유가 없기 때문).

`app/models/dur.py`에 새 컬럼/테이블을 추가하는 마이그레이션(예: `0027_expand_dur_tables.py`)이
있는 경우, `seed_dur`가 새 컬럼까지 채우려면 **먼저 `alembic upgrade head`로 스키마를 반영한
뒤에** `seed_dur`를 실행해야 합니다. `docker compose up`은 fastapi 컨테이너 기동 시 항상
`alembic upgrade head`를 자동으로 실행하므로, 컨테이너를 재기동(`docker compose up -d --build
fastapi` 또는 재시작)하면 스키마는 이미 최신입니다 — 그다음 위 `seed_dur` 커맨드만 실행하면 됩니다.

#### 🩹 (컨테이너 없이) 로컬 venv에서 직접 alembic/seed 실행하기

컨테이너 재빌드 없이 빠르게 반복 확인하고 싶을 때는 호스트에서 직접 실행할 수도 있습니다.

```bash
# alembic/asyncmy 등은 app 그룹에 있다
uv sync --group app

# .env의 DB_HOST=mysql은 "컨테이너 안에서 mysql 컨테이너를 찾기 위한" 값이라, 호스트에서 직접
# 실행할 땐 mysql이라는 호스트명을 못 찾는다. DB_EXPOSE_PORT로 열려있는 localhost로 덮어써야 한다.
DB_HOST=localhost uv run --group app python -m alembic upgrade head
DB_HOST=localhost uv run --group app python -m app.scripts.seed_dur
```

**⚠️ `alembic upgrade head`가 `Table 'xxx' already exists`로 실패하는 경우**: `alembic_version`
테이블의 기록과 실제 DB 스키마가 어긋나 있다는 뜻입니다(예: 과거에 다른 방식으로 테이블이
만들어졌거나, 마이그레이션 적용 후 버전 기록이 누락된 경우). 아래로 실제 상태를 먼저 확인하세요.

```bash
DB_HOST=localhost uv run --group app python -m alembic current   # 기록된 리비전 확인
DB_HOST=localhost uv run --group app python -c "
import asyncio
from app.core.db.databases import AsyncSessionLocal
from sqlalchemy import text
async def main():
    async with AsyncSessionLocal() as s:
        r = await s.execute(text('SHOW TABLES'))
        print(sorted(row[0] for row in r.fetchall()))
asyncio.run(main())
"
```

실제 테이블 목록이 기록된 리비전보다 앞서 있다면(= 스키마는 이미 반영됐는데 기록만 뒤처짐),
실제 상태와 일치하는 리비전으로 먼저 `stamp`한 뒤 `upgrade head`를 실행하세요.

```bash
DB_HOST=localhost uv run --group app python -m alembic stamp <실제_상태와_일치하는_리비전>
DB_HOST=localhost uv run --group app python -m alembic upgrade head
```

#### ⚠️ RAG 벡터 시딩 (최초 1회, 팀원 각자 로컬에서)

챗봇 검색에 쓰는 벡터 저장소(`ai_worker/chroma_data/`)는 **git에 없습니다**(수백 MB 바이너리).
논문 JSON/OCR 마크다운은 `ai_worker/source/`에 커밋돼 있지만, **DUR/e약은요 CSV 8개는
더 이상 커밋되지 않습니다** — MySQL이 원본이고(`app/scripts/seed_dur.py`가 옮겨놨습니다),
빌드 시점마다 최신 데이터로 새로 뽑아옵니다. 그래서 MySQL DUR 시딩(위 "DUR 데이터 시딩"
참고)을 먼저 끝내야 합니다.

**API 키도, 과금도, 네트워크도 필요 없습니다.** 임베딩 모델을 로컬에 내려받아 색인도 질의도
직접 돌립니다. 몇 번을 다시 만들어도 공짜라 마음껏 실험하세요.

```bash
# 0. MySQL에 DUR 데이터가 이미 있어야 한다(uv run python -m app.scripts.seed_dur, 위 참고).

# 1. AI 워커 의존성 — 이 프로젝트는 [dependency-groups]를 쓰므로 --group이다.
#    `--all-extras`는 아무 그룹도 안 잡고 나머지를 지워버린다(실제로 당함).
uv sync --group ai

# 2. MySQL의 DUR/e약은요 데이터를 드롭 폴더 CSV로 뽑아온다(source/에 8개 파일 생성/갱신).
uv run python -m ai_worker.scripts.export_source_from_mysql

# 3. 뭐가 색인될지 먼저 본다 (색인은 안 함)
uv run python -m ai_worker.ingest --scan

# 4. 색인. 첫 실행은 임베딩 모델(e5-large, 약 2GB)을 내려받아 5~15분 걸린다.
uv run python -m ai_worker.ingest

# 5. 검증 — 실제 질문을 던져 팀과 같은 결과가 나오는지 확인한다.
uv run python -m ai_worker.scripts.verify_rag
```

5번이 전부 OK면 끝입니다. 기대 결과가 스크립트에 박혀 있어 내 로컬이 팀과 같은지 눈으로
맞춰볼 수 있습니다. **건수가 아니라 질문으로 확인하는 이유**: 색인은 "몇 건 넣었다"고 보고하지만
그게 검색이 된다는 뜻은 아닙니다. 메타데이터 키가 하나 틀리면 문서는 들어가 있는데 영원히
안 뽑히고, 실제로 그런 상태로 오래 굴러간 적이 있습니다.

> 모델은 서빙 프로세스가 1.1GB를 물고 있고, 기동 시 약 10초를 들여 미리 올립니다
> (`initialize_rag`). 안 그러면 그 10초를 첫 질문한 사용자가 냅니다.

**DUR/e약은요 데이터를 갱신하려면** MySQL을 다시 시딩하고(0번) 2번부터 다시 돌리면 됩니다.
**그 외 RAG 재료(논문/가이드 문서 등)를 추가하려면** `ai_worker/source/`에 파일을 넣고 4번을
다시 돌리면 됩니다. 등록 절차는 없습니다 — 폴더에 있으면 색인됩니다(`.csv` / `.json` / `.md`
/ `.pdf`). RAG 재료가 아닌 것(SQL 조회용 표 등)은 여기 두지 않습니다. 자세한 규칙은
`ai_worker/ingest/__init__.py`와 `ai_worker/source/_tuning.yaml` 참고.

재색인은 안 바뀐 문서를 콘텐츠 해시로 걸러 건너뛰므로(`SQLRecordManager`) 몇 번을 돌려도
안전하고 빠릅니다. 청킹 규칙을 바꿔서 전부 다시 임베딩해야 할 때만 `--force`를 씁니다.

#### 로컬에서 개별 실행 (개발용)

**FastAPI 서버 실행:**
```bash
uv run uvicorn app.main:app --reload
# or
docker compose up -d --build app
```

**AI Worker 실행:**
```bash
uv run python -m ai_worker.main
# or
docker compose up -d --build ai_worker
```

### 2. EC2 배포 환경 (Production)

제공된 쉘 스크립트를 사용하여 AWS EC2 환경에 이미지를 빌드, 푸시 및 배포할 수 있습니다.

#### 사전 준비
- EC2 인스턴스 (Ubuntu 권장)
- SSH 키 페어 (`~/.ssh/` 경로에 위치)
- 도커 허브(Docker Hub) 계정 및 Personal Access Token
- 배포용 환경 변수 설정 (`envs/.prod.env`)
- 도메인 구매 (Gabia, GoDaddy, AWS Route53 등)

#### 자동 배포 스크립트 실행
`scripts/deployment.sh`는 도커 이미지 빌드, 레포지토리 푸시, EC2 접속 및 컨테이너 실행 과정을 자동화합니다.

```bash
chmod +x scripts/deployment.sh
./scripts/deployment.sh
```
스크립트 실행 시 다음 정보를 입력해야 합니다:
1. 도커 허브 계정 정보 (Username, PAT)
2. 이미지를 업로드할 레포지토리 이름
3. 배포할 서비스 선택 (FastAPI, AI-Worker) 및 버전(Tag)
4. SSH 키 파일명 및 EC2 IP 주소
5. https 사용여부
   - 5-1. https인 경우 도메인 추가 입력  

#### SSL(HTTPS) 설정 (Certbot)
도메인을 연결하고 HTTPS를 적용하려면 `scripts/certbot.sh`를 사용합니다.

```bash
chmod +x scripts/certbot.sh
./scripts/certbot.sh
```
1. 도메인 주소 및 이메일 입력
2. SSH 키 파일명 및 EC2 IP 주소 입력
3. Let's Encrypt를 통한 인증서 발급 및 Nginx 설정 자동 갱신 적용

---

## 🧪 테스트 및 품질 관리

제공된 스크립트를 사용하여 코드의 품질을 검증할 수 있습니다.

```bash
# 테스트 실행
./scripts/ci/run_test.sh

# 코드 포맷팅 확인 (Ruff)
./scripts/ci/code_fommatting.sh

# 정적 타입 검사 (Mypy)
./scripts/ci/check_mypy.sh
```

---

## 📝 개발 가이드

- **API 추가**: `app/apis/v1/` 아래에 새로운 라우터 파일을 생성하고 `app/apis/v1/__init__.py`에 등록하세요.
- **DB 모델 추가**: `app/models/`에 SQLAlchemy 2.0 선언형 모델(`Mapped`/`mapped_column`)을 정의하고, `alembic revision --autogenerate`로 마이그레이션을 작성하세요. 같은 커밋/PR에서 `docs/dev/ERD.dbml`도 갱신합니다(`docs/CODING_RULES.md` 6번).
- **AI 로직 추가**: `ai_worker/tasks/`에 새로운 처리 로직을 작성하고 `ai_worker/main.py`에서 호출하도록 구성하세요.

---

## 📚 문서 지도

이 레포의 규칙/설계 문서는 "얼마나 자주 참조해야 하는지"에 따라 나뉩니다.

| 단계 | 문서 | 언제 보는가 |
| --- | --- | --- |
| 1. 진입(매 세션) | `AGENTS.md`(`CLAUDE.md`는 여기로의 리다이렉트) | 작업 시작 전 항상 |
| 2. 참조(필요할 때) | `docs/CONTRIBUTING.md`, `docs/TROUBLESHOOTING.md`, `docs/CODING_RULES.md`, `docs/FRONTEND_UI_GUIDE.md`, `docs/decision_log/`, `docs/SQUAD_MAP.md` | T-ID 작업, 구조/소유권 확인, "왜 이렇게 됐는지" 찾을 때 |
| 3. 개발설계 산출물 | `docs/dev/ERD.dbml`, `docs/dev/api_spec_core_v1_v1.1.yaml`, `docs/dev/sample_code_chat/`, `docs/dev/sample_code_recog/` | DB/스키마 변경, 새 도메인 구현 시 참고 예제 |
| 4. 기획 원본 스냅샷 (수정 금지) | `docs/plan/PRD_ReMedi_v1.1.md`, `docs/plan/TRD_ReMedi_v1.1.md` | T-ID의 입력/출력/성공요건 확인 |

문서 버전 관리: 파일명 고정, 내용 변경 시 헤더 버전만 올림(이력은 `git log`).
