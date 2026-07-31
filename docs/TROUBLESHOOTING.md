# TROUBLESHOOTING.md — 증상→원인→조치

v1.1 · 이력: `git log docs/TROUBLESHOOTING.md`.

A. 로컬 MySQL/포트에 이미 무관한 데이터/프로세스가 있음
증상: DB접속은 되는데 무관한 테이블이 보임, 또는 `GRANT`/로그인이 예상과 다름.
원인: 이 컴퓨터에 다른 프로젝트/이전 실습이 같은 이름 DB/유저를 이미 사용중.
조치: 기존 DB drop/유저삭제 절대 금지(되돌릴 수 없는 사고) — `envs/.local.env`에 이 프로젝트 고유 DB이름을 새로 지정(예: 레포이름 접두어). 확인:
```bash
mysql -uroot -e "SHOW DATABASES;"
mysql -uroot -e "USE 그이름; SHOW TABLES;"
```

B. 포트 충돌 (3306/8000/5174 등)
증상: `bind: address already in use`, docker-compose 컨테이너 기동중 멈춤, preview 서버 시작실패.
원인: 다른 프로세스(대개 다른 프로젝트)가 그 포트 점유중.
조치: `lsof -i :포트번호 -sTCP:LISTEN`으로 확인, 본인이 띄운 게 아니면 죽이지 않음. 대신 Docker=`docker-compose.override.yml`(커밋안함)로 다른 호스트포트 매핑, Vite=`vite.config.ts`의 `server.port`/`proxy` 임시변경. 검증 끝나면 팀표준값(8000/5174/3306)으로 원복+override파일 삭제 — 커밋에 남기지 않음.

C. Docker 컨테이너 안에서 `alembic`이 `No 'script_location' key found`
원인: `Dockerfile`이 `alembic.ini`를 이미지에 COPY 안 함(코드만 복사, 루트 설정파일 누락).
조치: `Dockerfile`의 COPY 목록에 `alembic.ini` 추가, 이미지 재빌드(`docker compose up -d --build <서비스명>`).

D. SQLAlchemy `InvalidRequestError: A transaction is already begun on this Session`
원인: 앞선 조회(중복체크 SELECT 등)가 이미 트랜잭션 autobegin, 그 뒤 `async with session.begin():`으로 또 명시적 트랜잭션 시도.
조치: 요청1개=write유닛1개면 중간에 `session.begin()` 쓰지 말고 마지막에 `await session.commit()`만. `session.begin()`은 그 시점 트랜잭션이 전혀 없다고 확신할 때만.

E. pytest에서 `RuntimeError: Task ... attached to a different loop`
원인: 세션스코프 fixture(DB엔진 등)와 개별 테스트함수가 다른 asyncio 이벤트루프에서 실행(pytest-asyncio 기본값=테스트마다 새 루프).
조치: `pyproject.toml`의 `[tool.pytest.ini_options]`에 추가:
```toml
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

F. 레포루트에서 `pytest` 실행시 `docs/dev/sample_code_*/` 안 테스트까지 잘못 수집돼 깨짐
원인: 그 폴더들은 각자 독립 `app` 패키지를 가진 예제라 진짜 앱 `app` 패키지와 이름충돌. pytest가 rootdir 전체 훑으면 충돌.
조치: `pyproject.toml`의 `[tool.pytest.ini_options]`에 `testpaths = ["app/tests"]` 지정(이미 설정됨). `docs/dev/sample_code_*/`는 그 폴더 안에서 `PYTHONPATH=. pytest -v`로 별도 실행.

G. 백엔드 응답스키마 변경(필드추가 등)했는데 프론트가 안 맞음
원인: 백엔드-프론트 타입동기화는 수동규칙(`CODING_RULES.md` §3-4).
조치: `app/dtos/*.py` 변경 커밋/PR 안에 `frontend/src/api/types.ts`도 같이 수정 — 다른 PR로 쪼개지 않음.

H. `git status`에 `.omc/`,`node_modules/`,`__pycache__/`,`.pytest_cache/` 등이 계속 걸림
조치: 새 프론트/파이썬 산출물 디렉터리 추가시 `.gitignore`에 패턴 추가(임시 unstaging이 아니라). `node_modules/`,`.omc/`는 이미 등록됨.

I. 프론트에서 에러메시지가 `[object Object]`로만 찍힘
증상: 회원가입/로그인 실패시 화면에 `[object Object]`만 뜸.
원인: FastAPI 422 검증실패 응답의 `detail`이 배열로 오는데(`{"detail":[{"loc":[...],"msg":"..."}, ...]}`), 문자열만 가정하고 `new Error(body.detail)`로 그대로 넘겨 배열이 문자열로 강제변환됨.
조치: 에러파싱 규칙 전문 — `CODING_RULES.md` §9. 수정지점: `frontend/src/api/client.ts` 1곳.
