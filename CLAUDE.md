# CLAUDE.md

이 파일은 이 리포에서 작업하는 Claude(Code)에게 주는 규칙입니다.
사람용 설명은 `docs/CONTRIBUTING_v1.0.md`를 보세요. 여기는 **에이전트가 실제로 지켜야 할 규칙만** 있습니다.
불확실하면 추측해서 진행하지 말고 사용자에게 물어보세요.

> **문서 버전**: v1.0 · **최종 수정**: 2026-07-07
> **변경 이력**
> - v1.0 (2026-07-07): `remedi_mweb_co`에서 이식하며 레포 구조·데이터 설계 원칙을 `AH_04_01`의 실제 구현(SQLAlchemy+Alembic, User/Profile 분리)에 맞춰 갱신

## 프로젝트

- ReMedi: LLM 기반 복약·건강관리 서비스
- 요구사항 원본: `docs/PRD_ReMedi_v1.1.md`(기능 요구사항), `docs/TRD_ReMedi_v1.1.md`(입력/출력/성공요건)
- 구조: 모노레포 — `frontend/`(프론트, `pages/` 구조), `app/`(백엔드, **레이어 우선** — `apis/`, `services/`, `repositories/`, `models/`, `dtos/`, `core/`, `dependencies/`. `docs/CODING_RULES_v1.0.md` 2번 참고), `ai_worker/`(AI/RAG 별도 서비스, 현재는 빈 껍데기)
- 작업 지시에 T-ID(예: T-MED-1)가 주어지면, 반드시 `docs/TRD_ReMedi_v1.1.md`에서 해당 항목의
  **입력/출력/성공요건**을 먼저 확인하고 그 조건을 만족하도록 구현하세요. 성공요건에
  없는 동작을 임의로 추가하거나, 성공요건을 스스로 완화해서 구현하지 마세요.

## 데이터 설계 원칙 — User ↔ Profile

- **User**는 계정/인증 전용(email/password/is_active 등)이고, **Profile**이 개인정보(name/gender/birthday/phone_number) + 앞으로 만들 모든 도메인 테이블의 참조 키다. 본인도 하나의 Profile로 취급한다.
- **새 도메인 테이블(복약, 일정, 채팅 등)은 `user_id`가 아니라 `profile_id`를 참조 키로 쓴다.** 나중에 한 계정이 여러 프로필(가족구성원 등)을 갖게 되어도 테이블 구조를 바꾸지 않고 확장하기 위함.
- 도메인 라우터에서 현재 사용자를 스코핑할 때는 `app/dependencies/security.py`의 `get_current_profile`(JWT의 `profile_id`로 `Profile`을 조회)을 쓴다. `get_request_user`(User 조회)는 계정 정보가 필요할 때만 쓴다.
- 배경과 상세 규칙은 `docs/decision_log_v1.0.md`, `docs/CODING_RULES_v1.0.md` 2-1번 참고.

## 백엔드 스택

- ORM: **SQLAlchemy(AsyncSession)**. Tortoise ORM이 아니다 — 리포지토리는 반드시 `AsyncSession`을 인자로 받는 메서드로 작성한다 (`app/repositories/user_repository.py`, `app/repositories/profile_repository.py` 패턴 참고).
- 마이그레이션: **Alembic** (`app/core/db/migrations/`). 모델을 바꾸면 반드시 새 리비전을 작성한다.
- DB CRUD 작업을 할 때마다 `docs/ERD_v1.0.dbml`도 같은 커밋/PR에서 함께 갱신한다 (`docs/CODING_RULES_v1.0.md` 6번).

## 브랜치 (GitFlow) — 반드시 지킬 것

- `main`, `dev`에는 **절대 직접 커밋/푸시하지 않는다.** 항상 브랜치를 만들고 PR로만 반영한다.
- 새 작업을 시작할 때:
  1. `git checkout dev && git pull origin dev`
  2. `git checkout -b feature/{T-ID}-{짧은-영문-설명}` (예: `feature/T-MED-1-pill-recognition`)
- 브랜치 종류와 용도:
  | 브랜치 | 분기 시작점 | 병합 대상 | 용도 |
  |---|---|---|---|
  | `feature/*` | `dev` | `dev` | 평소 기능 개발 (기본값, 대부분 이걸 사용) |
  | `Release/*` | `dev` | `main`+`dev` | 배포 준비 — 사용자가 명시적으로 요청할 때만 |
  | `hotfix/*` | `main` | `main`+`dev` | 운영 긴급수정 — 사용자가 명시적으로 요청할 때만 |
- `Release/*`, `hotfix/*` 브랜치는 사용자가 명확히 지시하지 않는 한 만들지 않는다.
- 이미 존재하는 다른 사람의 `feature/*` 브랜치에 임의로 커밋하지 않는다.

## 커밋 / PR

- 커밋 메시지: `type(T-ID): 설명` — type은 `feat`/`fix`/`docs`/`refactor`/`chore`
- 커밋은 작게, 자주. 관련 없는 변경을 한 커밋에 섞지 않는다.
- PR을 만들 때:
  - 제목: `[T-ID] 요약`
  - 본문에 TRD 성공요건 중 무엇을 충족했는지 체크리스트로 명시
  - **직접 머지하지 않는다.** PR 생성까지가 작업 범위이며, 병합은 사람 리뷰 후 진행된다.
- 공통모듈(`app/services/`의 소유자 지정된 파일, `docs/squad-map_v1.0.md` 참고)을 수정하는 경우, PR 설명에 `[공통모듈 변경]`을 명시하고 어떤 스쿼드에 영향을 줄 수 있는지 한 줄로 적는다.

## 작업 범위 — 넘지 말아야 할 경계

- 지시받은 T-ID/기능과 무관한 파일을 수정하지 않는다. 레이어 우선 구조라 도메인별 코드가
  `app/apis`, `app/services`, `app/repositories`, `app/models`, `app/dtos` 여러 폴더에 흩어져
  있으므로, 폴더 단위가 아니라 **파일명 접두어**로 소유권을 구분한다 (`docs/CODING_RULES_v1.0.md` 2번,
  `docs/squad-map_v1.0.md` 참고). 다른 스쿼드가 소유한 접두어의 파일을 임의로 건드리지 않는다.
- `docs/PRD_ReMedi_v1.1.md`, `docs/TRD_ReMedi_v1.1.md`는 요구사항 원본이므로, 사용자가 명시적으로
  "문서를 수정해줘"라고 하지 않는 한 내용을 바꾸지 않는다.
- `.env`, API 키, 시크릿 값을 코드/커밋/PR 설명에 절대 하드코딩하지 않는다.
  필요한 값은 `envs/example.*.env`에 키 이름만 추가한다.
- 실제 코드가 `docs/CODING_RULES_v1.0.md`/`docs/decision_log_v1.0.md`와 다른 구조로 되어 있다면, 팀 합의 없이 개인이 임의로
  작업했을 가능성이 있다. 그 구조를 그대로 따르지 말고, 먼저 사용자에게 이 문서 기준으로 재작업이 필요한지 확인한다.

## 작업 완료 전 체크리스트

작업을 "완료"로 보고하기 전에 다음을 스스로 확인한다:

1. **새 기능/엔드포인트/버그수정에는 예외 없이 테스트를 같은 커밋/PR에 포함했는가** — 테스트 없는 기능 코드는 미완성으로 간주한다. 테스트는 구현보다 먼저 작성한다(TDD, `docs/CODING_RULES_v1.0.md` §4).
2. 해당 T-ID의 TRD 성공요건을 모두 충족했는가
3. `ruff check`/`ruff format --check`, `pytest`(백엔드), `npm run lint`/`npx tsc --noEmit`(프론트)가 통과하는가
4. 변경 범위가 지시받은 T-ID/기능에 한정되어 있는가 (`git diff --stat`으로 확인)
5. 새 엔드포인트를 만들었다면 `summary`/`description`/`responses`/DTO `Field(description=...)`를 채웠는가(`docs/CODING_RULES_v1.0.md` 5번) — `/api/docs`에서 확인
6. DB 스키마를 바꿨다면 Alembic 리비전과 `docs/ERD_v1.0.dbml`을 같이 갱신했는가
7. 커밋 메시지와 브랜치명이 위 규칙을 따르는가

## 모호할 때

- T-ID가 명시되지 않은 요청, 여러 도메인에 걸친 요청, 또는 TRD에 없는 동작이 필요한
  요청을 받으면 임의로 판단해 진행하지 말고 무엇을 가정했는지 먼저 설명하고 확인받는다.
- 이미 실패한 접근을 사용자가 이전에 명시적으로 피하라고 했다면, 같은 대화 내에서 이를 번복해 다시 시도하지 않는다.

## 문서 버전 관리

- `docs/PRD_ReMedi_v1.1.md`, `docs/TRD_ReMedi_v1.1.md`, `docs/decision_log_v1.0.md`, `CLAUDE.md`,
  `docs/CODING_RULES_v1.0.md`, `docs/api_spec_core_v1_v1.1.yaml`, `docs/CONTRIBUTING_v1.0.md`,
  `docs/FRONTEND_ARCHITECTURE_v1.0.md`, `docs/ERD_v1.0.dbml` 중 하나라도
  내용을 바꾸면, 그 문서 상단(또는 파일명)의 **버전 번호를 올리고 변경 이력에 한 줄 추가**한다.
  오타 수정처럼 사소한 변경은 예외로 하되, 애매하면 사용자에게 버전을 올릴지 확인한다.
