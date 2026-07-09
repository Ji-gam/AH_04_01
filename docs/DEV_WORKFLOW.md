# DEV_WORKFLOW.md — 구현 순서 / 로컬 실행 / 검증 / 커밋·PR

> **문서 버전**: v1.0 · **최종 수정**: 2026-07-08
> **변경 이력**
> - v1.0 (2026-07-08): `AGENT_PLAYBOOK.md` 1·2·2-1·3·5·6·6-1번을 하네스 정리 과정에서 이 문서로 분리 이관

`AGENTS.md`가 담는 핵심 계약을 실제로 실행할 때 쓰는 상세 매뉴얼. 세션 시작 트리거는 `docs/SESSION_START.md`, 흔한 문제 해결은 `docs/TROUBLESHOOTING.md` 참고.

---

## 1. 작업 시작 전 체크리스트

- [ ] `docs/SESSION_START.md`의 drill-me 트리거에 해당하는 요청인가 — 해당하면 체크리스트보다 먼저 그 절차부터 마친다
- [ ] `git checkout dev && git pull origin dev` 후 `feature/{T-ID}-{설명}` 브랜치를 새로 팠는가
- [ ] 이 작업이 DB 스키마/ORM/인증 방식처럼 "여러 파일에 걸쳐 되돌리기 힘든" 결정을 포함하는가 → 포함한다면 구현 전에 사용자에게 먼저 확인 (`AGENTS.md`의 "반드시 멈추고 물어야 하는 경우" 참고)
- [ ] 관련 T-ID가 있다면 `docs/plan/TRD_ReMedi_v1.1.md`에서 입력/출력/성공요건을 먼저 읽었는가
- [ ] 비슷한 기존 패턴이 있는가 확인했는가 — 새 도메인이면 `docs/dev/sample_code_chat/`, `docs/dev/sample_code_recog/`를, 인증/계정 관련이면 `app/services/auth.py` 계열을 먼저 읽고 그 패턴을 따른다
- [ ] 로컬로 돌릴지 Docker로 돌릴지 정했는가 (3번 참고 — 섞어 쓰면 반드시 에러난다)
- [ ] **프론트엔드 작업이면 2-1번(구현 순서)과 `docs/CODING_RULES.md` 3번(프론트엔드 규칙)을 먼저 읽었는가**

---

## 2. 구현 순서 (TDD 루프 — 항상 이 순서)

1. **정상 케이스 + 실패 케이스 테스트를 먼저 작성**하고 실행해서 실패(RED)하는 걸 확인한다. 실패 케이스는 최소: 중복/충돌, 유효성 검증 실패, 인증 없음/실패.
2. `models` → `repositories` → `services` → `apis`(routers) 순서로 구현해서 테스트를 통과(GREEN)시킨다. 이 순서를 거슬러 올라가며 구현하지 않는다(라우터부터 짜지 않는다).
3. 라우터/DTO에 Swagger 문서화를 채운다: `summary`, `description`, 실패 케이스별 `responses`, DTO 필드의 `Field(description=...)`. 기준은 `docs/CODING_RULES.md` 5번.
4. DB 스키마를 바꿨다면: Alembic 리비전 작성 + `docs/dev/ERD.dbml` 갱신을 **같은 작업 단위**로 한다.
5. 검증한다(5번 참고) — "테스트를 돌렸다"가 아니라 "돌려서 통과한 로그가 있다"가 완료 기준이다.
6. 커밋/PR을 만든다(6번 참고).

### 2-1. 프론트엔드 구현 순서 (도메인 화면을 새로 만들 때 — 이미 합의된 기본값)

`docs/CODING_RULES.md` 3번의 "확정 안 된 것"(탭 구성, 디자인 톤 등)과는 별개로, **일단 화면을 만들기로 정해지면 아래 순서를 그냥 따른다** — 매번 순서를 다시 물어보지 않는다:

1. **백엔드 계약이 이미 있고 검증까지 끝났는지 확인한다.** 없으면 먼저 백엔드를 만들고 `curl`/Swagger로 실제로 저장·조회되는지 확인한 다음에 넘어온다(2번 TDD 루프) — 계약이 안 굳은 상태에서 프론트를 먼저 만들지 않는다.
2. `frontend/src/api/types.ts`에 백엔드 DTO와 1:1 대응하는 타입을 추가/동기화한다.
3. `frontend/src/api/`에 그 엔드포인트를 호출하는 함수를 추가한다(엔드포인트당 함수 1개).
4. 이 화면이 다른 페이지와 공유해야 하는 상태가 있는지 판단한다 — 없으면 페이지 로컬 `useState`로 충분하다(전역 Context를 새로 만들지 않는다. `hooks/useAuth.tsx`처럼 여러 화면이 공유해야 하는 게 명확할 때만 Context로 승격한다).
5. **스타일 없이** 최소 입력폼/출력만 있는 화면을 만든다 — 목표는 "눌렀을 때 실제로 백엔드까지 왕복하는가"를 스웨거 레벨 체크만큼 단순하게 증명하는 것이다. 공통 컴포넌트로 뽑거나 디자인을 입히는 건 지금 하지 않는다(`docs/CODING_RULES.md` 3-5번, 화면이 2~3개 쌓인 뒤로 미룬다).
6. 라우터(`App.tsx`)에 연결한다. 로그인이 필요한 화면이면 `RequireAuth`로 감싼 트리 안에 넣는다.
7. **브라우저에서 직접 눌러서 확인한다** — 입력한 값이 그대로 저장/조회되는지, 실패 케이스(잘못된 입력 등)일 때 에러 문구가 사람이 읽을 수 있게 나오는지(`docs/CODING_RULES.md` 9번 참고)까지. `tsc --noEmit`/`eslint`만 통과한 걸로 끝내지 않는다.

---

## 3. 로컬 실행 환경 판단 — 반드시 먼저 정하고 시작

이 레포는 **Docker Compose가 팀 표준**이다(`docker-compose.yml`, 각 서비스 `Dockerfile`). 로컬 venv로 빠르게 돌리는 것도 가능하지만, 두 모드는 설정이 다르고 섞으면 바로 에러난다.

| | Docker 모드 | 로컬(venv) 모드 |
|---|---|---|
| `envs/.local.env`의 `DB_HOST` | `mysql` (서비스명) | `localhost` |
| pytest 실행 위치 | `docker compose exec fastapi uv run pytest` | `uv run pytest` (호스트에서) |
| 마이그레이션 실행 위치 | `docker compose exec fastapi uv run alembic upgrade head` | `uv run alembic upgrade head` (호스트에서) |

**증상으로 지금 뭐가 잘못됐는지 판단하는 법**:
- `Access denied for user ...` 또는 `Unknown database` → `DB_HOST`가 지금 실행 위치와 안 맞는 모드로 설정돼 있다. 위 표에서 확인.
- `mysql`이라는 호스트를 못 찾는다는 DNS/연결 에러 → 로컬(venv)에서 실행 중인데 `DB_HOST=mysql`로 되어 있다. `localhost`로 바꾸거나, Docker 컨테이너 안에서 실행하도록 명령을 바꾼다.

`envs/.local.env`는 `.gitignore` 대상(개인 파일)이라 이 값을 마음대로 바꿔도 팀에 영향 없다. 단, **팀 표준 파일**(`docker-compose.yml`, `envs/example.local.env`, `vite.config.ts`의 포트/프록시 값)은 개인 사정으로 바꾸고 그대로 두지 않는다 — 검증 끝나면 반드시 원래 값으로 되돌린다(`docs/TROUBLESHOOTING.md` B 참고).

---

## 5. 검증 — "말로 끝났다" 금지, 명령어 결과로 끝났다는 걸 확인

작업을 완료로 보고하기 전에 실제로 아래를 실행해서 결과를 확인한다(3번에서 정한 모드에 맞는 쪽으로):

```bash
# 백엔드 — Docker 모드
docker compose exec fastapi uv run --no-sync pytest -v
docker compose exec fastapi uv run --no-sync ruff check app/
docker compose exec fastapi uv run --no-sync alembic upgrade head   # 스키마를 바꿨다면

# 백엔드 — 로컬 모드
uv run pytest -v
uv run ruff check app/
uv run alembic upgrade head   # 스키마를 바꿨다면

# API가 실제로 도는지 curl로 한 번은 직접 확인 (Swagger 문서화 확인 겸)
curl -s http://localhost:8000/api/openapi.json | python3 -m json.tool | head -40

# 프론트
cd frontend && npx tsc --noEmit && npm run lint
```

새 도메인 라우터를 만들었다면 `/api/docs`를 열어서 summary/description/응답 스키마가 빠짐없이 보이는지 육안으로도 한 번 확인한다.

---

## 6. 커밋 / PR 만들기

- **PR을 만들기 전에 같은 브랜치에 이미 열린 PR이 있는지 먼저 확인**한다(`gh pr list --head <브랜치>`). 있으면 새 PR을 만들지 않고 그냥 push — 자동으로 반영된다.
- 브랜치는 원칙적으로 `dev`에서 분기, PR도 `dev`로. **단, 이 작업이 의존하는 앞선 feature 브랜치가 아직 `dev`에 머지되지 않았다면, 그 feature 브랜치를 base로 잡는다(스택형 PR)** — 안 그러면 그 앞선 브랜치의 전체 diff가 이 PR에도 그대로 섞여 나온다. 앞선 브랜치가 `dev`에 머지되면 이 PR의 base를 `dev`로 재조정한다(6-1번).
- 하나의 작업이 여러 관심사(예: 백엔드 로직 + 문서 + 인프라 수정)에 걸쳐 있으면, **관심사별로 커밋/브랜치를 쪼갠다.** 커밋 메시지 형식은 `type(T-ID): 설명` (`AGENTS.md` 참고).
- PR 본문에 **실제로 실행해서 통과한 명령어**를 적는다 ("테스트를 추가했습니다"가 아니라 "`pytest -v` 결과 13 passed" 식으로) — 리뷰어가 같은 명령으로 재현할 수 있어야 한다.
- T-ID가 있다면 TRD 성공요건과 대조해 PR 본문에 체크리스트로 남긴다. 미달 항목은 숨기지 말고 그대로 적는다 — "부분 구현"이라고 정직하게 쓰는 게, 성공요건을 조용히 완화한 것처럼 보이는 것보다 낫다.
- 작업 중 임시로 바꾼 로컬 전용 값(포트, DB 이름 등)이 diff에 남아있지 않은지 `git diff`로 마지막에 한 번 확인한다.

### 6-1. 스택형 PR의 머지 순서

여러 PR이 서로를 base로 삼아 쌓여있으면(예: B가 A의 브랜치를 base로 함), **의존관계의 아래쪽(A)부터 `dev`에 머지**한다. "feature 브랜치부터 정리하고 `main`에 머지"가 아니다 — 이 레포는 `feature/*`를 `main`에 직접 머지하지 않는다(`AGENTS.md` 브랜치 규칙). `dev`→`main`은 오직 `Release/*` 브랜치를 통해서만 이뤄지므로, feature 단계에서는 항상 `dev`까지만 생각한다.

1. 가장 아래(다른 브랜치들의 base가 되는) feature 브랜치를 리뷰 후 `dev`에 먼저 머지한다.
2. 그 위에 쌓인 PR의 base를 `dev`로 재조정한다(GitHub이 보통 자동으로 재조정하지만, 안 되면 `gh pr edit <번호> --base dev`).
3. 재조정 후 diff를 다시 확인해 그 PR만의 변경사항만 남았는지(머지된 브랜치의 커밋이 다시 섞여 보이지 않는지) 확인한다.
4. 다음 PR도 같은 순서로 반복한다.
