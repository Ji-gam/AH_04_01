# squad-map.md — 담당자 매핑 (킥오프 때 채우기)

> **문서 버전**: v1.2 · **최종 수정**: 2026-07-08
> **변경 이력**
>
> - v1.0 (2026-07-07): `remedi_mweb_co`에서 이식. 표 구조는 그대로, 이름만 새로 채운다.
> - v1.1 (2026-07-07): `FRONTEND_ARCHITECTURE.md`가 `CODING_RULES.md`로 흡수되며 §6 표와의 중복 참조를 제거. `useAuth.ts`→`useAuth.tsx` 오탈자 수정(실제 파일이 Context/Provider라 확장자가 다름)
> - v1.2 (2026-07-08): T-LLM-3(건강 콘텐츠 생성 파이프라인) 착수하며 D 스쿼드 백엔드 파일 접두어에 `content_*` 추가
>
> 목적: "이 파일/기능은 누구 담당인지"를 이슈 번호나 파일명만 보고 바로 알 수 있게 한다.
> `CONTRIBUTING.md` §2, `CODING_RULES.md` 2번·3-6번과 짝을 이루는 문서. 이 문서가 공통모듈 소유자의 **유일한 출처**다 — 다른 문서에 같은 표를 중복해서 두지 않는다.

## 1. 스쿼드 ↔ 담당자 ↔ T-그룹

레이어 우선 구조라 폴더가 아니라 **파일명 접두어**로 소유권을 나눈다 (`CODING_RULES.md` 2번).

| 스쿼드                | 담당자                      | 담당 T-그룹                                                                   | 백엔드 파일 접두어               |
| --------------------- | --------------------------- | ----------------------------------------------------------------------------- | -------------------------------- |
| A. 인증/보안          | 심복규                      | T-AUTH-1~6, T-SEC-1, T-STAT-1, T-PRIV-1, T-ENC-1, T-ARCH-1                    | `auth_*`                         |
| B. 복약인식/알림      | (인식)이은호 / (알림)정다이 | T-MED-1~2, T-DOC-1~3, T-NTFY-1~6, T-CARD-1                                    | `medication_*`, `notification_*` |
| C. 목표/추적/건강정보 | _(이름)_                    | T-GOAL-1~3, T-ADH-1~3, T-GUIDE-1, T-INFO-1~3, T-TRCK-1~3, T-DIET-1~2, T-ACC-1 | `tracking_*`, `diet_*`           |
| D. LLM/AI             | 박지은                      | T-LLM-1~6, (T-QUAL-2 관련)                                                    | `chat_*` + `content_*` + `ai_worker/` |

## 2. 백엔드 공통모듈 소유자 (`app/services/*`, 접두어 없음)

같은 공통 파일을 두 사람이 동시에 고치면 그 지점에서 충돌이 몰린다. 담당자 외에는 임의 수정하지 않는다.

| 공통모듈                       | 파일                                                      | 담당자                              |
| ------------------------------ | --------------------------------------------------------- | ----------------------------------- |
| 계정/인증 공통                 | `app/services/auth.py`, `app/services/jwt.py`             | 심복규                              |
| Profile 공통 조회/수정         | `app/repositories/profile_repository.py`                  | _(이름)_                            |
| 응급필터 + 면책정책            | `app/services/safety_service.py` (신설 예정)              | _(이름)_                            |
| 질병/복약/목표 조회 단일창구   | `app/services/user_health_context_service.py` (신설 예정) | _(이름)_                            |
| 문서/알약 인식 (Tier 2 stub)   | `app/services/recognition_service.py` (신설 예정)         | 이은호                              |
| Push 발송                      | `app/services/notification_service.py` (신설 예정)        | 정다이                              |
| RAG Retriever / Context Binder | `ai_worker/`                                              | _(이름, decision_log.md 참고)_ |

## 3. 프론트 공통모듈 소유자 (`CODING_RULES.md` 3-6번이 참조하는 표)

| 공통 모듈              | 파일                                                  | 담당자                  |
| ---------------------- | ----------------------------------------------------- | ----------------------- |
| API 클라이언트 베이스  | `frontend/src/api/client.ts`                          | _(이름)_                |
| 인증 상태 공유 훅      | `frontend/src/hooks/useAuth.tsx`                      | _(이름, Auth 스쿼드)_   |
| 면책조항 공통 컴포넌트 | `frontend/src/components/common/DisclaimerBanner.tsx` | _(이름, T-LLM-1 담당)_  |
| 챗봇 스트리밍 훅       | `frontend/src/hooks/useChatStream.ts`                 | _(이름, RAG/Chat 담당)_ |

## 4. 3개 스쿼드로 줄일 경우

D(LLM)를 B 또는 C에 흡수하거나, A(인증/보안)를 C에 붙이는 방식을 추천한다 (`CONTRIBUTING.md` §2 참고).
