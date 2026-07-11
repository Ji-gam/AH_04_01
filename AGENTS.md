# AGENTS.md — ReMedi 프로젝트 단일 진입점

> **문서 버전**: v1.1 · **최종 수정**: 2026-07-12
> **변경 이력**
> - v1.0 (2026-07-08): `CLAUDE.md`+`AGENT_PLAYBOOK.md`+`.agents/`+`.antigravity/`로 흩어져 있던 하네스 문서를
>   이 파일 하나로 통합. 상세 절차는 12번 "참고 문서 지도"의 위성 문서로 분리(배경: `docs/decision_log/2026-07-08.md`)
> - v1.1 (2026-07-12): §8 면책조항 정책을 "전 응답 강제"에서 "의료 관련 조건부"로 정정(코드 실동작에 맞춤, 근거: `docs/decision_log/2026-07-12-disclaimer-conditional.md`)

이 문서는 이 레포에서 작업하는 **모든 에이전트(사람 포함)가 매 세션 읽는 단일 진입점**이다. `CLAUDE.md`는 이 문서를 가리키는 리다이렉트일 뿐이다. 불확실하면 추측해서 진행하지 말고 사용자에게 물어본다.

---

## 0. 절대 원칙 (이 5줄이 전부입니다)

1. **자신에게 배정된 Task Contract(`docs/tasks/T-XXX-N.md`)에 적힌 "허용 경로" 안의 파일만 수정한다.** 그 밖의 파일은 존재 확인 외에 절대 열거나 고치지 않는다.
2. **작업 시작 전 확인 질문을 최소화한다.** 아래 "8. 이미 결정된 것"과 배정된 Task Contract만으로 진행하고, 부족하면 합리적으로 가정한 뒤 완료 보고서에 "가정(Assumptions)"으로 남긴다.
3. **"8. 반드시 멈추고 물어야 하는 경우"에 해당할 때만 중단하고 보고한다.** 그 외 판단(변수명, 내부 함수 분리, 에러 메시지 문구 등)은 스스로 결정한다. 단 사람이 `STOP`을 입력하면 즉시 멈추고 현재 상태를 보고한다(`docs/SESSION_START.md`).
4. **공유 구역**(`app/core/`, `app/dependencies/`, `ai_worker/core/`, `envs/` 등 스키마·타입·계약 파일)**은 Task Contract에 명시적으로 허용되지 않는 한 절대 수정하지 않는다.** 완료 보고서에 "공유 파일 변경 필요"로만 남긴다.
5. **작업 시작 시 `docs/tasks/_active.json`에 Task ID와 브랜치명을 등록하고, 종료 시 해제한다** (에이전트 간 충돌 방지 claim 파일).

---

## 1. 디렉토리 = 소유권 경계

레이어별 폴더 구조. 도메인 구분은 폴더가 아니라 **파일명**으로 한다.

```
app/            apis/v1/ dtos/ services/ repositories/ models/ tests/
                dependencies/ core/                    # [공유 구역]
ai_worker/      tasks/ schemas/  |  core/              # [공유 구역], 아직 내부 로직 미구현
frontend/src/   pages/ hooks/                          # 화면 소유 경계
                api/ components/ routes/ store/ types/  # [공유 구역]
envs/ infra/ scripts/                                    # [공유 구역]
docs/tasks/     Task Contract(T-그룹당 1개) + _active.json(claim 파일)
```

- 한 에이전트(또는 사람)는 한 번에 백엔드 기능 파일 하나, 프론트 화면 폴더 하나, 또는 AI 태스크 파일 하나만 소유한다.
- 배정 전 `docs/tasks/_active.json`을 확인해 이미 클레임된 도메인이면 진행하지 않고 사람에게 알린다. 종료(PR 병합) 시 항목을 제거한다. 이 파일 자체도 공유 구역 — 등록/해제 외 수정 금지.
- 새 Task Contract는 `docs/tasks/TASK_CONTRACT_TEMPLATE.md`를 복사해서 만든다.
- 상세 폴더 배치와 프론트 구조는 `docs/CODING_RULES.md` 2번/3번 참고.

## 2. 기술 스택 (미리 결정 — 질문 금지 대상)

FastAPI + Uvicorn, SQLAlchemy 2.0(AsyncSession) + Alembic, MySQL 8.0(Docker) + Redis, `uv` 패키지 매니저, JWT(Access 30분/Refresh 14일, python-jose) + Argon2, OpenAI GPT(챗봇/가이드) + CLOVA OCR, React(Vite+TS) + Zustand 없이 로컬 state 우선, 브랜치 `feature/{T-ID}-{요약}`, Conventional Commits, TDD(pytest), API P95 ≤ 3초(T-QUAL-1), Ruff+Mypy 필수. 결정 배경은 `docs/decision_log/` 참고.

## 3. 데이터 설계 원칙 — User ↔ Profile

- **User**는 계정/인증 전용(email/password/is_active 등), **Profile**이 개인정보(name/gender/birthday/phone_number) + 앞으로 만들 모든 도메인 테이블의 참조 키. 본인도 하나의 Profile로 취급한다.
- **새 도메인 테이블은 `user_id`가 아니라 `profile_id`를 참조 키로 쓴다** (가족 프로필 확장 대비).
- 현재 사용자 스코핑은 `app/dependencies/security.py`의 `get_current_profile`을 쓴다. `get_request_user`는 계정 정보가 필요할 때만.
- 상세: `docs/CODING_RULES.md` 2-1번.

## 4. 브랜치 / 커밋 / PR — 핵심만

- `main`, `dev`에 직접 커밋/푸시 금지 — 항상 브랜치 + PR. `feature/*`는 `dev`에서 분기해 `dev`로 병합.
- 새 작업: `git checkout dev && git pull origin dev` → `git checkout -b feature/{T-ID}-{설명}`
- 커밋: `type(T-ID): 설명` (`feat`/`fix`/`docs`/`refactor`). 작게, 자주.
- PR 제목 `[T-ID] 요약`, 본문에 TRD 성공요건 체크리스트, **직접 머지하지 않는다**(PR 생성까지가 범위).
- 공통모듈(`docs/squad-map.md` 소유자 지정 파일) 수정 시 PR에 `[공통모듈 변경]` 명시.
- 기존 PR 확인, 스택형 PR 머지 순서 등 상세는 `docs/DEV_WORKFLOW.md` 6/6-1번.

## 5. 세션 시작 — Drill-Me / STOP (요약)

새 화면·컴포넌트·플로우를 다루거나 텍스트 화면 스펙이 아직 없으면, 코드 작성 전 `docs/SESSION_START.md`의 6개 질문(진입점/컴포넌트/로딩·빈·에러 상태/인터랙션→API/T-ID/profile_id 기준)부터 확인한다. 순수 버그 수정·리팩토링은 생략 가능. 사람이 메시지 어디에든 `STOP`을 쓰면 즉시 멈추고 재확인 모드로 전환한다 — 전문은 `docs/SESSION_START.md`.

## 6. 구현 순서 (요약)

테스트(RED) → `models→repositories→services→apis` 순 구현(GREEN) → Swagger 문서화 → DB 변경 시 Alembic+ERD 동시 갱신 → 검증(명령 실행 결과로) → 커밋/PR. 프론트는 백엔드 계약 검증 후 타입 동기화 → api 함수 → 최소 UI → 라우팅 → 브라우저 직접 확인. 로컬 실행(Docker vs venv) 판단, 검증 커맨드, 전체 순서는 `docs/DEV_WORKFLOW.md`. 막히면 흔한 증상은 `docs/TROUBLESHOOTING.md`.

## 7. 작업 범위 — 넘지 말아야 할 경계

- 지시받은 T-ID/기능과 무관한 파일을 수정하지 않는다. 소유권은 폴더가 아니라 **파일명 접두어**(`docs/squad-map.md` 참고).
- `docs/plan/PRD_ReMedi_v1.1.md`, `docs/plan/TRD_ReMedi_v1.1.md`는 사용자가 명시적으로 요청하지 않는 한 내용을 바꾸지 않는다.
- `.env`, API 키, 시크릿 값을 코드/커밋/PR 설명에 하드코딩하지 않는다 — `envs/example.*.env`에 키 이름만.
- 실제 코드가 `docs/CODING_RULES.md`/`docs/decision_log/`와 다른 구조라면, 팀 합의 없는 개인 작업일 수 있다 — 그대로 따르지 말고 사용자에게 재작업 필요 여부를 먼저 확인한다.

## 8. 이미 결정된 것 / 반드시 멈추고 물어야 하는 경우

| 이미 결정됨 (재확인 불필요) | 반드시 멈추고 물어야 함 |
| --- | --- |
| 면책조항은 **의료 관련 응답에 조건부 노출** (T-LLM-1, 근거: `docs/decision_log/2026-07-12-disclaimer-conditional.md`) | 공유 구역 파일이나 DB 공통 스키마를 직접 수정해야만 작업 가능한 경우 |
| User/Profile 분리, 신규 테이블은 `profile_id` 기준 (T-ARCH-1) | Task Contract에 없는 새 외부 API/서비스 연동 |
| PII 비식별화는 정규식+NER 기반 실질 마스킹 (F-PRIV-1) | 성공요건(TRD) 충족에 "허용 경로" 밖 수정이 불가피한 경우 |
| CORS `allow_origins=["*"]`는 로컬 전용, 배포 시 명확히 제어 | 개인정보/보안 비가역적 작업(암호화 방식, PII 로직, 영구 삭제) |
| 통계 API는 5명 이하 집계 시 자동 마스킹 (T-STAT-1) | 두 Task Contract 요구사항이 서로 모순되는 경우 |
| 병원 예약 등 스코프 외 기능은 고도화하지 않음 | DB 스키마/ORM/인증 방식처럼 되돌리기 힘든 설계 결정 |
| 새 테이블 추가 시 모델+`docs/dev/ERD.dbml` 동시 갱신 | T-ID 없거나 여러 도메인에 걸친 모호한 요청 |
| 테스트는 TDD로 구현보다 먼저 작성 | 다른 스쿼드 소유 파일(`docs/squad-map.md`)을 고쳐야 할 것 같을 때 |
| Backlog(⚠) 항목은 Task Contract 없이 착수하지 않음 | 사용자가 이미 정한 것을 다르게 재해석해야 할 것 같을 때 |

이 표 밖의 모든 것은 위 원칙 + Task Contract + 합리적 가정으로 끝까지 진행한다.

## 9. 완료 시 자가 검증

배정된 Task Contract의 "완료 정의" 체크리스트를 스스로 확인하고 `docs/tasks/T-XXX-N.md`의 "완료 보고"에 결과를 기록한다. 실패 항목이 있으면 PR을 열지 않고 스스로 수정한다. 검증 커맨드는 `docs/DEV_WORKFLOW.md` 5번.

또한 아래를 스스로 확인한다: 새 기능/버그수정에 테스트 포함, TRD 성공요건 충족, `ruff`/`pytest`/`tsc`/`lint` 통과, 변경 범위가 T-ID에 한정(`git diff --stat`), 새 엔드포인트에 `summary`/`description`/`responses`/`Field(description=...)` 기입, DB 변경 시 Alembic+ERD 동기화, 커밋/브랜치명이 4번 규칙 준수.

## 10. 문서 버전 관리

문서는 두 종류다. **파일명은 버전 때문에 다시 바꾸지 않는다** (배경: `docs/decision_log/2026-07-07.md`).

- **살아있는 문서** (`AGENTS.md`, `CLAUDE.md`, `docs/CODING_RULES.md`, `docs/CONTRIBUTING.md`, `docs/SESSION_START.md`, `docs/DEV_WORKFLOW.md`, `docs/TROUBLESHOOTING.md`, `docs/squad-map.md`, `docs/dev/ERD.dbml`): 파일명 고정, 내용을 바꾸면 헤더의 **버전 번호만 올리고 변경 이력에 한 줄 추가**한다.
- **원본 스냅샷 문서** (`docs/plan/PRD_ReMedi_v1.1.md`, `docs/plan/TRD_ReMedi_v1.1.md`, `docs/dev/api_spec_core_v1_v1.1.yaml`): 파일명 버전 접미사를 유지한다. 내용을 바꿔야 하면 파일명 버전을 올리기 전에 사용자에게 먼저 확인한다.
- **`docs/decision_log/`**: 파일당 하루(`YYYY-MM-DD.md`), 새 결정은 새 날짜 파일에 추가한다. 컨벤션: `docs/decision_log/README.md`.

오타 수정 같은 사소한 변경은 버전 갱신 예외 — 애매하면 사용자에게 확인.

## 11. 모호할 때

T-ID가 없거나, 여러 도메인에 걸치거나, TRD에 없는 동작이 필요한 요청은 임의로 진행하지 말고 무엇을 가정했는지 먼저 설명하고 확인받는다. 새 화면/기능/사용자 플로우라면 5번(Drill-Me) 절차를 따른다. 이미 실패한 접근을 사용자가 명시적으로 피하라고 했다면 같은 대화 내에서 번복해 재시도하지 않는다.

## 12. 참고 문서 지도

| 문서 | 언제 보는가 |
| --- | --- |
| `docs/SESSION_START.md` | 새 화면/기능/플로우 착수 전, STOP 처리 |
| `docs/DEV_WORKFLOW.md` | 구현 순서, 로컬 실행환경, 검증 커맨드, 커밋/PR·스택형 PR |
| `docs/TROUBLESHOOTING.md` | 로컬 실행 중 에러(DB/포트/alembic/pytest 등) 만났을 때 |
| `docs/CODING_RULES.md` | 폴더구조, 코드 스타일, API 응답/에러 포맷, DB 네이밍, TDD/Swagger/ERD 규칙 |
| `docs/CONTRIBUTING.md` | 브랜치/이슈/충돌방지 등 협업 최소 규칙 |
| `docs/decision_log/` | "왜 이렇게 됐는지" 배경, 미결사항 |
| `docs/squad-map.md` | 스쿼드/담당자/공통모듈 소유자 (유일한 출처) |
| `docs/plan/PRD_ReMedi_v1.1.md`, `TRD_ReMedi_v1.1.md` | T-ID의 요구사항/입출력/성공요건 (수정 금지) |
| `docs/dev/` | ERD.dbml, api_spec, sample_code_* (개발 산출물/참고 예제) |
| `docs/tasks/` | Task Contract, `TASK_CONTRACT_TEMPLATE.md`, `_active.json` |
