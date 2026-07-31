# AGENTS.md — ReMedi 단일 진입점

v3.0 · 이력: `git log AGENTS.md`. 모든 에이전트 매 세션 필독. `CLAUDE.md`/`.antigravity/rules/AGENTS.md`=리다이렉트. 불확실하면 추측 금지, 확인. 이 문서는 정책+라우팅만 — 각 항목의 상세 규칙은 아래 대상 문서에만 존재(중복 서술 금지).

0. 절대원칙
- Task Contract(`docs/tasks/T-XXX-N.md`) "허용 경로" 밖 파일 금지(존재확인 외 열람도 금지)
- 확인질문 최소화 — §6표+Task Contract로 진행, 부족분은 가정 후 완료보고에 Assumptions로 기록. T-ID없음/여러도메인처럼 모호하면 임의진행 대신 가정을 먼저 설명. 사용자가 피하라고 한 접근은 같은 대화 내 재시도 안 함
- 중단은 §6표 "반드시멈춤" 항목일 때만. 그 외(변수명/함수분리/에러문구)는 자체결정. `STOP` 입력시 즉시중단(§4)
- 공유구역([공유]표시, §1) Task Contract 미허용시 수정 금지 — 완료보고에 "공유파일 변경 필요"만 기록
- 시작시 `docs/tasks/_active.json`에 Task ID+브랜치명 등록, 종료시 해제

1. 디렉토리=소유권 (전체 구조/파일역할: `docs/CODING_RULES.md` §2/§3)

```
app/            apis/v1/ dtos/ services/ repositories/ models/ tests/
                dependencies/ core/ [공유]
ai_worker/      tasks/ schemas/ | core/[공유,로직미구현]
frontend/src/   pages/ hooks/ [화면소유]
                api/ components/ routes/ store/ types/ [공유]
envs/ infra/ scripts/ [공유]
docs/tasks/     Task Contract(T그룹당1)+_active.json(claim)
```
폴더 아닌 파일명 접두어로 도메인 구분(소유자 표: `docs/SQUAD_MAP.md`). 1에이전트=백엔드파일1/프론트화면폴더1/AI태스크파일1개 소유. 배정 전 `_active.json` 확인, 클레임중이면 진행금지+보고. 신규 Task Contract는 `docs/tasks/TASK_CONTRACT_TEMPLATE.md` 복사.

2. 스택
`pyproject.toml`/`frontend/package.json` 참고 — 재질문 금지. 코드 컨벤션은 `docs/CODING_RULES.md`.

3. User↔Profile
전체 규칙: `docs/CODING_RULES.md` §2-1. 요지만: 신규 도메인 테이블은 `user_id`아닌 `profile_id` 참조.

4. Drill-Me/STOP
트리거(하나라도): 새 화면/컴포넌트/플로우 요청, 텍스트 화면스펙(진입점/컴포넌트/로딩·빈·에러상태/인터랙션→API/T-ID) 없음, 기존 스펙 범위 초과.
생략: 스펙 안에서만 구현, 순수 버그수정/내부 리팩토링.
질문세트(답 없는 것만 콕 집어 되물음, 코드 먼저 안 씀): 진입점(탭/화면) / 구성 컴포넌트+필수·선택 / 로딩·빈·에러 상태 표시 / 인터랙션→API 매핑 / T-ID(PRD/TRD/decision_log 대조) / (해당시)profile_id 기준 여부.
판단기준: "이 요구사항만으로 두 사람이 다른 화면을 만들 수 있는가"→그렇다면 미완료. 답 다 있으면 "이렇게 이해했다" 요약확인만. 끝나면 짧은 텍스트스펙 동의받고 코드 작성.
STOP: 메시지 어디든 `STOP`→ 작성중이면 즉시멈춤 / 이해내용 요약 / 미답 문항만 재확인 / 답 받기 전 재산출 안 함. 취소 아님, 재확인모드 전환.

5. 브랜치/커밋/PR/구현순서/로컬실행/검증
전부 `docs/CONTRIBUTING.md`. 에이전트는 PR 생성+CI확인까지가 범위, 직접 머지 안 함. 에러 발생시 `docs/TROUBLESHOOTING.md`.

6. 결정됨/반드시멈춤
결정됨(재확인불필요, 각주=근거/상세위치): 면책조항 의료응답조건부노출(T-LLM-1) · User/Profile분리+profile_id 기준(T-ARCH-1, CODING_RULES§2-1) · PII 정규식+NER 실질마스킹(F-PRIV-1) · CORS allow_origins=["*"]는 로컬전용 · 통계API 5명이하 자동마스킹(T-STAT-1) · 병원예약 등 스코프외 기능 고도화 안함 · 신규테이블시 모델+ERD.dbml 동시갱신(CODING_RULES§6) · 테스트는 구현보다 먼저 TDD(CONTRIBUTING§5) · Backlog(⚠)는 Task Contract 없이 착수 안함 · JWT Access30분/Refresh14일 · 프론트 로컬state 우선 Zustand없음(CODING_RULES§3-3) · API P95≤3초(T-QUAL-1)
반드시멈춤: 공유구역/DB공통스키마 직접수정 필요 · Task Contract에 없는 외부API/서비스연동 · TRD충족에 허용경로 밖 수정 불가피 · 개인정보/보안 비가역작업(암호화방식,PII로직,영구삭제) · 두 Task Contract 요구사항 모순 · DB스키마/ORM/인증방식 등 되돌리기 힘든 결정 · T-ID없거나 여러도메인 걸친 모호한 요청 · 타스쿼드 소유파일(SQUAD_MAP.md) 수정 필요할듯 · 이미 정해진 것 다르게 재해석해야 할듯
표 밖은 위 원칙+Task Contract+합리적 가정으로 진행.

7. 범위경계
- T-ID/기능 무관 파일 수정 금지
- `docs/plan/PRD*.md`,`TRD*.md`는 명시요청 없이 수정 금지
- `.env`/API키/시크릿 코드·커밋·PR에 하드코딩 금지 — `envs/example.*.env`엔 키 이름만
- 실코드가 `CODING_RULES.md`/`decision_log`와 다르면 팀합의 없는 개인작업 가능성 — 그대로 안 따르고 재작업 필요여부 확인

8. 완료 자가검증
Task Contract "완료정의" 체크 후 `docs/tasks/T-XXX-N.md` 완료보고에 기록. 실패항목은 PR 열기 전 자체수정. 확인: 테스트포함 / TRD 성공요건 충족 / `ruff`·`pytest`·`tsc`·`lint` 통과 / 변경범위 T-ID 한정(`git diff --stat`) / 새 엔드포인트 summary·description·responses·Field(description=...) / DB변경시 Alembic+ERD 동기화 / 커밋·브랜치명 규칙 준수(CONTRIBUTING§3,§8). 검증커맨드: `docs/CONTRIBUTING.md` §7.

9. 문서지도
`docs/CONTRIBUTING.md`(구조/브랜치/이슈·PR/TDD순서/로컬실행/검증) · `docs/CODING_RULES.md`(계층/폴더/네이밍/API·DB포맷/프론트규칙/TDD품질기준/ERD/Swagger) · `docs/TROUBLESHOOTING.md`(로컬실행 에러) · `docs/SQUAD_MAP.md`(스쿼드/소유자, 유일출처) · `docs/FRONTEND_UI_GUIDE.md`(디자인시스템/Tailwind+shadcn) · `docs/decision_log/`(배경/미결) · `docs/plan/PRD*,TRD*`(요구사항, 수정금지) · `docs/dev/`(ERD.dbml/api_spec/sample_code) · `docs/tasks/`(Task Contract/`_active.json`)
