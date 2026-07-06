# 실행 방법

두 샘플 폴더(`sample_code_chat/`, `sample_code_recog/`)는 각각 독립적으로 실행됩니다. **해당 폴더 안으로 들어가서** 실행하세요 (`app/` 패키지가 그 폴더 기준 상대경로이기 때문).

```bash
pip install fastapi "uvicorn[standard]" pytest pytest-asyncio httpx sqlalchemy

# 이 폴더(sample_code_chat/)에서: 테스트 실행 (10개 통과 확인됨)
PYTHONPATH=. pytest -v

# 서버 실행
PYTHONPATH=. uvicorn app.main:app --reload
# http://localhost:8000/docs 에서 확인
```

이 폴더 안 `app/`는 실제 레포의 레이어 우선 구조(`app/apis/v1`, `app/services`, `app/repositories`, `app/dtos`)를 그대로 축소 재현한 것입니다 — 복붙할 때 폴더 경로까지 그대로 옮기면 됩니다. 실제 레포는 SQLAlchemy(AsyncSession) + Alembic을 쓰지만(`CODING_RULES_v1.0.md` 참고), 여기 Repository는 데모라서 여전히 인메모리 가짜 저장소입니다 — 실제 기능을 만들 때는 `app/repositories/user_repository.py`, `app/repositories/profile_repository.py`의 실제 SQLAlchemy 패턴을 참고하세요. 테스트도 `app/tests/`의 실제 컨벤션(`httpx.AsyncClient` + `ASGITransport` + `starlette.status`)을 그대로 따릅니다.

여기에는 **두 가지 패턴 예제**가 있습니다:
1. **닉네임 중복확인** (이 폴더) — 순수 계층 분리(Router→Service→Repository) 기본형
2. **AI 챗봇 실시간 스트리밍** (`chat_service.py`, `chat_routers.py` 등, 이 폴더) — 여러 공통모듈(Safety/UserHealthContext) 오케스트레이션 + Retriever/LLM stub 패턴. `chat_flow_sequence.mermaid` 참고

`../sample_code_recog/`에는 세 번째 패턴 — **Tier 2 stub 패턴**(RAG 완성 전 임시 로직 → 완성 후 Service 내부만 교체)이 있습니다.

실제 개발 시작할 때 이 구조(Router→Service→Repository, 테스트 패턴)를 그대로 복사해서
다른 엔드포인트(로그인, 복약등록 등)에 적용하면 됩니다.

같이 보세요: `../CODING_RULES.md`, `./chat_flow_sequence.mermaid`(실시간 RAG 패턴), `../sample_code_recog/recognition_flow_sequence.mermaid`(Tier 2 stub 패턴)
