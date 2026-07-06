# AH_04_01 개발 시작 전 규칙 (Backend)

> **문서 버전**: v1.0 · **최종 수정**: 2026-07-07
> **변경 이력**
> - v1.0 (2026-07-07): `remedi_mweb_co`에서 이식하며 `AH_04_01`의 실제 구현(SQLAlchemy+Alembic, User/Profile 분리, API 문서화 규칙, ERD 동기화 규칙)에 맞춰 전면 재작성

## 1. 계층 구조 — 이것만 지켜도 꼬임의 80%가 사라집니다

```
Router  → Service → Repository → (DB/Redis 등)
(HTTP)    (판단)     (데이터접근)
```

**절대 규칙: 화살표 반대 방향으로도, 화살표를 건너뛰어서도 호출하지 않는다.**

| 레이어 | 여기서 해도 되는 것 | 여기서 절대 하면 안 되는 것 |
| --- | --- | --- |
| Router | 요청 파싱, Service 호출, 응답 반환 | if로 비즈니스 판단, DB/쿼리 직접 접근 |
| Service | 조건 분기, 여러 Repository 조합, 외부 API 호출 | SQL 직접 작성, `Request`/`status_code` 등 HTTP 관련 코드 |
| Repository | `AsyncSession`으로 SQLAlchemy 쿼리 실행 | 비즈니스 판단(if 조건 분기) |

이렇게 나누는 이유: Router가 Service만 알고 Service 내부 구현을 모르면, 나중에 DB를 다른 걸로 바꿔도 Router/Service 코드는 한 줄도 안 바뀝니다.

실제로 동작하는 예제가 `docs/sample_code_chat/`(닉네임 중복확인 기본형 + AI 챗봇 실시간 스트리밍형)와 `docs/sample_code_recog/`(Tier 2 stub 패턴 조합형)에 있습니다. 각 폴더 README대로 `PYTHONPATH=. pytest -v`로 직접 돌려보고 시작하세요.

이 규칙은 아래 2번의 폴더 구조에도 그대로 적용됩니다 — `apis/`의 라우터 파일이 `services/`의 서비스 파일만 알고, `services/`의 서비스 파일이 `repositories/`의 저장소 파일만 알아야 합니다.

## 2. 폴더 구조 (Backend)

**레이어 우선(종류별) 구조**입니다. 종류(레이어)당 폴더 하나이며, 도메인별 파일들이 같은 레이어 폴더 안에 나란히 놓입니다. 도메인이 많아지면 폴더가 잘게 쪼개져 코드 스타일이 제각각으로 갈릴 위험과, 레이어 우선이 같은 폴더 안 옆 파일을 보고 패턴을 따라 하기 쉽다는 점(사람 개발자뿐 아니라 Claude 같은 AI 에이전트가 코드를 대신 작성할 때도 동일)을 이유로 팀이 의도적으로 이 구조를 택했습니다.

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
- 배경(왜 이 결정을 했는지)은 `decision_log_v1.0.md` 참고.

### 2-2. 환경 변수 관리

- `envs/` 폴더에 환경별 설정 파일을 둡니다: 예시 파일(`envs/example.local.env`, `envs/example.prod.env` — 커밋 대상)과 실제 값이 든 파일(`envs/.local.env`, `envs/.prod.env` — `.gitignore` 대상).
- 앱과 Docker Compose가 실제로 읽는 파일은 프로젝트 루트의 `.env` 하나뿐입니다. 로컬/배포 환경 전환은 `.env` 내용을 직접 고치는 대신, **심볼릭 링크로 바꿔치기**합니다: `ln -s envs/.local.env .env`.
- 로컬에서 Docker 없이 개발 DB를 붙일 때, 이미 다른 프로젝트가 로컬 MySQL에 같은 `DB_NAME`을 쓰고 있을 수 있습니다 — `envs/.local.env`의 `DB_NAME`을 프로젝트별로 구분되는 이름으로 바꿔서 충돌을 피하세요.

### 2-3. 설정 관리

- `os.getenv()`를 여러 파일에서 각자 호출하지 않고, `pydantic-settings`의 `BaseSettings`로 설정 클래스 하나를 만들어 `core/config.py`에 둡니다.
- 필수 환경변수가 없으면 앱 시작 시점에 바로 에러가 나서, 실행 중간에 알아채는 것보다 훨씬 빨리 문제를 잡을 수 있습니다.

## 3. 폴더 구조 (Frontend)

> 상세 협업 규칙은 `FRONTEND_ARCHITECTURE_v1.0.md`(이 문서의 프론트엔드 짝 문서) 참고.

```
frontend/src/
├── App.tsx                  # React Router 설정 (5탭: 홈/추적/상담/Info/더보기)
├── pages/                    # 탭 1개 = 폴더 1개 (소유권 경계)
│   ├── HomePage/ / TrackPage/ / ChatPage/ / InfoPage/ / MorePage/
├── components/common/         # 3개 이상 페이지에서 재사용될 때만 승격
├── api/                       # 백엔드 호출 함수. 엔드포인트와 파일을 1:1로 맞춤
├── hooks/                      # 페이지 전용이 아닌, 여러 곳에서 쓰는 훅만
└── serviceWorker.ts
```

**규칙: 컴포넌트(`pages/`, `components/`)는 `fetch`를 직접 호출하지 않는다. 반드시 `api/` 폴더 함수를 통해서만 호출한다.**

## 4. TDD 규칙

- **테스트 없는 기능 코드는 미완성이다.** Service 함수 하나(또는 엔드포인트/버그수정) 만들면, 최소 2개 테스트(정상/실패)를 **같은 PR 안에** 포함한다.
- **작업 순서는 테스트 먼저**: 모델/리포지토리/서비스/라우터를 구현하기 전에, 정상 케이스 + 실패 케이스(중복/유효성 실패/권한 없음 등) 테스트를 먼저 작성해 실패(RED)를 확인한 뒤, 구현으로 통과(GREEN)시킨다.
- Service 단위테스트는 진짜 DB 없이 가짜(Fake) Repository로 테스트한다 (`docs/sample_code_chat/test_nickname_service.py` 패턴 참고).
- Router는 `httpx.AsyncClient(transport=ASGITransport(app=app))`로 통합테스트만 가볍게 — 상태코드와 응답 형태만 확인, 로직 재검증은 안 함 (`app/tests/auth_apis/test_signup_api.py` 패턴 참고).
- 테스트 작성 시 지킬 최소 원칙 (짧게):
  - 외부 의존성(DB/Redis/LLM/네트워크)은 항상 Fake/Stub으로 대체한다 — 실제 호출 없이 몇 번을 돌려도 같은 결과가 나와야 한다. Router 통합테스트의 DB는 예외 — `app/tests/conftest.py`가 실제 테스트 DB를 초기화하고 테스트마다 정리(clean)한다.
  - 테스트 하나는 동작 하나만 검증한다.
  - 테스트 이름은 "무엇을 검증하는지" 설명하는 함수명으로 짓는다 (예: `test_signup_duplicate_email`).
  - 정상 케이스만 있는 테스트는 미완성이다 — 경계값/실패 케이스를 반드시 포함한다.

## 5. API 문서화 규칙 (Swagger)

`/api/docs`에서 팀원 누구나 엔드포인트를 열어보고 바로 이해할 수 있어야 합니다.

- **라우터**(`app/apis/v1/*.py`): 각 엔드포인트에 `summary`(한 줄 요약), `description`(동작/부수효과 설명), `responses={상태코드: {"description": ...}}`로 실패 케이스까지 명시한다.
- **DTO**(`app/dtos/*.py`): 모든 필드에 Pydantic `Field(description=..., examples=[...])`를 채운다.
- **`app/main.py`**: `FastAPI(title=..., summary=..., description=..., version=...)`로 API 전체 소개를 붙이고, 라우터의 `tags`에도 한글 설명(`openapi_tags`)을 붙인다.
- **`docs/api_spec_core_v1_v1.1.yaml`**: 실제 구현과 어긋나지 않는지 대조해서 필요한 부분만 갱신한다 (문서 버전 접미사를 올리며 갱신 — 6번 참고).

## 6. ERD 동기화 규칙

- `docs/ERD_v1.0.dbml`([dbdiagram.io](https://dbdiagram.io) DBML 문법)가 DB 스키마의 최신 상태를 나타내는 단일 창구입니다.
- **DB를 CRUD하는 작업(모델 추가/변경, 마이그레이션 작성)을 할 때마다 이 파일도 같은 커밋/PR에서 함께 갱신**하고 버전 접미사를 올린다.
- 다른 팀원이 이 ERD를 보고 자기 기능에서 남의 테이블(예: `profile_id`)을 참조/저장하기 때문에, 최신 상태 유지가 필수입니다. 새 도메인 테이블을 추가할 때 이 파일에 테이블과 FK 관계를 반드시 추가하세요.

## 7. 그 외 최소 규칙

- 커밋 메시지: `[T-ID] 설명` 형식 (예: `[T-LLM-2] 응급 키워드 필터 추가`) — Notion 스토리와 매칭용
- API 에러 응답은 항상 `{error_code, message}` 형태로 통일 (OpenAPI 명세의 `ErrorResponse` 스키마 참고)
- `.env`는 절대 커밋하지 않는다 — `envs/example.*.env`만 커밋 (2-2 참고)
- PR을 올리기 전 로컬에서 `ruff check`/`ruff format --check`, `pytest`를 미리 돌려본다 — GitHub Actions CI에서 동일하게 검사한다

## 8. RAG 완성 전 개발 규칙 (Tier 2 stub 패턴)

RAG Retriever가 필요한 기능인데 아직 RAG가 준비 안 됐다면:
- Router/Schema(API 명세)는 **최종 형태 그대로** 먼저 만든다
- Service 내부는 일단 규칙기반 하드코딩 값을 리턴하는 stub으로 채운다
- RAG가 완성되면 **Service 내부 구현만** 교체한다. Router/프론트/API 명세는 손대지 않는다
- 이게 가능한 이유는 1번 규칙(계층 분리)을 지켰기 때문
- 참고 예제: `docs/sample_code_recog/`(Tier 2 stub 패턴 실제 코드)
