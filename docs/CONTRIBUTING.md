# CONTRIBUTING.md — 협업 하네스

v3.0 · 이력: `git log docs/CONTRIBUTING.md`. 구조/브랜치/이슈·PR/구현순서/로컬실행/검증/커밋 전부 이 문서 하나. 사람용 프로세스(슬랙공지/킥오프체크리스트) 없음 — 에이전트 실행 규칙만.

0. 요약
레포=모노레포1개(`frontend/`,`app/`=레이어우선). 브랜치=`main`(배포)←`dev`(통합)←`feature/T-ID-설명`. 이슈→PR=이슈먼저→버티컬슬라이스200~300줄PR→즉시머지(스택형금지,§4). 구현순서=TDD:테스트(RED)→`models→repos→services→apis`(GREEN)→Swagger→검증→커밋(§5). 커밋=`type(T-ID): 설명` 예`feat(T-AUTH-1): 이메일 회원가입 API`. PR/이슈 작성=길게 쓰지 않음(§8).

1. 레포 구조
```
app/            apis/ services/ repositories/ models/ dtos/ core/ dependencies/ tests/
ai_worker/      AI/RAG/멀티모달 — 별도서비스
frontend/       React+Vite (CODING_RULES.md §3)
envs/ infra/ scripts/
docs/           CODING_RULES / CONTRIBUTING / TROUBLESHOOTING / decision_log/ / SQUAD_MAP.md / FRONTEND_UI_GUIDE.md / plan/ / dev/
AGENTS.md       진입점(Drill-Me/STOP 포함) · CLAUDE.md=리다이렉트
```
모노레포=프론트/백엔드 스펙변경 한 PR에서 같이 리뷰(레포분리시 동기화사고 방지).

2. 스쿼드↔도메인
TRD T그룹=스쿼드경계, 실배정/소유파일접두어=`SQUAD_MAP.md`(유일출처). 폴더아닌 파일명접두어로 소유권 구분(`AGENTS.md` §1).

3. 브랜치 전략 (GitFlow)
```
main   ←배포가능 상태만(PR only)
 └dev  ←통합(PR only)
   ├feature/{T-ID}-{설명}  dev분기→dev병합
   ├Release/{버전}         dev분기→main+dev병합
   └hotfix/{설명}          main분기→main+dev병합
```
`main`/`dev` 보호브랜치(PR+승인1). `feature/*`는 항상 `dev` 최신 pull 후 분기.

4. 이슈 → PR 흐름
원칙: 이슈먼저→작게쪼갠PR→즉시머지. 스택형 금지.
종류: Proposal — 코드없이 팀승인 필요(외부API/아키텍처변경, `AGENTS.md` §6) — 제목`[PROPOSAL] ...` — 템플릿`.github/ISSUE_TEMPLATE/proposal.md`→승인시 Task Contract 전환. Task — Task Contract 기반 구현/버그수정 — 제목`[T-ID] ...` — 템플릿`.github/ISSUE_TEMPLATE/task.md`→시작전`_active.json` Claim(`AGENTS.md` §0).
PR 쪼개기: 계층별아닌 버티컬슬라이스(엔드포인트 DB모델~라우터 전체 등 완결단위), 200~300줄/PR 권장, 프론트는 API연동+최소바인딩 완결 화면단위.
머지흐름: `dev` base PR생성(스택형금지)→CI통과 확인→리뷰요청. 에이전트는 직접 머지 안함(PR생성+CI확인까지가 범위, `AGENTS.md` §5). 머지후 로컬동기화: `git checkout dev && git pull origin dev`.
종료: 이슈의 모든 슬라이스 PR 머지완료→이슈Close, `_active.json` Claim 제거.

5. 구현 순서 (TDD)
1. 정상+실패케이스 테스트→RED확인(실패케이스: 중복/충돌, 유효성실패, 인증없음/실패). 테스트 품질기준(가짜Repository, 통합테스트 범위, 이름규칙): `CODING_RULES.md` §4
2. `models→repositories→services→apis`(routers) 순 구현→GREEN(역순금지)
3. Swagger: `summary`/`description`/실패별`responses`/`Field(description=...)` — 상세 `CODING_RULES.md` §5
4. DB스키마 변경시: Alembic리비전+`ERD.dbml` 갱신을 같은 커밋단위로 — 상세 `CODING_RULES.md` §6
5. 검증(§7, "통과 로그 확보"가 완료기준)
6. 커밋/PR(§8)

프론트(도메인화면 신규시 기본값):
1. 백엔드계약 검증확인(없으면 위 TDD로 먼저, curl/Swagger로 저장·조회 확인)
2. `frontend/src/api/types.ts`에 DTO 1:1 타입 동기화
3. `frontend/src/api/`에 엔드포인트당 호출함수 1개
4. 공유상태 필요시만 Context — 계층/상태관리 규칙: `CODING_RULES.md` §3-1,§3-3
5. 스타일 없이 최소 입출력 화면만 — 스타일 규칙: `CODING_RULES.md` §3-5, `FRONTEND_UI_GUIDE.md`
6. `App.tsx` 라우팅, 인증필요시 `RequireAuth`
7. 브라우저 직접 클릭확인(저장/조회 값, 에러문구) — `tsc`/`eslint` 통과만으로 안 끝냄

6. 로컬 실행 (Docker 표준, venv 병행가능·혼용금지)
`DB_HOST`: Docker=`mysql`, venv=`localhost`. pytest: Docker=`docker compose exec fastapi uv run pytest`, venv=`uv run pytest`. migration: Docker=`docker compose exec fastapi uv run alembic upgrade head`, venv=`uv run alembic upgrade head`.
`Access denied`/`Unknown database`→`DB_HOST` 모드불일치. `mysql` DNS에러→venv인데 `DB_HOST=mysql`→`localhost`로.
`envs/.local.env`=개인파일(gitignore). 팀표준파일(`docker-compose.yml`,`envs/example.local.env`,`vite.config.ts` 포트/프록시)은 검증후 원복 필수(`TROUBLESHOOTING.md`).

7. 검증 (실행결과로 확인)
```bash
# Docker
docker compose exec fastapi uv run --no-sync pytest -v
docker compose exec fastapi uv run --no-sync ruff check app/
docker compose exec fastapi uv run --no-sync alembic upgrade head   # 스키마변경시

# 로컬
uv run pytest -v
uv run ruff check app/
uv run alembic upgrade head   # 스키마변경시

curl -s http://localhost:8000/api/openapi.json | python3 -m json.tool | head -40   # API 실동작+Swagger 확인

cd frontend && npx tsc --noEmit && npm run lint
```
신규 도메인 라우터 추가시 `/api/docs`에서 응답스키마 육안확인.

8. 커밋 / PR / 이슈 — 길게 쓰지 않는다
핵심만: 무엇을/왜/어떻게 검증했는지 불릿 몇 줄. 배경서술·산문 금지 — 필요하면 `decision_log/` 링크로 대체. 길수록 에이전트는 토큰낭비, 사람은 인지부하로 안 읽음.
```
type(T-ID): 설명
feat(T-AUTH-1): 이메일 회원가입 API 구현
fix(T-NTFY-1): 알림 미도착 버그 수정
```
- PR 생성전 `gh pr list --head <브랜치>` 확인 — 있으면 새 PR 없이 push
- 제목 `[T-ID] 요약`, 관심사별 커밋·브랜치 분리
- 본문: TRD 성공요건 체크 + 실행결과("추가함" 금지, "`pytest -v` 13 passed" 식), 미달항목 숨기지 않음
- DB CRUD PR은 `ERD.dbml` 동시갱신 확인(`CODING_RULES.md` §6)
- 임시 로컬값(포트/DB명)이 diff에 안 남았는지 마지막 확인
- 이슈 제목 T-ID/F-ID 포함(Proposal은`[PROPOSAL]`), 라벨=스쿼드+상태, 담당자 없이 시작 금지

9. 환경변수/시크릿
실값든 `.env`,`envs/.local.env`,`envs/.prod.env` 커밋 금지. API키/시크릿 코드·커밋·PR·이슈에 하드코딩·평문 금지 — `envs/example.*.env`엔 키 이름만. 메커니즘(심볼릭링크 전환, DB_NAME 충돌회피): `CODING_RULES.md` §2-2,§2-3.
