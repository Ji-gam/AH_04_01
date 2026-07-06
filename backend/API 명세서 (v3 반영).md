# API 명세서 (API_Specification_v3.pdf 반영본)

> `API_Specification_v3.pdf` + PRD/TRD를 기준으로 도메인 구조 백엔드에 실제 구현한 뒤, 서버를 직접 띄워서 검증한 결과입니다.

---

## 공통 사항

- **Base URL**: `/api/v1` (모든 경로 앞에 공통으로 붙습니다. 예: `/api/v1/users/signup`)
- **인증**: 이번 버전부터 **실제 JWT 인증이 동작**합니다.
  - `Authorization: Bearer <access_token>` 헤더 필요
  - 예외(인증 불필요): 회원가입, 로그인, 토큰 재발급, 이메일 중복확인 — **이 4개만** 인증 없이 접근 가능
  - `refresh_token`은 HttpOnly 쿠키로 브라우저가 자동 전송 (클라이언트 코드가 직접 다루지 않음)
- **공통 에러 형식**: `{ "detail": "에러 메시지" }` (v3 명세의 `status_code`/`error_code`/`timestamp`/`path` 포함 포맷은 아직 미적용, 지금은 FastAPI 기본 형식)

**범례**: 🟢 완료(실제 호출 테스트 통과) · ⬜ 확인 필요(동작하지만 TODO 또는 단순화됨)

---

## [M1] 회원 및 계정 관리 (Auth / User)

`prefix: /api/v1/users` — 🟢 전체 완료, 실제 JWT 발급까지 검증됨

| Method | URL | 설명 | 인증 | 상태 |
|---|---|---|---|---|
| POST | `/signup` | 회원가입 (LOCAL/GOOGLE 모두 수용) | 불필요 | 🟢 |
| POST | `/login` | 로그인 (JWT Access+Refresh 발급) | 불필요 | 🟢 |
| POST | `/logout` | 로그아웃 | 필요 | 🟢 |
| POST | `/refresh` | 토큰 재발급 (Cookie 기반) | 불필요 (Cookie로 검증) | 🟢 |
| GET | `/check-email` | 이메일 중복 확인 | 불필요 | 🟢 |
| GET | `/me` | 내 정보 및 개인화 설정 조회 | 필요 | 🟢 |
| PATCH | `/me` | 내 정보 및 개인화 설정 수정 | 필요 | 🟢 |
| DELETE | `/me` | 회원 탈퇴 (연관데이터 Cascade 삭제) | 필요 | 🟢 |

**회원가입 요청/응답 예시**
```json
// POST /signup 요청
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "name": "홍길동",
  "role_type": "PATIENT",
  "gender": "MALE",
  "birth_date": "1955-08-15"
}

// 201 Created 응답
{
  "user_id": 1, "email": "user@example.com", "name": "홍길동",
  "role_type": "PATIENT", "gender": "MALE", "birth_date": "1955-08-15",
  "sns_provider": "LOCAL", "created_at": "2026-07-03T01:30:00Z"
}
```

**로그인 요청/응답 예시**
```
// POST /login 요청 (Form Data, JSON 아님)
username=user@example.com&password=SecurePassword123!

// 200 OK 응답 (+ Set-Cookie: refresh_token, HttpOnly/Secure/SameSite=Strict)
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

---

## [M2] PWA 푸시 구독 관리

`prefix: /api/v1/pwa-subscriptions` — 🟢 완료 (단, 실제 발송 워커는 별도 구축 필요)

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| POST | `` | 푸시 구독 등록 (Upsert) | 🟢 |
| DELETE | `` | 푸시 구독 해지 | 🟢 |

> ⚠️ 구독 정보(endpoint_url, key 등) **저장만** 구현되어 있습니다. 실제로 사용자에게 푸시 메시지를 발송하는 백그라운드 워커/스케줄러는 API 명세 범위 밖이라 **별도 구축이 필요**합니다.

---

## [M3] 서포트 그룹 및 경쟁 관리

`prefix: /api/v1/support-groups` — 🟢 완료 (리더보드 점수 자동 증가만 미구현)

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| POST | `` | 서포트 그룹 생성 | 🟢 |
| POST | `/join` | 서포트 그룹 참여 (초대 코드 입력) | 🟢 |
| GET | `/{group_id}/members` | 그룹 멤버 및 리더보드 조회 | ⬜ |

> 📌 테이블에 `created_by`(방장) 컬럼이 없어, **생성 요청자를 GROUP_MEMBERS의 첫 멤버로 자동 등록**하는 방식으로 방장을 대신 식별합니다 (v3 명세서에도 명시된 제약).
> ⚠️ `leaderboard_score` 자동 증가(복약완료/식사체크 연동) 로직은 아직 없어서 항상 0에서 시작합니다.

---

## [M4] 응급 의료 카드

`prefix: /api/v1/emergency-cards` — 🟢 완료

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| GET | `` | 응급 의료 카드 조회 | 🟢 |
| PUT | `` | 응급 의료 카드 등록/수정 (Upsert) | 🟢 |

```json
// PUT 요청 예시 (전부 선택 필드)
{ "blood_type": "A+", "food_allergies": "복숭아, 밀가루", "medication_allergies": "페니실린 계열" }
```

---

## [M5] 진료 기록 및 처방약 관리 (Record / Medication)

`prefix: /api/v1/medical-records`, `/api/v1/medications` — 🟢 완료 (OCR·이미지검색은 단순화/보류)

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| POST | `/medical-records/ocr` | 처방전/약봉투 이미지 OCR 분석 | ⬜ |
| GET | `/medical-records/ocr/status/{task_id}` | OCR 처리 상태 조회 | 🟢 |
| POST | `/medical-records` | 진료 및 처방 기록 등록 (약물 매핑 포함) | 🟢 |
| GET | `/medical-records/{record_id}` | 진료 및 처방 기록 상세 조회 | 🟢 |
| GET | `/medications/{medication_id}` | 의약품 마스터 조회 | 🟢 |
| POST | `/medications/search-by-image` | 알약 이미지 기반 의약품 검색 | ⬜ |

> ⚠️ **OCR**: 실제 CLOVA OCR/S3 업로드/비동기 큐는 미구현입니다. 내부적으로 즉시 동기 처리 후 `SUCCESS`로 저장하지만, **API 계약(task_id 패턴)은 명세와 동일하게** 맞춰뒀습니다. 실제 OCR 엔진 연동 시 `record/router.py`의 `handle_ocr` 내부만 교체하면 됩니다.
> ⚠️ **알약 이미지 검색**: pgvector(PostgreSQL 확장) 도입이 보류되어 **항상 빈 배열만 반환**하는 스텁 상태입니다.

**진료기록 생성 예시 (핵심 로직: 처방 수량 자동 계산)**
```json
// POST /medical-records 요청
{
  "document_type": "PRESCRIPTION",
  "hospital_name": "서울성모병원",
  "visit_date": "2026-07-01",
  "medications": [
    {
      "medication_id": 200384,
      "dosage_per_take": "10클릭",
      "takes_per_day": 1,
      "duration_days": 30,
      "device_type": "MULTI_DOSE_PEN",
      "total_clicks_or_doses": 60
    }
  ]
}
```
> ✅ `remaining_quantity`(잔여량) 자동 계산 로직 포함 — `device_type=MULTI_DOSE_PEN`이면 `total_clicks_or_doses`로, 아니면 `total_prescribed_quantity`로 초기화합니다. 실제 호출 테스트로 검증했습니다.

---

## [M6] 복약 일정 및 수행 이력 (Schedule / IntakeLog)

`prefix: /api/v1/medication-schedules`, `/api/v1/intake-logs` — 🟢 완료

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| POST | `/medication-schedules` | 복약 알림 일정 등록 | 🟢 |
| GET | `/medication-schedules` | 복약 알림 일정 조회 | 🟢 |
| GET | `/intake-logs?start_date=...&end_date=...` | 복약 수행 이력 조회 (캘린더 뷰) | 🟢 |
| PATCH | `/intake-logs/{log_id}` | 복약 완료 수행 체크 (잔여량 자동 차감) | 🟢 |

> 📌 `intake-logs` 조회는 **쿼리 파라미터**(`start_date`/`end_date`)로 기간을 필터링합니다 — 예전에 "경로보단 쿼리파라미터로"라고 짚어주신 원칙을 반영했습니다.
> ✅ `PATCH /intake-logs/{log_id}`로 `COMPLETED` 처리하면 `device_type`에 따라 잔여량이 자동 차감됩니다 (예: 60클릭 → 10클릭 사용 → 50 확인. 실제 테스트로 검증됨).

```json
// PATCH /intake-logs/{log_id} 요청
{ "status": "COMPLETED", "actual_take_time": "2026-07-02T08:35:12Z" }

// 응답
{ "log_id": 102, "status": "COMPLETED", "remaining_quantity_after": 50 }
```

---

## [M7] 식사 이력 관리

`prefix: /api/v1/food-intake-logs` — 🟢 완료 (영양성분 자동분석만 미구현)

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| POST | `` | 식사 일지 등록 | ⬜ |

> ⚠️ `key_nutrients`(주요 영양성분 자동분석)는 실제 영양성분 분석 로직/외부 API 연동이 필요해서 항상 `null`로 저장됩니다.

---

## [M8] 약물-음식 상호작용 규칙

`prefix: /api/v1/drug-food-interactions` — 🟢 완료 (분석은 규칙기반 임시구현)

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| GET | `?medication_id=...` | 특정 의약품의 상호작용 규칙 조회 | 🟢 |
| POST | `/analyze` | 식사-투약 통합 위험도 분석 | ⬜ |

> ⚠️ v3 명세는 **LLM RAG로 자연어 경고문을 생성**해야 하지만, 지금은 사용자의 활성 스케줄과 매칭되는 규칙의 `guidance_text`를 단순히 이어붙이기만 합니다. 실제 LLM 연동은 조원 몫입니다.

---

## [M9] 건강 추적, 증상 및 병원 관리

`prefix: /health-metrics`, `/appointments`, `/symptom-logs` — ⬜ 등록만 구현, 조회 API는 전부 TODO

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| POST | `/health-metrics` | 건강 생체 지표 등록 (체중/혈압/혈당 등) | ⬜ |
| POST | `/appointments` | 병원 예약 및 의사 등록 | ⬜ |
| POST | `/symptom-logs` | 증상 기록 및 심각도 등록 | ⬜ |

> ⚠️ 세 도메인 다 **등록(POST)만 있고 목록/조회 API가 없습니다.** 추이 그래프나 이력 확인이 필요하면 각 도메인의 `router.py`에 GET 엔드포인트부터 추가해야 합니다.

---

## [M10] AI 챗봇 및 자동 가이드

`prefix: /chat`, `/generated-guides` — ⬜ 세션/저장 로직은 완료, LLM 실연동+SSE는 TODO

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| POST | `/chat/sessions` | 챗봇 대화 세션 개설 | 🟢 |
| GET | `/chat/sessions` | 챗봇 대화방 목록 조회 | 🟢 |
| POST | `/chat/sessions/{session_id}/messages` | 챗봇 메시지 전송 | ⬜ |
| POST | `/generated-guides` | LLM 맞춤형 가이드 자동 생성 | ⬜ |
| GET | `/generated-guides/{guide_id}` | 자동 생성 가이드 상세 조회 | 🟢 |

> ⚠️ **챗봇 메시지 전송**: v3 명세는 SSE 스트리밍 + 실제 LLM 응답을 요구하지만, 지금은 메시지 저장 + 고정 플레이스홀더 문구("아직 실제 AI 상담 기능이 연결되지 않았어요")만 반환합니다. 실시간 스트리밍이 아니라 일반 JSON 응답입니다.
> ⚠️ **가이드 자동생성**: 실제 LLM 호출 없이 고정 문구를 즉시 저장합니다. `title`/`visual_card_path`/`voice_audio_path` 컬럼은 v3 명세엔 없지만 PRD 요구사항(카드뉴스/TTS)을 위해 임시로 남겨뒀습니다 — 팀 논의 후 계속 쓸지 확정 필요합니다.

---

## [사내 테스트용] 의약품 정보 조회 (v3 명세엔 없음)

`prefix: /api/test` — ⬜ 정리 대상

| Method | URL | 설명 | 상태 |
|---|---|---|---|
| GET | `/test-drug-api/{pill_name}` | 의약품안전나라 Open API 연동 테스트 | ⬜ |

> 📌 v3 명세서에는 없는 사내 테스트 도구입니다. API 버저닝(`/api/v1`) 대상도 아닙니다. **정식 기능으로 편입할지, 삭제할지 팀 논의가 필요**합니다.

---

## 요약: 지금 상태

### 🟢 완전 구현된 도메인 (11개) — 실제 로직 + 호출 테스트 통과
Auth/User, PWA 구독, 서포트 그룹, 응급카드, 진료기록/의약품, 복약스케줄/수행이력, 식사기록, 약물-음식 상호작용(조회만), 챗봇(세션/메시지 저장), 가이드(저장/조회)

### ⬜ TODO로 남겨둔 것 (조원 구현 몫)
1. 건강지표/병원예약/증상기록 — 목록 조회 API 없음
2. AI 챗봇 — 실제 LLM 미연동, SSE 스트리밍 미구현
3. 가이드 자동생성 — 실제 LLM 미연동
4. 약물-음식 통합분석 — 규칙 텍스트 이어붙이기 수준
5. OCR — 실제 CLOVA/S3 미연동 (API 계약은 명세와 동일하게 맞춰둠)
6. 알약 이미지 검색 — pgvector 보류로 항상 빈 배열
7. 서포트그룹 리더보드 — 자동 증가 로직 없음, 항상 0

### 🚫 명세서 자체에 없는 것 (요구사항정의서엔 있었지만 API 설계 단계에서 빠진 것)
**목표·순응도 관리**(목표 설정 / 목표기반 가이드 / 달성 리포트) 도메인이 `API_Specification_v3.pdf`에 아예 없습니다. 백엔드를 아무리 손봐도 안 채워지는 부분이라, **명세서 자체에 먼저 추가**해야 합니다.
