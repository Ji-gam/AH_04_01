# TROUBLESHOOTING.md — 자주 만나는 문제 (증상 → 원인 → 조치)

> **문서 버전**: v1.0 · **최종 수정**: 2026-07-08
> **변경 이력**
> - v1.0 (2026-07-08): `AGENT_PLAYBOOK.md` 4번을 하네스 정리 과정에서 이 문서로 분리 이관

## A. 로컬 MySQL/포트에 이미 무관한 데이터/프로세스가 있음
**증상**: DB에 접속은 되는데 이 프로젝트와 무관한 테이블이 보인다. 또는 `GRANT`/로그인이 예상대로 안 된다.
**원인**: 이 컴퓨터에 다른 프로젝트나 이전 실습이 같은 이름의 DB/유저를 이미 쓰고 있다.
**조치**: **절대로 기존 DB를 드랍하거나 유저를 지우지 않는다** — 누구 데이터인지 모른 채 지우는 건 되돌릴 수 없는 사고다. 대신 이번 프로젝트만의 고유한 DB 이름을 `envs/.local.env`에 새로 정해서 쓴다 (예: 레포 이름을 접두어로). 확인 명령:
```bash
mysql -uroot -e "SHOW DATABASES;"
mysql -uroot -e "USE 그이름; SHOW TABLES;"   # 내용을 보고 이 프로젝트 것인지 먼저 판단
```

## B. 포트 충돌 (3306 / 8000 / 5174 등)
**증상**: `bind: address already in use`, 또는 docker-compose 컨테이너가 기동 중 멈춤, 또는 preview 서버 시작 실패.
**원인**: 이 컴퓨터에서 이미 다른 프로세스가 그 포트를 쓰고 있다(다른 프로젝트일 가능성이 높다).
**조치**:
```bash
lsof -i :포트번호 -sTCP:LISTEN
```
내가 지금 이 작업으로 띄운 게 아닌 프로세스라면 **죽이지 않는다.** 대신:
- Docker: `docker-compose.override.yml`(커밋 안 함)로 그 서비스만 다른 호스트 포트에 매핑해서 검증
- Vite: `vite.config.ts`의 `server.port`/`proxy` 값을 임시로 바꿔서 검증
- **검증이 끝나면 반드시 팀 표준 값(8000/5174/3306)으로 되돌리고, 임시 override 파일은 삭제한다.** 이 값들이 커밋에 남아있으면 안 된다.

## C. Docker 컨테이너 안에서 `alembic`이 `No 'script_location' key found`
**원인**: `Dockerfile`이 `alembic.ini`를 이미지에 `COPY`하지 않았다(코드만 복사하고 루트의 설정 파일을 빠뜨리는 흔한 실수).
**조치**: `Dockerfile`의 `COPY` 목록에 `alembic.ini`를 추가하고 이미지를 재빌드(`docker compose up -d --build <서비스명>`).

## D. SQLAlchemy `InvalidRequestError: A transaction is already begun on this Session`
**원인**: 같은 세션에서 앞선 조회(예: 중복 체크용 `SELECT`)가 이미 트랜잭션을 autobegin 시켰는데, 그 뒤에 또 `async with session.begin():`으로 명시적으로 새 트랜잭션을 열려고 했다.
**조치**: 요청 하나가 하나의 write 유닛이면, 중간에 `session.begin()`을 쓰지 말고 마지막에 `await session.commit()`만 호출한다. `session.begin()`은 그 시점에 트랜잭션이 전혀 시작되지 않았다고 확신할 때만 쓴다.

## E. pytest에서 `RuntimeError: Task ... attached to a different loop`
**원인**: 세션 스코프 fixture(DB 엔진 등)와 개별 테스트 함수가 서로 다른 asyncio 이벤트 루프에서 돈다 (pytest-asyncio 기본값은 테스트마다 새 루프).
**조치**: `pyproject.toml`의 `[tool.pytest.ini_options]`에 다음을 모두 넣는다:
```toml
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

## F. 레포 루트에서 `pytest`를 돌리면 `docs/dev/sample_code_*/` 안의 테스트까지 잘못 수집돼서 깨짐
**원인**: 그 폴더들은 각자 자기만의 `app` 패키지를 가진 독립 예제라, 진짜 앱의 `app` 패키지와 이름이 겹친다. pytest가 rootdir 전체를 훑으면 충돌한다.
**조치**: `pyproject.toml`의 `[tool.pytest.ini_options]`에 `testpaths = ["app/tests"]`를 지정해서 진짜 테스트 경로만 수집하게 한다(이미 설정되어 있음). `docs/dev/sample_code_*/`는 그 폴더 안에 들어가서 `PYTHONPATH=. pytest -v`로 따로 돌린다.

## G. 백엔드 응답 스키마를 바꿨는데(예: 필드 추가) 프론트가 안 맞음
**원인**: 백엔드-프론트 타입 동기화가 자동이 아니라 수동 규칙이다(`docs/CODING_RULES.md` 3-4번).
**조치**: `app/dtos/*.py`를 바꾼 커밋/PR 안에 `frontend/src/api/types.ts`(해당 타입)도 같이 고친다. 둘을 다른 PR로 쪼개지 않는다.

## H. `git status`에 `.omc/`, `node_modules/`, `__pycache__/`, `.pytest_cache/` 같은 게 계속 걸림
**조치**: 새로 프론트/파이썬 산출물 디렉터리를 추가했다면 `.gitignore`에 패턴을 추가하는 게 맞다(임시로 안 스테이징하는 게 아니라). 이미 `.gitignore`에 `node_modules/`, `.omc/`는 등록돼 있다.

## I. 프론트에서 에러 메시지가 `[object Object]`로만 찍힘
**증상**: 회원가입/로그인 실패 시 화면에 `[object Object]`만 뜨고 실제 원인을 알 수 없다.
**원인**: FastAPI의 유효성 검증 실패(422) 응답은 `{"detail": [{"loc": [...], "msg": "..."}, ...]}`처럼 **배열**로 오는데, `HTTPException(detail="...")`(문자열)만 가정하고 `new Error(body.detail)`처럼 그대로 넘겨서 배열이 문자열로 강제 변환됐다.
**조치**: 에러 파싱 로직(`frontend/src/api/client.ts`)에서 `detail`이 문자열인지 배열인지 먼저 분기해서, 배열이면 각 항목의 `loc`/`msg`를 사람이 읽을 문장으로 합친다. 이 변환은 `client.ts` 한 곳에서만 하고 각 페이지가 직접 파싱하지 않는다 (`docs/CODING_RULES.md` 9번 참고).
