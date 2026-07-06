# AH_04_01 아키텍처 결정 로그

> **문서 버전**: v1.0 · **최종 수정**: 2026-07-07
> **변경 이력**
> - v1.0 (2026-07-07): `remedi_mweb_co`의 decision_log를 이식하며 `AH_04_01`로 이관하는 과정에서 새로 확정/변경된 내용을 반영. 이전 버전과의 핵심 차이는 아래 "AH_04_01 이관 시 변경된 결정" 참고.

## AH_04_01 이관 시 변경된 결정 (2026-07-07)

| 항목 | 이전(remedi_mweb_co) | 지금(AH_04_01) | 이유 |
| --- | --- | --- | --- |
| ORM | SQLAlchemy Async Engine (문서상 결정, 실제 구현 전) | **SQLAlchemy(AsyncSession) + Alembic** — 실제로 구현·마이그레이션까지 완료 | `AH_04_01`에 이미 적용돼 있던 학원 템플릿이 Tortoise ORM+aerich였는데, 팀이 원래 하려던 SQLAlchemy 기준으로 다시 맞춤. 지금이 auth/user 도메인 하나뿐이라 마이그레이션 리스크가 가장 적은 시점이라 판단 |
| 데이터 모델 | `profile_id` 기준 설계가 **결정만 되고 미구현** 상태로 남아 있었음 | **User/Profile 분리 완료**. `User`(계정/인증)와 `Profile`(개인정보 + 도메인 데이터 기준) 테이블을 분리하고, 회원가입 시 기본 Profile(`relation=SELF`)을 자동 생성. JWT payload에 `user_id`+`profile_id` 모두 포함 | 서포터그룹/가족 프로필 등록 기능을 나중에 추가할 때 기존 도메인 테이블 구조를 안 바꾸려면 지금(도메인이 auth/user 하나뿐인 시점)에 정리해야 함 |
| 프론트엔드 구조 | `pages/`(탭 단위) 기준으로 실제 코드 존재 | `pages/` 구조 그대로 이식, 표준으로 확정 | `AH_04_01`에 있던 `프론트엔드 작업 가이드.md`(features/ 구조)는 팀원 한 명이 도메인 우선 시절에 개인적으로 작성한 초안이라 최종 레이어 우선 구조와 안 맞음 — 폐기하고 실제 동작하는 `pages/` 코드를 표준으로 채택 |
| `dtos` 폴더명 | `app/dtos/` | `app/dtos/` (동일) | `AH_04_01` 템플릿에 있던 `app/dtos(schema)/`라는 오타성 폴더명(실제 import는 `app.dtos.*`)을 수정 |

## 확정된 기술 결정 (변경 없이 유지)

| 항목 | 결정 | 비고 |
| --- | --- | --- |
| 앱 형태 | PWA 단독 (Web Push) | 도달률 리스크 감수, 품질 미달 시 앱 전환 가능성 열어둠 |
| 프론트엔드 | React + Vite (SPA) | |
| 백엔드 구조 | 단일 FastAPI 앱, **레이어 우선 폴더 구조**(`app/apis`, `app/services`, `app/repositories`, `app/models`, `app/dtos`) | 도메인이 많아지면(15개 안팎 예상) 폴더가 잘게 쪼개져 팀원마다 코드 스타일이 제각각으로 갈릴 위험과, 레이어 우선은 같은 폴더 안에 여러 도메인 파일이 나란히 있어 옆 파일 패턴을 따라 하기 쉽다는 점(AI 에이전트가 대신 작성할 때도 동일)을 이유로 유지. AI/RAG/멀티모달 추론은 별도 서비스(`ai_worker/`)로 분리 |
| 인증 토큰 | **JWT** (Access — 응답 body, Refresh — httpOnly 쿠키) | Access Token은 프론트 메모리에만 보관 (XSS 방어) |
| RDB | **MySQL**, 비동기 필수 | SQLAlchemy AsyncSession + `asyncmy` 드라이버 |
| 마이그레이션 | **Alembic** | 위 표 참고 |
| Vector DB | ChromaDB (Server Mode) | RAG 완성 시점에 실제 도입 |
| 응급 키워드 감지 | 규칙 기반 사전 필터 (LLM 호출 전) | `docs/sample_code_chat/app/services/safety_service.py` 패턴 참고 |
| CI/CD | `ruff check`/`ruff format --check` + `pytest` (로컬은 `scripts/ci/*.sh`) | GitHub Actions 등록은 아직 (`CONTRIBUTING_v1.0.md` 8번 참고) |
| 환경변수/설정 관리 | `envs/` 2계층(예시+실값) + 루트 `.env` 심볼릭 링크, `pydantic-settings`로 타입 검증 | `CODING_RULES_v1.0.md` 2-2/2-3 참고 |

## 공통 모듈 (기능 간 결합 방지용)

| 공통 모듈 | 사용하는 기능 |
| --- | --- |
| **User Health Context Service**(질병/복약/목표 조회 단일 창구) | AI 챗봇 상담, 목표 기반 맞춤 가이드, 통합 정보 대시보드, 순응도 피드백 |
| **RAG Retriever / Context Binder** | AI 챗봇 상담, 약품 안전 정보 안내, 인식 데이터 기반 맞춤 가이드 |
| **문서 인식 서비스**(OCR 업로드~인식~컨펌 공통 흐름) | 알약 인식 및 복약 스케줄 등록 + 처방전/진료기록 인식 |
| **Push 발송 인프라** | 알림 전체, 가족 알림 |

## RAG 개발 기간 동안의 화면별 대응 전략 (Tier 구조)

| Tier | 대상 | RAG 필요 여부 | 처리 방식 |
| --- | --- | --- | --- |
| Tier 0 | 홈 위젯, 순응도 히트맵 | 없음 | RAG 완성 대기 없이 즉시 개발 |
| Tier 1 | 건강 콘텐츠 생성 파이프라인 | 생성만 필요 | 배치 생성 → 캐시 테이블 저장 → 화면은 캐시만 읽음 |
| Tier 2 | 약품 안전 정보 안내, 인식 데이터 기반 맞춤 가이드 | 사용자별 실시간 판단 필요 | RAG 완성 전까지는 Service가 규칙기반 stub 리턴 (`docs/sample_code_recog/` 실제 코드 참고) |
| 실시간 필수 | AI 챗봇 상담 | 있음 | RAG 파이프라인 완성 시점에 맞춰 통합 |

## 미결사항 (Open Issues)

| 항목 | 내용 | 영향 |
| --- | --- | --- |
| DUR 병용금기 데이터 수집 | 병용금기(DUR) 데이터 수집이 누락되어 있을 가능성이 있어 재확인 필요 | 약품 안전 정보 안내 |
| AI/RAG 워커 통신 방식 | 별도 서비스로 분리하기로 했으나, 큐 종류·동기 엔드포인트 프로토콜 등 상세는 미정 | RAG 설계 확정 시 이 문서에 반영 |
| Profile 다중 프로필 UI | User 1:N Profile 스키마는 준비됐지만, 프로필 전환/가족 초대 UI는 아직 없음 (Phase 2, T-AUTH-5/6) | 가족 관련 기능 착수 시 확정 |
