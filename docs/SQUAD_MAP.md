# SQUAD_MAP.md — 담당자 매핑 (유일 출처)

v2.0 · 이력: `git log docs/SQUAD_MAP.md`. "이 파일/기능 담당자"의 유일 출처 — 다른 문서에 같은 표 중복 금지. 짝문서: `CONTRIBUTING.md` §2, `CODING_RULES.md` §2,§3-6.

1. 스쿼드↔담당자↔T그룹 (파일명접두어 소유권, `CODING_RULES.md` §2)
A.인증/보안 — 심복규 — T-AUTH-1~6,T-SEC-1,T-STAT-1,T-PRIV-1,T-ENC-1,T-ARCH-1 — 접두어`auth_*`
B.복약인식/알림 — (인식)이은호/(알림)정다이 — T-MED-1~2,T-DOC-1~3,T-NTFY-1~6,T-CARD-1 — 접두어`medication_*`,`notification_*`
C.목표/추적/건강정보 — (이름) — T-GOAL-1~3,T-ADH-1~3,T-GUIDE-1,T-INFO-1~3,T-TRCK-1~3,T-DIET-1~2,T-ACC-1 — 접두어`tracking_*`,`diet_*`
D.LLM/AI — 박지은 — T-LLM-1~6,(T-QUAL-2 관련) — 접두어`chat_*`+`content_*`+`ai_worker/`

2. 백엔드 공통모듈 소유자 (`app/services/*`, 접두어 없음 — 담당자 외 임의수정 금지, 동시수정시 충돌집중)
계정/인증공통 — `app/services/auth.py`,`app/services/jwt.py` — 심복규
Profile공통 조회/수정 — `app/repositories/profile_repository.py` — 심복규
응급필터+면책정책 — `app/services/safety_service.py`(신설예정) — 박지은
질병/복약/목표 조회 단일창구 — `app/services/user_health_context_service.py`(신설예정) — (이름)
문서/알약인식(Tier2 stub) — `app/services/recognition_service.py`(신설예정) — 이은호
Push발송 — `app/services/notification_service.py`(신설예정) — 정다이
RAG Retriever/Context Binder — `ai_worker/`,`app/services/retriever_stub.py`,`app/services/llm_stub.py` — 박지은(근거:`docs/decision_log/2026-07-10-ai-rag-worker.md`)

3. 프론트 공통모듈 소유자 (`CODING_RULES.md` §3-6이 참조)
API클라이언트베이스 — `frontend/src/api/client.ts` — (이름)
인증상태공유훅 — `frontend/src/hooks/useAuth.tsx` — 심복규
면책조항 공통컴포넌트 — `frontend/src/components/common/DisclaimerBanner.tsx` — 박지은
챗봇스트리밍훅 — `frontend/src/hooks/useChatStream.ts` — 박지은