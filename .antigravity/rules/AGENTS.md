# AGENTS.md — ReMedi 프로젝트 하네스 규칙 (AI 워커 및 백엔드 전용)

이 문서는 코딩 에이전트(및 이 문서를 읽는 모든 팀원)가 따라야 하는 **작업 방식의 계약**입니다.
관련 문서: `PRD_ReMedi.md`, `TRD_ReMedi.md`, `docs/req-trace.md`, `CONVENTIONS.md`

---

## 0. 절대 원칙 (이 5줄이 전부입니다)

1. **자신에게 배정된 Task Contract(`docs/tasks/T-XXX-N.md`)에 적힌 "허용 경로" 안의 파일만 수정한다.**
   그 밖의 파일은 존재를 확인하는 것 외에는 절대 열거나 고치지 않는다.
2. **작업 시작 전 확인 질문을 하지 않는다.** 아래 "3. 이미 결정된 것"과 배정된 Task Contract만으로
   끝까지 진행한다. 정보가 부족하면 가장 합리적인 가정을 세우고 진행한 뒤, 완료 보고서의
   "가정(Assumptions)" 항목에 무엇을 가정했는지 적는다.
3. **아래 "4. 반드시 멈추고 물어야 하는 경우"에 해당할 때만 예외적으로 중단하고 보고한다.**
   그 외의 모든 판단(변수명, 내부 함수 분리, 에러 메시지 문구 등)은 에이전트가 스스로 결정한다.
4. **공유 구역(`app/core/`, `ai_worker/core/`, `envs/` 등 스키마·타입·계약 파일)은
   Task Contract에 명시적으로 허용되지 않는 한 절대 수정하지 않는다.** 필요하다고 판단되면
   수정하지 말고 완료 보고서에 "공유 파일 변경 필요" 항목으로 남긴다.
5. **작업 시작 시 `docs/tasks/_active.json`에 자신의 Task ID와 브랜치명을 등록하고, 종료 시 해제한다.**
   (에이전트-에이전트 충돌 방지용 클레임 파일. 아래 6번 참조)

---

## 1. 디렉토리 = 소유권 경계

`CONVENTIONS.md`에 따라 프로젝트는 **레이어별 폴더 구조**를 가집니다. 도메인 구분은 폴더가 아니라 **파일명**으로 합니다.

```
app/
  apis/v1/           # API 라우터 (v1 버전 관리) — 예: apis/v1/medication.py (로직 없음, 라우팅만)
  dtos/              # 데이터 전송 객체 (Pydantic DTOs) — 예: dtos/medication_dto.py
  models/            # DB 테이블 정의 (Tortoise ORM 모델) — 예: models/medication_model.py
  services/          # 비즈니스 로직 수행 — 예: services/medication_service.py
  core/              # [공유 구역] DB 설정, 환경 변수 등 핵심 인프라 및 JWT 의존성
ai_worker/
  tasks/             # AI 모델 추론 및 백그라운드 작업 정의 — 예: tasks/ocr_task.py
  core/              # [공유 구역] 워커 설정 및 로거
frontend/
  src/
    features/        # 프론트엔드 기능 컴포넌트 및 로직 — 예: features/medication/
    api/             # [공유 구역] API 연동 모듈 (자동 생성 또는 공통 클라이언트)
    components/      # [공유 구역] 공통 UI 컴포넌트
    routes/          # [공유 구역] 페이지 라우팅 구성
    store/           # [공유 구역] 상태 관리 (Zustand 등)
    types/           # [공유 구역] 공통 타입 선언
envs/                # [공유 구역] 환경 변수 설정 파일 (.env)
infra/               # [공유 구역] Nginx 리버스 프록시 및 도커 오케스트레이션 구성
scripts/             # [공유 구역] 빌드/포맷팅/테스트 자동화 스크립트
docs/
  tasks/             # Task Contract 파일들 (T-그룹당 1개)
  decisions/         # ADR (아키텍처 결정 기록)
  req-trace.md       # REQ ID ↔ 파일 경로 매핑표
```

**규칙**:
* 한 에이전트(또는 사람)는 한 번에 하나의 백엔드 기능 파일(예: `services/medication_service.py`) 또는 프론트엔드 기능 폴더(예: `frontend/src/features/medication/`) 또는 AI 테스크 파일만 소유한다.
* 같은 도메인에 속하는 파일이라도 레이어별로 소유권은 독립적으로 매핑되어야 하며, `docs/tasks/_active.json`으로 충돌을 방지한다.
* React 프론트엔드와 백엔드가 하나의 레포지토리 내에서 관리(모노레포)되지만, R&R 및 소유권 경계는 폴더 구조상에서 엄격히 준수한다.

---

## 2. 기술 스택 (미리 결정 — 질문 금지 대상)

> 이 섹션은 프로젝트 착수 시 팀이 확정한 기술 스택입니다. 이에 대해 에이전트는 추가적인 질문 없이 아래 규격에 맞추어 개발해야 합니다.

- 백엔드: FastAPI, Uvicorn, Tortoise ORM (비동기 전용 ORM)
- DB: MySQL 8.0 (Docker Container), Redis (비동기 작업 큐 및 캐시)
- 패키지 매니저: uv (`pyproject.toml`, `uv.lock`)
- 인증: JWT Token (Access Token 30분, Refresh Token 14일 만료, python-jose), Argon2 비밀번호 해싱 (argon2-cffi)
- LLM/AI 연동: OpenAI GPT API (챗봇 상담 및 맞춤형 가이드 생성), CLOVA OCR API (알약/처방전 이미지 텍스트 추출)
- 프론트엔드: React (Vite + TypeScript), Vanilla CSS, Zustand (상태 관리)
- 브랜치 전략: `feat/{T-ID}-{요약}` (예: `feat/T-MED-1-pill-ocr`)
- 커밋 컨벤션: Conventional Commits
- 성능 기준: API P95 Latency ≤ 3초가 모든 신규 엔드포인트의 기본 성능 기준 (T-QUAL-1)
- 개발 컨벤션: REST API 설계 원칙 준수, Ruff 포맷터 준수, Mypy 타입체크 필수 (`CONVENTIONS.md` 준수)

---

## 3. 이미 결정된 것 (에이전트가 재확인하지 않아도 되는 것들)

- 모든 LLM 응답에는 면책조항이 강제 노출된다 (T-LLM-1) — 새 LLM 기능을 만들 때도 기본 적용, 별도 확인 불필요.
- 개인 식별 정보(User)와 건강 정보는 항상 분리 저장한다 (T-ARCH-1). 동일 DB 내에 존재하더라도 함부로 직접 조인하여 노출시키지 않는다.
- 개인 식별 정보(PII) 비식별화(F-PRIV-1): 단순히 테스트용 정적 이름 치환 방식이 아닌, 정규식 및 NER(개체명 인식) 기법을 사용하여 이름, 연락처, 주민번호 등을 감지하고 실질적인 마스킹을 적용해야 한다.
- CORS 정책: `allow_origins=["*"]`는 로컬 개발을 위해서만 사용하며, 프로덕션 배포 혹은 보안 심의 시에는 Nginx 또는 FastAPI 미들웨어 허용 대상을 명확히 제어하도록 구현/주석을 작성해야 한다.
- 통계 API는 5명 이하 집계 시 자동 마스킹한다 (T-STAT-1).
- 병원 예약 및 조회 기능 등 스코프 외 기능: 현재 PRD/TRD 스코프에서 벗어난 임시 추가 기능이므로, 마이너한 버그 수정 외에 추가적인 고도화 개발을 하지 않으며, 핵심 기능(스케줄링, OCR, AI 챗봇, 알림)에 집중해야 한다.
- 새 DB 테이블 추가 시 **반드시** `app/models/{도메인}_model.py` 변경과 `docs/erd.md`를 동시에 갱신해야 한다.
- 핵심 기능은 3~5 액션 이내 접근 가능해야 한다 (T-QUAL-4, 평가기준 4-3).
- API P95 Latency ≤ 3초가 모든 신규 엔드포인트의 기본 성능 기준이다 (T-QUAL-1, 평가기준 5-1).
- Backlog 항목(⚠ 표시, 채팅/커뮤니티, 자체 AI 모델)은 이번 릴리스에서 착수하지 않는다. Task Contract 없이 이 범위의 코드를 작성하지 않는다.

---

## 4. 반드시 멈추고 물어야 하는 경우 (예외, 이것만)

- 공유 구역(`app/core/`, `ai_worker/core/`, `frontend/src/api/`, `frontend/src/components/`, `frontend/src/routes/`, `frontend/src/store/`, `frontend/src/types/`, `envs/`, `infra/`, `scripts/` 등) 파일이나 DB 공통 스키마 모델을 직접 수정해야만 작업이 가능한 경우
- Task Contract에 없는 새 외부 API/서비스 연동이 필요한 경우
- 성공요건(TRD)을 충족하려면 Task Contract에 명시된 "허용 경로" 밖의 파일 수정이 불가피한 경우
- 개인정보/보안 관련 비가역적 작업 (예: 암호화 방식 변경, PII 비식별화 핵심 로직 변경, 데이터 영구 삭제 로직 등)
- 두 Task Contract 간 요구사항이 서로 모순되는 경우

이 외의 모든 것은 "3. 이미 결정된 것" + Task Contract + 합리적 가정으로 끝까지 진행합니다.

---

## 5. 완료 시 자가 검증 (사람에게 리뷰 부담을 넘기지 않기 위해)

작업 완료 전, 배정된 Task Contract의 "성공요건 체크리스트"를 스스로 확인하고
`docs/tasks/T-XXX-N.md`의 "완료 보고" 섹션에 결과를 기록합니다. 실패 항목이 있으면
PR을 열지 않고 스스로 수정합니다. (→ TASK_CONTRACT_TEMPLATE.md 참조)

---

## 6. 에이전트 간 충돌 방지 (Claim 파일)

`docs/tasks/_active.json` 예시:

```json
{
  "T-MED-1": { "owner": "agent-B", "branch": "feat/T-MED-1-pill-ocr", "started": "2026-07-03" },
  "T-AUTH-1": { "owner": "agent-A", "branch": "feat/T-AUTH-1-email-signup", "started": "2026-07-03" }
}
```

- 작업 시작 전 이 파일을 확인해 같은 도메인 폴더가 이미 클레임되어 있는지 확인한다.
- 클레임되어 있다면 다른 Task를 배정받거나 사람에게 알린다 (진행하지 않는다).
- 작업 종료(PR 병합) 시 해당 항목을 제거한다.
- 이 파일 자체도 공유 구역이므로, 등록/해제 외의 다른 수정은 하지 않는다.

---

## 7. 평가기준 대응 메모

이 하네스 구조 자체가 고갱님 평가기준 6-1(역할 분담), 6-2(Git/PR 협업 도구 활용)의 근거 자료가 됩니다:
도메인 소유권 표 = R&R 문서화, 브랜치/PR/Task Contract 흐름 = 협업 도구 활용 증빙.
