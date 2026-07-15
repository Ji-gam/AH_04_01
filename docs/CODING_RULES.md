# CODING_RULES.md — 개발 규칙 (코드 컨벤션 단일 문서)

v2.0 · 이력: `git log docs/CODING_RULES.md`. 계층/폴더/네이밍/API·DB포맷/프론트규칙/TDD품질기준/Swagger/ERD 전부 이 문서 하나. 프로세스(브랜치/PR/로컬실행/검증커맨드)는 `CONTRIBUTING.md`, 정책/라우팅은 `AGENTS.md`.

1. 계층 구조
`Router(HTTP)→Service(판단)→Repository(데이터접근)→DB/Redis`. 절대규칙: 화살표 반대방향/건너뛰기 호출 금지(`apis/`는`services/`만,`services/`는`repositories/`만 안다 — 프론트 §3-1도 동일).
Router: 요청파싱/Service호출/응답반환만. 금지: if로 비즈니스판단, DB/쿼리 직접접근.
Service: 조건분기/여러Repository조합/외부API호출. 금지: SQL직접작성, `Request`/`status_code` 등 HTTP코드.
Repository: `AsyncSession`으로 SQLAlchemy 쿼리실행만. 금지: 비즈니스판단(if조건분기).
예제: `docs/dev/sample_code_chat/`(닉네임중복확인+AI챗봇스트리밍), `docs/dev/sample_code_recog/`(Tier2 stub패턴). 각 폴더 README대로 `PYTHONPATH=. pytest -v`.

2. 폴더 구조 (Backend)
레이어우선(종류별)구조 — 레이어당 폴더1개, 도메인별 파일이 같은 레이어 폴더에 나란히.
```
app/
├── main.py                    # FastAPI생성+라우터등록
├── core/
│   ├── config.py                   # pydantic-settings 기반 설정(§2-3)
│   ├── db/databases.py             # AsyncEngine/AsyncSession/get_db()
│   ├── db/migrations/              # Alembic(env.py,script.py.mako,versions/)
│   ├── jwt/                        # AccessToken/RefreshToken 커스텀클래스
│   ├── utils/                      # 도메인공용 순수유틸(비밀번호해싱 등)
│   └── validators/                 # Pydantic AfterValidator용 검증함수
├── dependencies/security.py        # get_request_user, get_current_profile
├── apis/v1/                        # 도메인별 파일 나란히: auth_routers.py, user_routers.py ...
├── services/                       # 도메인서비스+공용서비스 공존: auth.py, users.py, jwt.py
├── repositories/                   # user_repository.py, profile_repository.py ...
├── models/                         # SQLAlchemy2.0 선언형(Mapped/mapped_column)
│   ├── base.py                      # DeclarativeBase
│   ├── users.py                      # User=계정/인증 전용
│   └── profiles.py                   # Profile=개인정보+도메인데이터 기준(profile_id, §2-1)
├── dtos/                            # Pydantic request/response: base.py, auth.py, users.py
└── tests/                          # 레이어우선 안 따름, 도메인별: conftest.py, auth_apis/, user_apis/
```
새 도메인 추가시 각 레이어폴더에 파일 나란히 추가, 소유권=파일명접두어(`docs/SQUAD_MAP.md`).

2-1. User↔Profile 분리 (에이전트 전원 필독 — AGENTS.md §3의 canonical 원본)
User(계정/인증전용): `id,email,hashed_password,is_active,is_admin,last_login,created_at,updated_at`. 로그인자격만.
Profile(개인정보+모든 도메인테이블의 기준): `id,user_id(FK),name,gender,birthday,phone_number,relation(SELF/향후가족용),created_at,updated_at`. 본인도 Profile 1개 — 회원가입시 User와 함께 `relation=SELF` 기본Profile 자동생성.
신규 도메인테이블(복약/일정/채팅 등)은 반드시 `profile_id` 참조키 사용, `user_id` 직접참조 금지 — 가족프로필 확장시 기존 도메인테이블 구조변경 없이 확장 가능.
JWT payload에 `user_id`+`profile_id` 동시포함. 도메인라우터는 `get_current_profile`로 곧장 Profile 수신, `profile.id`로 스코핑 — `get_request_user`(User조회) 경유 불필요.

2-2. 환경변수 관리
`envs/`에 환경별 설정: 예시파일(`envs/example.local.env`,`example.prod.env`, 커밋대상)과 실값파일(`envs/.local.env`,`.prod.env`, gitignore대상).
앱/Docker Compose가 읽는 파일은 루트 `.env` 1개뿐 — 전환은 내용수정이 아니라 심볼릭링크 교체: `ln -s envs/.local.env .env`.
로컬 MySQL을 다른 프로젝트와 공유시 `DB_NAME` 충돌 가능 — `envs/.local.env`의 `DB_NAME`을 프로젝트별로 구분되게 변경.

2-3. 설정 관리
`os.getenv()` 산발 호출 금지 — `pydantic-settings`의 `BaseSettings`로 설정클래스 1개, `core/config.py`에 위치. 필수 환경변수 누락시 앱 시작시점에 즉시 에러(런타임 중 발견보다 빠름).

3. 프론트엔드 규칙
스택: React+Vite(SPA)+React Router+Service Worker(Push/오프라인캐싱). 인증: Access Token=로그인응답body로 메모리에만 보관(localStorage/sessionStorage 저장 금지, XSS방어), 요청마다 `Authorization: Bearer` 헤더. Refresh Token=백엔드가 httpOnly쿠키로 내려줌, JS직접조작 금지, `fetch`에 `credentials:"include"`만(`frontend/src/api/client.ts`).
5탭(홈/추적/상담/Info/더보기) 구성은 가안 — UI/UX영역이라 변경가능, 변경돼도 §3-1~3-5는 유효.

3-1. 계층 구조 (백엔드 §1 대응)
`Page(화면)→Hook(상태+판단)→api/함수(fetch)→서버`.
Page(`pages/`): 컴포넌트조립/레이아웃/Hook호출만. 금지: `fetch`직접호출, 복잡한 판단로직.
Hook(`hooks/`): 상태관리/조건분기/여러api함수조합. 금지: JSX반환.
api(`api/`): fetch호출/요청응답 형태변환만. 금지: 화면관련 판단.
규칙: 컴포넌트(`pages/`,`components/`)는 `fetch` 직접호출 금지 — 반드시 `api/` 함수 경유.

3-2. 폴더 구조
```
frontend/src/
├── App.tsx                    # React Router. 로그인필요 탭은 RequireAuth로 감쌈
├── pages/                      # 화면1개=폴더1개(소유권경계)
│   ├── HomePage/ TrackPage/ ChatPage/ InfoPage/ MorePage/   # 로그인후 탭
│   └── LoginPage/ SignupPage/                                 # 비로그인 공개라우트
├── components/common/           # 3개+ 페이지 재사용시만 승격(Layout,RequireAuth,DisclaimerBanner 등)
├── api/                         # 엔드포인트당 함수1개, 반드시 client.ts 경유
├── hooks/                       # 페이지전용 아닌 공용훅만(useAuth,useChatStream)
└── serviceWorker.ts
```

3-3. 상태관리 — 전역 라이브러리 도입 안함 (canonical 원본)
Redux/Zustand/React Query 도입 안함. 상태=원칙적으로 페이지로컬 `useState`. 예외=클라이언트(세션)상태뿐 — 브라우저에만 있고 DB로우 없는 값(로그인여부,토큰)만 `hooks/useAuth.tsx` Context로 공유. "생활정보 입력여부" 같은 서버상태(DB사실 반영)는 Context캐싱 금지 — 필요시 그때그때 백엔드 조회(캐싱시 동기화버그 위험).

3-4. API 연동 & 타입 (백엔드DTO 변경시 동기화 규칙의 canonical 원본)
`api/`함수+각 페이지 `loading/error/data` 3-state 동일패턴 복사. React Query 등 자동캐싱 도구 도입 안함. 타입은 `app/dtos/*.py`를 보고 `api/types.ts`에 수동동기화 — 백엔드DTO 변경 커밋/PR에 `frontend/src/api/types.ts`도 같은 PR에서 수정(§9 에러처리 규칙과 동일 취지).

3-5. 스타일링
스타일 라이브러리 아직 미도입. 새 화면=입력/출력에 필요한 최소 inline style만, 동종화면 2~3개 쌓이면 `components/common/`으로 승격+공통스타일 방향 결정. 참고: `pages/LoginPage/`,`pages/SignupPage/`. Tailwind+shadcn 도입 후 상세: `docs/FRONTEND_UI_GUIDE.md`.

3-6. 공통 모듈 소유자
소유자/대상파일의 유일 출처: `docs/SQUAD_MAP.md` §3. 소유자 지정 없이 임의수정 금지.

3-7. 요약 (정석 vs 팀 조정)
상태관리: 정석=Redux/Zustand+React Query, 조정=페이지로컬state+Context1개(`useAuth`)만.
컴포넌트구조: 정석=Atomic Design, 조정=페이지폴더 내 우선, 3+재사용시 `components/common` 승격.
API/타입: 정석=React Query+자동타입생성, 조정=수동fetch패턴+수동타입정의.
스타일: 정석=CSS-in-JS/디자인시스템, 조정=도입전(화면2~3개 쌓인 뒤 재검토).

3-8. Drill-Me 대표 트리거 사례 (메커니즘: `AGENTS.md` §4)
탭/화면구성(IA): 5탭 구성은 `docs/decision_log/`에 가안으로 남음 — 새 탭 추가/기존 탭 성격변경시 먼저 확인.
로그인이후 온보딩분기(생활정보/생체정보/삼성헬스 연동여부별 분기 등): 해당도메인 백엔드 자체가 아직 없음 — 담당자 몫, 임의설계 금지.
디자인 레퍼런스 전무 상태에서 "최소한의 톤"이 §3-5로 부족하다고 판단되면 먼저 확인.

4. TDD 품질 기준 (작업순서=RED→GREEN은 `CONTRIBUTING.md` §5)
테스트 없는 기능코드는 미완성 — Service함수1개(또는 엔드포인트/버그수정)당 최소 정상+실패 테스트 2개를 같은 PR에 포함.
Service 단위테스트는 진짜DB 없이 Fake Repository로(`docs/dev/sample_code_chat/test_nickname_service.py` 패턴).
Router는 `httpx.AsyncClient(transport=ASGITransport(app=app))`로 통합테스트만 가볍게 — 상태코드/응답형태만 확인, 로직 재검증 안함(`app/tests/auth_apis/test_signup_api.py` 패턴).
외부의존성(DB/Redis/LLM/네트워크)은 항상 Fake/Stub — 몇번 돌려도 같은 결과. Router통합테스트의 DB는 예외(`app/tests/conftest.py`가 실제 테스트DB 초기화+테스트마다 정리).
테스트 하나=동작 하나만 검증. 이름="무엇을 검증하는지"로(예:`test_signup_duplicate_email`). 정상케이스만 있는 테스트는 미완성 — 경계값/실패케이스 필수 포함.

5. API 문서화 규칙 (Swagger, canonical 원본)
`/api/docs`만 보고 엔드포인트를 바로 이해할 수 있어야 함.
라우터(`app/apis/v1/*.py`): 엔드포인트마다 `summary`(한줄요약)/`description`(동작·부수효과)/`responses={상태코드:{"description":...}}`로 실패케이스까지 명시.
DTO(`app/dtos/*.py`): 모든 필드에 `Field(description=...,examples=[...])`.
`app/main.py`: `FastAPI(title=...,summary=...,description=...,version=...)`+라우터 `tags`에 한글설명(`openapi_tags`).
`docs/dev/api_spec_core_v1_v1.1.yaml`: 실제구현과 어긋나지 않게 필요한부분만 갱신(문서버전 접미사 올림).

6. ERD 동기화 규칙 (canonical 원본)
`docs/dev/ERD.dbml`(dbdiagram.io DBML문법)=DB스키마 최신상태의 단일창구.
DB CRUD 작업(모델추가/변경, 마이그레이션 작성)마다 같은 커밋/PR에서 이 파일도 갱신+버전접미사 상향. 신규 도메인테이블 추가시 테이블+FK관계 반드시 추가.

7. 그 외 규칙
API 에러응답 형태: §11. `.env` 커밋 금지(§2-2). 로컬검증 커맨드/PR전 실행순서: `CONTRIBUTING.md` §7.

8. RAG 완성전 개발 규칙 (Tier2 stub 패턴)
RAG Retriever 필요기능인데 미완성이면: Router/Schema(API명세)는 최종형태 그대로 먼저 작성. Service내부는 규칙기반 하드코딩값 리턴 stub. RAG완성후 Service내부 구현만 교체 — Router/프론트/API명세는 무변경(§1 계층분리 덕). 참고: `docs/dev/sample_code_recog/`.
LLM/RAG 호출(`AIWorkerGateway`) 사용법 및 "이거 정말 LLM이 필요한가" 체크리스트는 `docs/dev/2026-07-15_ai_worker_gateway_guide.md` 참고.

9. 에러 처리 / 로깅 규칙 (canonical 원본)
완료기준="일단 막았다"가 아니라 "무엇이 왜 잘못됐는지 바로 알 수 있다"(사례:`docs/decision_log/`).
백엔드: 의도된 실패는 `HTTPException(detail="사람이 읽을 문장")`(또는 공용`AppException`), 문자열 그대로 노출 금지. 사용자용(한국어,간결)/로그용(영어,상세) 메시지 분리. `except: pass`로 조용히 삼키지 않음 — 의도치 않은 예외는 전파시키거나 최소 `logger.warning`/`logger.error`로 스택트레이스 남김.
프론트: FastAPI 422응답의 `detail`은 문자열 또는 배열(`[{"loc":[...],"msg":"..."}, ...]`)로 옴 — 타입분기 후 배열이면 각 항목 `loc`/`msg`를 사람이 읽을 문장으로 합침. 이 변환은 `api/client.ts` 공통파싱 1곳에서만, 각 페이지 직접파싱 금지. 화면엔 짧고 명확한 문장만, 원본에러(전체응답body,stack trace)는 `console.error`(프론트)/로거(백엔드)에 보존.
새 실패케이스(`responses=` 항목) 추가시 프론트에서 실제 트리거해 에러문구가 사람이 읽을 수 있게 나오는지 확인.

10. 코드 스타일 (백엔드)
10-1. 네이밍: 변수/함수=snake_case(`get_user_by_id`). 클래스(Pydantic DTO,SQLAlchemy Model)=PascalCase(`MedicationScheduleDTO`,`MedicationSchedule`). 상수/Enum값=UPPER_SNAKE_CASE(`MAX_RETRY_COUNT`). 파일명=snake_case(`medication_service.py`). Boolean 변수/필드=is/has/can 접두사(`is_active`,`has_consent`).
10-2. 도구(질문없이 고정): 패키지매니저=`uv`(`pyproject.toml`+`uv.lock`, pip직접설치 금지). 포맷/린트=`ruff format`+`ruff check`(line-length100). 타입체크=`mypy` 필수통과(모든 함수시그니처 타입힌트 명시). 실행타이밍/커맨드: `CONTRIBUTING.md` §7.
10-3. 주석/TODO: 스텁/미완성코드는 `# TODO(T-ID): 설명` 형태 필수(예:`# TODO(T-MED-1): OCR 후보매칭률 로직 미구현`). Task ID 없는 TODO 금지(추적불가).

11. API 응답/에러 규칙
11-1. 엔드포인트 네이밍: 경로=`/api/v1/{도메인}/{리소스}`(복수형,kebab-case, 예`/api/v1/medication/schedules`). 동사를 경로에 쓰지 않음 — HTTP메서드로 표현(`GET`조회`POST`생성`PATCH`부분수정`PUT`전체수정`DELETE`삭제). 예외: 상태변경트리거만 동사허용(`/api/v1/medication/schedules/{id}/complete`).
11-2. 요청/응답 공통포맷(고정, 신규 엔드포인트도 준수): 성공=`{"success":true,"data":{...},"message":null}`. 에러=`{"success":false,"data":null,"message":"사용자메시지","error_code":"MED_001"}`. 리스트응답은 `data`에 `{"items":[...],"total":N,"page":N}`(페이지네이션시). `error_code`={도메인3글자}_{3자리숫자}(예`AUTH_001`,`MED_002`).
11-3. 상태코드: 조회/수정성공=200. 생성성공=201. 입력값오류=400. 인증실패/토큰없음=401. 권한없음=403. 리소스없음=404. 서버내부오류=500.
11-4. 필수사항: 신규엔드포인트는 §5 기준 Swagger문서화 필수. 인증필요 엔드포인트는 `Depends(get_current_user)`또는`Depends(get_current_profile)` 명시(임의우회 금지) — 개인데이터(건강정보 등) 다루는 엔드포인트는 `profile_id` 기준 조회/기록. 로그인/회원가입/토큰재발급 응답 바디엔 `access_token`+`profile_id`만, `refresh_token`은 바디노출 금지(HttpOnly쿠키). 날짜/시간은 항상 ISO8601 UTC 문자열(`2026-07-04T10:00:00Z`), `frontend/`에서 로컬변환.

12. DB/ERD 네이밍 규칙
테이블명=snake_case복수형(`medication_schedules`). 컬럼명=snake_case(`created_at`,`profile_id`). PK=항상`id`(`mapped_column(primary_key=True)`). FK=`{참조테이블단수}_id`(SQLAlchemy`ForeignKey`, 예`profile_id`,`medication_id`). 생성/수정시각=모든모델 필수(`server_default=func.now()`/`onupdate=func.now()`, `created_at`,`updated_at`). 삭제=하드삭제 대신 소프트삭제 우선(`deleted_at` nullable). Boolean컬럼=is/has접두사(`is_active`,`has_consent`). Enum값=DB에 문자열저장,UPPER_SNAKE_CASE(`"COMPLETED"`,`"PENDING"`).
PII(개인식별정보)와 건강정보 테이블은 물리적으로 분리, FK로만 연결(§2-1). 마이그레이션은 반드시 Alembic(`uv run alembic revision --autogenerate -m "{설명}"` 후 `uv run alembic upgrade head`) — DB 수동ALTER 금지.

13. 공용 타입/상수 관리
백엔드 전체공용값(에러코드,enum,상태값 등)은 `app/core/constants.py` 한곳에서만 정의 — 같은 의미 상수를 도메인마다 재정의 금지(예: 복약상태값을 medication과 tracking에서 각자 또 만들기 금지).
새 Enum/상수 추가시 `docs/shared-glossary.md`에 한줄 등록(이름,의미,사용도메인) — 파일 없으면 신규생성.
프론트와 코드레벨 값공유 패키지 없음 — `error_code`/enum값 변경시 PR설명에 `[API 계약 변경]` 태그+프론트담당자 별도공지.
