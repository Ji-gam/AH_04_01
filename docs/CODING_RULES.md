# AH_04_01 개발 규칙

> **문서 버전**: v1.2 · **최종 수정**: 2026-07-07
> **변경 이력** (배경 설명은 `docs/decision_log.md` 참고 — 여긴 무엇이 바뀌었는지만, 최근 변경만 남김)
> - v1.2 (2026-07-07): `FRONTEND_ARCHITECTURE.md`를 3번으로 흡수, `docs/dev/`·`docs/plan/` 경로 반영, 전반적으로 배경 설명/변경 이력 축약

## 1. 계층 구조

```
Router  → Service → Repository → (DB/Redis 등)
(HTTP)    (판단)     (데이터접근)
```

**절대 규칙: 화살표 반대 방향으로도, 화살표를 건너뛰어서도 호출하지 않는다.** (`apis/`는 `services/`만, `services/`는 `repositories/`만 안다 — 2번 폴더 구조에도 동일 적용)

| 레이어 | 여기서 해도 되는 것 | 여기서 절대 하면 안 되는 것 |
| --- | --- | --- |
| Router | 요청 파싱, Service 호출, 응답 반환 | if로 비즈니스 판단, DB/쿼리 직접 접근 |
| Service | 조건 분기, 여러 Repository 조합, 외부 API 호출 | SQL 직접 작성, `Request`/`status_code` 등 HTTP 관련 코드 |
| Repository | `AsyncSession`으로 SQLAlchemy 쿼리 실행 | 비즈니스 판단(if 조건 분기) |

예제: `docs/dev/sample_code_chat/`(닉네임 중복확인 기본형 + AI 챗봇 스트리밍형), `docs/dev/sample_code_recog/`(Tier 2 stub 패턴). 각 폴더 README대로 `PYTHONPATH=. pytest -v`.

## 2. 폴더 구조 (Backend)

**레이어 우선(종류별) 구조** — 레이어(종류)당 폴더 하나, 도메인별 파일이 같은 레이어 폴더 안에 나란히 놓인다(배경: `docs/decision_log.md`).

```
app/
├── main.py                    # FastAPI 생성 + 라우터 등록
├── core/
│   ├── config.py                   # pydantic-settings 기반 설정 (2-3 참고)
│   ├── db/
│   │   ├── databases.py            # SQLAlchemy AsyncEngine, AsyncSession, get_db() 의존성
│   │   └── migrations/             # Alembic (env.py, script.py.mako, versions/)
│   ├── jwt/                        # 커스텀 JWT 토큰 클래스 (AccessToken/RefreshToken)
│   ├── utils/                      # 여러 도메인이 같이 쓰는 순수 유틸 (비밀번호 해싱 등)
│   └── validators/                 # Pydantic AfterValidator용 검증 함수
│
├── dependencies/
│   └── security.py                 # get_request_user, get_current_profile (Depends용)
│
├── apis/v1/                        # API 엔드포인트 — 도메인별 파일이 한 폴더 안에 나란히
│   ├── auth_routers.py
│   └── user_routers.py             # ... 새 도메인 추가 시 이 옆에 나란히
│
├── services/                       # 비즈니스 로직. 도메인별 서비스 + 공통 서비스가 같은 폴더에 공존
│   ├── auth.py
│   ├── users.py
│   └── jwt.py
│
├── repositories/                   # DB 접근 (SQLAlchemy AsyncSession 기반)
│   ├── user_repository.py
│   └── profile_repository.py
│
├── models/                         # SQLAlchemy 2.0 선언형 모델 (Mapped/mapped_column)
│   ├── base.py                      # DeclarativeBase
│   ├── users.py                      # User — 계정/인증 전용
│   └── profiles.py                   # Profile — 개인정보 + 도메인 데이터의 기준(profile_id, 2-1 참고)
│
├── dtos/                            # Pydantic request/response
│   ├── base.py / auth.py / users.py
│
└── tests/                          # pytest. 레이어 우선 폴더를 따르지 않고 도메인별로 모음
    ├── conftest.py                    # 테스트 DB 초기화, get_db 오버라이드
    ├── auth_apis/
    └── user_apis/
```

새 도메인(복약, 채팅 등)을 추가할 때도 각 레이어 폴더에 파일을 나란히 추가하고, 소유권은 폴더가 아니라 **파일명 접두어**로 나눕니다 (`squad-map.md` 참고).

### 2-1. 데이터 모델 설계 원칙 — User ↔ Profile 분리

- **User**(계정/인증 전용): `id`, `email`, `hashed_password`, `is_active`, `is_admin`, `last_login`, `created_at`, `updated_at`. 로그인 자격만 담당한다.
- **Profile**(개인정보 + 앞으로 만들 모든 도메인 테이블의 기준): `id`, `user_id`(FK), `name`, `gender`, `birthday`, `phone_number`, `relation`(`SELF`/향후 가족용 값), `created_at`, `updated_at`. **본인도 하나의 Profile로 취급**한다 — 회원가입 시 User와 함께 `relation=SELF`인 기본 Profile이 자동 생성된다.
- **새 도메인 테이블(복약, 일정, 채팅 등)은 반드시 `profile_id`를 참조 키로 쓴다.** `user_id`를 직접 참조하지 않는다. 이렇게 하면 한 계정이 여러 프로필(가족구성원 등)을 갖게 되는 서포터그룹 기능이 나와도, 이미 만든 도메인 테이블의 구조를 바꾸지 않고 그대로 확장할 수 있다.
- JWT payload에는 `user_id`와 `profile_id`가 함께 담긴다. 도메인 라우터는 `app/dependencies/security.py`의 `get_current_profile` 의존성으로 곧바로 `Profile`을 받아 `profile.id`로 스코핑한다 — `get_request_user`(User 조회)를 거칠 필요가 없다.
- 배경(왜 이 결정을 했는지)은 `decision_log.md` 참고.

### 2-2. 환경 변수 관리

- `envs/` 폴더에 환경별 설정 파일을 둡니다: 예시 파일(`envs/example.local.env`, `envs/example.prod.env` — 커밋 대상)과 실제 값이 든 파일(`envs/.local.env`, `envs/.prod.env` — `.gitignore` 대상).
- 앱과 Docker Compose가 실제로 읽는 파일은 프로젝트 루트의 `.env` 하나뿐입니다. 로컬/배포 환경 전환은 `.env` 내용을 직접 고치는 대신, **심볼릭 링크로 바꿔치기**합니다: `ln -s envs/.local.env .env`.
- 로컬에서 Docker 없이 개발 DB를 붙일 때, 이미 다른 프로젝트가 로컬 MySQL에 같은 `DB_NAME`을 쓰고 있을 수 있습니다 — `envs/.local.env`의 `DB_NAME`을 프로젝트별로 구분되는 이름으로 바꿔서 충돌을 피하세요.

### 2-3. 설정 관리

- `os.getenv()`를 여러 파일에서 각자 호출하지 않고, `pydantic-settings`의 `BaseSettings`로 설정 클래스 하나를 만들어 `core/config.py`에 둡니다.
- 필수 환경변수가 없으면 앱 시작 시점에 바로 에러가 나서, 실행 중간에 알아채는 것보다 훨씬 빨리 문제를 잡을 수 있습니다.

## 3. 프론트엔드 규칙

기본 스택은 React + Vite(SPA) + React Router(클라이언트 라우팅) + Service Worker(Push/오프라인 캐싱)입니다. 인증은 JWT — Access Token은 로그인 응답 body로 받아 **메모리에만** 보관하고(`localStorage`/`sessionStorage` 저장 금지, XSS 방어), 요청마다 `Authorization: Bearer` 헤더로 붙입니다. Refresh Token은 백엔드가 `httpOnly` 쿠키로 내려주므로 JS에서 직접 다루지 않고, `fetch` 호출에 `credentials: "include"`만 챙깁니다(`frontend/src/api/client.ts` 참고).

> ℹ️ 5탭(홈/추적/상담/Info/더보기) 구성은 가안입니다 — UI/UX 영역이라 바뀔 수 있고, 바뀌어도 아래 3-1~3-5 규칙은 그대로 유효합니다.

### 3-1. 계층 구조 — 백엔드 Router→Service→Repository에 대응

```
Page (화면)  →  Hook (상태 + 판단 로직)  →  api/ 함수 (fetch)  →  서버
```

| 레이어 | 여기서 해도 되는 것 | 여기서 절대 하면 안 되는 것 |
| --- | --- | --- |
| Page (`pages/`) | 컴포넌트 조립, 레이아웃, Hook 호출 | `fetch` 직접 호출, 복잡한 판단 로직 |
| Hook (`hooks/`) | 상태 관리, 조건 분기, 여러 api 함수 조합 | JSX 반환 |
| api (`api/`) | fetch 호출, 요청/응답 형태 변환 | 화면 관련 판단 |

**규칙: 컴포넌트(`pages/`, `components/`)는 `fetch`를 직접 호출하지 않는다. 반드시 `api/` 폴더 함수를 통해서만 호출한다.**

### 3-2. 폴더 구조

```
frontend/src/
├── App.tsx                    # React Router 설정. 로그인 필요한 탭은 RequireAuth로 감싼다
├── pages/                      # 화면 1개 = 폴더 1개 (소유권 경계)
│   ├── HomePage/ TrackPage/ ChatPage/ InfoPage/ MorePage/   # 로그인 후 탭
│   └── LoginPage/ SignupPage/                                 # 비로그인 공개 라우트
├── components/common/           # 3개 이상 페이지에서 재사용될 때만 승격 (Layout, RequireAuth, DisclaimerBanner 등)
├── api/                         # 엔드포인트당 함수 1개. 반드시 client.ts(공통 fetch wrapper)를 거친다
├── hooks/                       # 페이지 전용이 아닌, 여러 곳에서 쓰는 훅만 (useAuth, useChatStream)
└── serviceWorker.ts
```

### 3-3. 상태관리 — 전역 라이브러리 도입 안 함

전역 상태 라이브러리(Redux/Zustand/React Query)는 도입하지 않는다. 상태는 원칙적으로 페이지 로컬 `useState`, 예외는 **클라이언트(세션) 상태**뿐이다 — 브라우저에만 있고 DB 로우가 없는 값(로그인 여부, 토큰)만 `hooks/useAuth.tsx`의 Context로 공유한다. "생활정보 입력 여부"처럼 DB 사실을 비추는 **서버 상태**는 Context에 캐싱하지 않고 필요한 화면이 그때그때 백엔드에 물어서 받는다(캐싱 시 동기화 버그 위험).

### 3-4. API 연동 & 타입

`api/` 폴더 함수 + 각 페이지에서 `loading/error/data` 3개 state를 다루는 동일 패턴을 그대로 복사해서 씁니다. React Query 같은 자동 캐싱 도구는 도입하지 않습니다. 타입도 백엔드 `app/dtos/*.py`를 보고 `api/types.ts`에 **수동으로** 동기화합니다 — 백엔드 DTO를 바꾼 커밋/PR에 `frontend/src/api/types.ts`도 같이 고칩니다(같은 PR, 9번 에러처리 규칙과 동일한 취지).

### 3-5. 스타일링

스타일 라이브러리는 아직 도입하지 않는다. 새 화면은 **입력/출력에 필요한 최소 inline style**로만 만들고, 같은 종류의 화면이 2~3개 쌓이면 그때 `components/common/`으로 승격하고 공통 스타일 방향을 정한다. 참고 예: `pages/LoginPage/`, `pages/SignupPage/`.

### 3-6. 공통 모듈 소유자

소유자와 대상 파일은 `docs/squad-map.md` 3번 표가 유일한 출처입니다. 소유자 지정 없이 임의로 고치지 않습니다.

### 3-7. 요약

| 항목 | 정석 | 우리 팀 조정 |
| --- | --- | --- |
| 상태관리 | Redux/Zustand + React Query | 페이지 로컬 state + Context 1개(`useAuth`)만 |
| 컴포넌트 구조 | Atomic Design | 페이지 폴더 내 우선, 3+ 재사용 시 `components/common` 승격 |
| API/타입 | React Query + 자동 타입생성 | 수동 fetch 패턴 + 수동 타입 정의 |
| 스타일 | CSS-in-JS/디자인시스템 | 도입 전 — 화면 2~3개 쌓인 뒤 재검토 |

## 4. TDD 규칙

- **테스트 없는 기능 코드는 미완성이다.** Service 함수 하나(또는 엔드포인트/버그수정) 만들면, 최소 2개 테스트(정상/실패)를 **같은 PR 안에** 포함한다.
- **작업 순서는 테스트 먼저**: 모델/리포지토리/서비스/라우터를 구현하기 전에, 정상 케이스 + 실패 케이스(중복/유효성 실패/권한 없음 등) 테스트를 먼저 작성해 실패(RED)를 확인한 뒤, 구현으로 통과(GREEN)시킨다.
- Service 단위테스트는 진짜 DB 없이 가짜(Fake) Repository로 테스트한다 (`docs/dev/sample_code_chat/test_nickname_service.py` 패턴 참고).
- Router는 `httpx.AsyncClient(transport=ASGITransport(app=app))`로 통합테스트만 가볍게 — 상태코드와 응답 형태만 확인, 로직 재검증은 안 함 (`app/tests/auth_apis/test_signup_api.py` 패턴 참고).
- 테스트 작성 시 지킬 최소 원칙 (짧게):
  - 외부 의존성(DB/Redis/LLM/네트워크)은 항상 Fake/Stub으로 대체한다 — 실제 호출 없이 몇 번을 돌려도 같은 결과가 나와야 한다. Router 통합테스트의 DB는 예외 — `app/tests/conftest.py`가 실제 테스트 DB를 초기화하고 테스트마다 정리(clean)한다.
  - 테스트 하나는 동작 하나만 검증한다.
  - 테스트 이름은 "무엇을 검증하는지" 설명하는 함수명으로 짓는다 (예: `test_signup_duplicate_email`).
  - 정상 케이스만 있는 테스트는 미완성이다 — 경계값/실패 케이스를 반드시 포함한다.

## 5. API 문서화 규칙 (Swagger)

`/api/docs`만 보고 엔드포인트를 바로 이해할 수 있어야 한다.

- **라우터**(`app/apis/v1/*.py`): 각 엔드포인트에 `summary`(한 줄 요약), `description`(동작/부수효과 설명), `responses={상태코드: {"description": ...}}`로 실패 케이스까지 명시한다.
- **DTO**(`app/dtos/*.py`): 모든 필드에 Pydantic `Field(description=..., examples=[...])`를 채운다.
- **`app/main.py`**: `FastAPI(title=..., summary=..., description=..., version=...)`로 API 전체 소개를 붙이고, 라우터의 `tags`에도 한글 설명(`openapi_tags`)을 붙인다.
- **`docs/dev/api_spec_core_v1_v1.1.yaml`**: 실제 구현과 어긋나지 않는지 대조해서 필요한 부분만 갱신한다 (문서 버전 접미사를 올리며 갱신 — 6번 참고).

## 6. ERD 동기화 규칙

- `docs/dev/ERD.dbml`([dbdiagram.io](https://dbdiagram.io) DBML 문법)가 DB 스키마의 최신 상태를 나타내는 단일 창구다.
- **DB를 CRUD하는 작업(모델 추가/변경, 마이그레이션 작성)을 할 때마다 이 파일도 같은 커밋/PR에서 함께 갱신**하고 버전 접미사를 올린다. 새 도메인 테이블을 추가할 때는 테이블과 FK 관계를 반드시 추가한다.

## 7. 그 외 최소 규칙

- 커밋 메시지: `[T-ID] 설명` 형식 (예: `[T-LLM-2] 응급 키워드 필터 추가`) — Notion 스토리와 매칭용
- API 에러 응답은 항상 `{error_code, message}` 형태로 통일 (OpenAPI 명세의 `ErrorResponse` 스키마 참고)
- `.env`는 절대 커밋하지 않는다 — `envs/example.*.env`만 커밋 (2-2 참고)
- PR을 올리기 전 로컬에서 `ruff check`/`ruff format --check`, `pytest`를 미리 돌려본다 — GitHub Actions CI에서 동일하게 검사한다

## 8. RAG 완성 전 개발 규칙 (Tier 2 stub 패턴)

RAG Retriever가 필요한 기능인데 아직 RAG가 준비 안 됐다면:
- Router/Schema(API 명세)는 **최종 형태 그대로** 먼저 만든다
- Service 내부는 일단 규칙기반 하드코딩 값을 리턴하는 stub으로 채운다
- RAG가 완성되면 **Service 내부 구현만** 교체한다. Router/프론트/API 명세는 손대지 않는다(1번 계층 분리 규칙 덕분)
- 참고 예제: `docs/dev/sample_code_recog/`(Tier 2 stub 패턴 실제 코드)

## 9. 에러 처리 / 로깅 규칙

완료 기준은 "일단 막았다"가 아니라 "무엇이 왜 잘못됐는지 바로 알 수 있다"(사례: `docs/decision_log.md`).

- FastAPI 422 응답의 `detail`은 문자열 또는 배열(`[{"loc": [...], "msg": "..."}, ...]`)로 온다 — **먼저 타입을 분기**해서, 배열이면 각 항목의 `loc`/`msg`를 사람이 읽을 문장으로 합친다. 이 변환은 `api/client.ts`의 공통 파싱 로직 한 곳에서만 하고, 각 페이지가 직접 파싱하지 않는다.
- 화면엔 짧고 명확한 문장만, 원본 에러(전체 응답 body, stack trace)는 `console.error`(프론트)/로거(백엔드)에 그대로 남긴다.
- **백엔드**: 의도된 실패는 `HTTPException(detail="사람이 읽을 문장")`. 의도치 않은 예외는 `except Exception: pass`로 삼키지 않고 전파시키거나 로그에 스택트레이스를 남긴다.
- 새 실패 케이스(`responses=` 항목)를 추가할 때마다 프론트에서 실제로 트리거해 에러 문구가 사람이 읽을 수 있게 나오는지 확인한다.
