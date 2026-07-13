# DB Raw Viewer (임시 개발용 관리자 페이지)

`ENV=local`일 때 `/admin`에 뜨는 임시 DB 뷰어. sqladmin으로 만든 1회성 개발 도구로,
docker-compose의 `mysql` 컨테이너(= app 본체와 동일한 engine)를 그대로 보고 고친다.

- 접속: `http://localhost:8000/admin` (프론트 dev 서버가 아니라 FastAPI 서버 포트로 직접 접속)
- `app/models/` 아래 전체 모듈을 자동 import해서 매핑된 테이블을 전부 순회하므로, 새 모델이 추가돼도
  이 기능 자체는 수정할 필요가 없다.
- 비밀번호 컬럼도 해시값 그대로 노출(마스킹 없음), JSON 컬럼은 상세화면에서 들여쓴 멀티라인으로 표시,
  PK/FK는 컬럼명 옆에 라벨로 표시, 목록에서 행을 클릭하면 상세화면으로 이동한다.
- 인증 없음. 팀원 아무나 CRUD 가능한 상태이므로 `ENV=local` 밖에서는 절대 켜면 안 된다(현재 코드도 그렇게 가드돼 있음).

## 깨끗하게 삭제하는 방법

이 기능은 아래 4곳에만 흔적이 있다. 전부 지우면 이 기능 도입 이전 상태로 완전히 되돌아간다.

1. **`app/admin.py` 파일 삭제**
   기능 전체가 이 파일 하나에 들어있다 (모델 자동탐색, PK/FK 라벨, JSON pretty-print, 행 클릭 이동 전부 포함).

2. **`app/main.py` 끝의 4줄 삭제**
   ```python
   if config.ENV == Env.LOCAL:
       from app.admin import register_admin

       register_admin(app)
   ```
   FastAPI `app` 인스턴스가 `main.py`에만 있어서 마운트하려면 이 4줄이 불가피했다 (다른 파일에서 우회할
   방법 없음 — 있었다면 애초에 여기 안 넣었을 것).

3. **`pyproject.toml`의 `sqladmin` 의존성 한 줄 삭제**
   `[dependency-groups] app = [...]` 안에 있는 `"sqladmin>=0.28.0",` 줄을 지운다.

4. **`uv.lock` 갱신**
   ```bash
   uv lock
   ```
   위 명령으로 `sqladmin`과 그 하위 의존성(`wtforms` 등)이 lock 파일에서도 빠진다. `uv sync --group app`으로
   로컬 `.venv`도 맞춰준다.

5. **(도커로 띄운 경우) 이미지 재빌드**
   ```bash
   docker compose build fastapi && docker compose up -d fastapi
   ```
   재빌드하지 않으면 이미 빌드된 이미지 안에 `sqladmin`이 남아있을 뿐 동작에는 지장 없지만, 의존성 목록과
   실제 이미지 내용을 일치시키려면 재빌드해두는 게 깔끔하다.

이 문서(`docs/dev/DB_ADMIN_VIEWER.md`)도 같이 지운다.

## 삭제 안 해도 되는 것

- `app/models/`, `app/core/db/databases.py` 등 기존 앱 코드는 전혀 건드리지 않았으므로 그대로 둔다.
- `docker-compose.yml`, `app/Dockerfile`은 수정한 적이 없다.
