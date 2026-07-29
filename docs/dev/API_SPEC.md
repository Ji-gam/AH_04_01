# ReMedi API 명세 요약 (v1)

- 생성 방식: FastAPI 런타임 OpenAPI 추출 · 최종 갱신 2026-07-29 · 총 116개 엔드포인트
- 전체 스키마(요청/응답 본문, 필드 설명): [`api_spec_v1.yaml`](api_spec_v1.yaml)
  · Swagger UI: 로컬 실행 후 <http://localhost:8000/docs>
- 인증: `Authorization: Bearer <access_token>` (Access 30분 / Refresh 14일)
- 도메인 데이터 스코핑 기준은 `user_id`가 아니라 `profile_id`
- ERD: [`ERD.dbml`](ERD.dbml) (dbdiagram.io에 붙여넣기)
- 재생성: `python scripts/gen_api_docs.py` — 엔드포인트/모델 변경 시 같은 PR에서 함께 갱신
- `api_spec_core_v1_v1.1.yaml`은 Phase 1 설계 단계의 수기 초안으로, 위 문서로 대체됨(참고용)

## Chat

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/chat/sessions` | 채팅 세션 목록 조회 | O |
| `POST` | `/api/v1/chat/sessions` | 채팅 세션 생성 | O |
| `GET` | `/api/v1/chat/sessions/{session_id}/messages` | 채팅 메시지 이력 조회 | O |
| `POST` | `/api/v1/chat/sessions/{session_id}/messages` | 채팅 메시지 전송(스트리밍) | O |

## Content

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/contents/generate` | [관리자] 건강 콘텐츠 생성 | O |
| `GET` | `/api/v1/contents/me` | 건강 콘텐츠 피드 조회 | O |
| `GET` | `/api/v1/contents/{content_id}` | 건강 콘텐츠 단건 조회 |  |
| `GET` | `/api/v1/contents/{content_id}/related` | 관련 콘텐츠 조회 |  |

## DUR

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/dur/screening/basic` | Screen Basic | O |
| `POST` | `/api/v1/dur/screening/ingredient` | Screen Ingredient | O |
| `POST` | `/api/v1/dur/screening/interaction` | Screen Interaction | O |

## Family

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/family/invite-code` | 가족 초대코드 발급 | O |
| `POST` | `/api/v1/family/invite-code/redeem` | 가족 초대코드 사용 (즉시 연결) | O |
| `POST` | `/api/v1/family/link` | 가족 구성원 연결 요청 보내기 | O |
| `DELETE` | `/api/v1/family/link/{link_id}` | 가족 연결/요청 해제 | O |
| `POST` | `/api/v1/family/link/{link_id}/accept` | 받은 연결 요청 수락 | O |
| `POST` | `/api/v1/family/link/{link_id}/reject` | 받은 연결 요청 거절 | O |
| `GET` | `/api/v1/family/members` | 가족 연결 목록 조회 | O |

## Medications

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/medications` | 등록된 복약 스케줄 목록 | O |
| `POST` | `/api/v1/medications` | 복약 스케줄 수동 등록 | O |
| `GET` | `/api/v1/medications/family/{target_profile_id}` | 가족 구성원의 복약 스케줄 전체 조회 (가족관리) | O |
| `GET` | `/api/v1/medications/food-interactions` | 등록약 기준 음식/음주 주의사항 체크 (빠른 응답) | O |
| `GET` | `/api/v1/medications/food-interactions/family/{target_profile_id}` | 가족 구성원의 음식 상호작용 확인 (가족관리, 빠른 응답) | O |
| `GET` | `/api/v1/medications/food-interactions/pending` | 빠른 응답에서 확인되지 않은 약의 음식/음주 주의사항 체크 (느린 실시간 API) | O |
| `GET` | `/api/v1/medications/food-interactions/pending/family/{target_profile_id}` | 가족 구성원의 음식 상호작용 확인 (가족관리, 느린 실시간 API) | O |
| `GET` | `/api/v1/medications/interactions` | 등록약 간 병용금기(약물 상호작용) 체크 | O |
| `GET` | `/api/v1/medications/interactions/family/{target_profile_id}` | 가족 구성원의 병용금기 확인 (가족관리) | O |
| `POST` | `/api/v1/medications/quick-register` | 약품명으로 바로 등록 (검색 단계 생략) | O |
| `GET` | `/api/v1/medications/search` | 의약품 마스터 수동 검색 | O |
| `GET` | `/api/v1/medications/search-dur` | 의약품 DUR 및 효능 검색 API (MySQL + 공공데이터 폴백) | O |
| `DELETE` | `/api/v1/medications/{schedule_id}` | 복약 스케줄 삭제 | O |
| `PATCH` | `/api/v1/medications/{schedule_id}` | 복약 스케줄 부분 수정 | O |
| `DELETE` | `/api/v1/medications/{schedule_id}/for-family` | 가족 구성원 몫 복약 스케줄 삭제 (가족관리) | O |
| `PATCH` | `/api/v1/medications/{schedule_id}/for-family` | 가족 구성원 몫 복약 스케줄 부분 수정 (가족관리) | O |
| `POST` | `/api/v1/recognition/jobs` | 알약/처방전/진료기록 인식 요청 | O |
| `GET` | `/api/v1/recognition/jobs/{job_id}` | 인식 결과 조회 | O |
| `POST` | `/api/v1/recognition/jobs/{job_id}/confirm` | 사용자 최종 확인 → 복약 스케줄 자동 반영 | O |
| `POST` | `/api/v1/recognition/jobs/{job_id}/confirm-for-family` | 사용자 최종 확인 → 가족 구성원 몫으로 복약 스케줄 등록 (가족관리) | O |

## admin

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/admin/actions` | 관리자 행위 감사로그 조회 (관리자 전용) | O |
| `GET` | `/api/v1/admin/contents` | 건강 콘텐츠 목록 조회 (관리자 전용) | O |
| `DELETE` | `/api/v1/admin/contents/{content_id}` | 건강 콘텐츠 삭제 (관리자 전용) | O |
| `PATCH` | `/api/v1/admin/contents/{content_id}` | 건강 콘텐츠 수정 (관리자 전용) | O |
| `GET` | `/api/v1/admin/error-logs` | 서버 오류 로그 조회 (관리자 전용, AI챗봇 제외) | O |
| `GET` | `/api/v1/admin/notices` | 공지 목록 조회 (관리자 전용) | O |
| `DELETE` | `/api/v1/admin/notices/{notice_id}` | 공지 삭제 (관리자 전용) | O |
| `PATCH` | `/api/v1/admin/notices/{notice_id}` | 공지 수정 (관리자 전용) | O |
| `GET` | `/api/v1/admin/ops-stats` | 관리자 대시보드 운영 현황 조회 (관리자 전용) | O |
| `GET` | `/api/v1/admin/stats` | 관리자 대시보드 통계 조회 (관리자 전용) | O |
| `GET` | `/api/v1/admin/users` | 사용자 목록 조회 (관리자 전용) | O |
| `PATCH` | `/api/v1/admin/users/{user_id}/admin` | 관리자 권한 승격/해제 (관리자 전용) | O |

## auth

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 로그인 |  |
| `POST` | `/api/v1/auth/logout` | 로그아웃 |  |
| `POST` | `/api/v1/auth/signup` | 이메일 회원가입 |  |
| `GET` | `/api/v1/auth/token/refresh` | 액세스 토큰 재발급 |  |
| `DELETE` | `/api/v1/auth/withdraw` | 회원탈퇴 | O |
| `GET` | `/api/v1/auth/{provider}/callback` | 소셜 로그인 콜백 |  |
| `GET` | `/api/v1/auth/{provider}/login` | 소셜 로그인 시작 |  |

## diary

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/diary` | 저장된 '오늘의 한 줄' 전체 목록 조회(최신순) | O |
| `GET` | `/api/v1/diary/today` | 오늘 이미 작성한 '오늘의 한 줄' 조회 | O |
| `POST` | `/api/v1/diary/today` | 오늘의 한 줄 저장(다시 호출하면 오늘 기록을 덮어씀) | O |
| `DELETE` | `/api/v1/diary/{entry_id}` | '오늘의 한 줄' 기록 삭제 | O |

## diet

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/diet/logs` | 식사 기록 추가 | O |
| `DELETE` | `/api/v1/diet/logs/{log_id}` | 식사 기록 삭제 | O |
| `GET` | `/api/v1/diet/recent` | 최근 7일(오늘 포함) 일별 총 칼로리 조회 | O |
| `GET` | `/api/v1/diet/search` | 음식 이름으로 영양성분 검색 | O |
| `GET` | `/api/v1/diet/today` | 오늘 식사 기록 및 총 영양성분 조회 | O |

## diseases

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/diseases/{category}/subtypes` | 구체적 질환명 자동완성 검색 | O |

## exercise

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/exercise/logs` | 운동 기록 추가 | O |
| `DELETE` | `/api/v1/exercise/logs/{log_id}` | 운동 기록 삭제 | O |
| `GET` | `/api/v1/exercise/recent` | 최근 7일(오늘 포함) 일별 총 소모 칼로리 조회 | O |
| `GET` | `/api/v1/exercise/search` | 운동 이름으로 MET 값 검색 | O |
| `GET` | `/api/v1/exercise/today` | 오늘 운동 기록 및 총 소모 칼로리 조회 | O |

## goals

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/goals` | 목표(F-GOAL-1) 목록 조회 | O |
| `POST` | `/api/v1/goals` | 목표 생성 | O |
| `DELETE` | `/api/v1/goals/{goal_id}` | 목표 삭제 | O |
| `PATCH` | `/api/v1/goals/{goal_id}` | 목표 수정 | O |
| `POST` | `/api/v1/goals/{goal_id}/logs` | 목표 일일 수치 기록(오늘 기록하기) | O |

## habits

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/habits/recommendations` | 오늘의 추천 습관 목록 조회 (선택용, 매일 5개) | O |
| `POST` | `/api/v1/habits/selections` | 오늘 할 습관 선택(최대 5개, 0개도 허용) | O |
| `GET` | `/api/v1/habits/today` | 오늘 선택한 습관 목록 및 진행량 조회 | O |
| `POST` | `/api/v1/habits/today/{habit_key}/check` | 습관 1회 체크(진행량 +1) | O |

## intake

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/intake` | 특정 날짜의 복약 체크 목록 조회 | O |
| `GET` | `/api/v1/intake/daily-counts` | 날짜 구간별 복약 체크 개수 (히트맵용) | O |
| `POST` | `/api/v1/intake/toggle` | 복약 체크/체크해제 (F-ADH-1) | O |

## notices

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/notices` | 공지사항 목록 조회 | O |
| `POST` | `/api/v1/notices` | 공지사항 등록 (관리자 전용) | O |

## notification-log

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/notifications/inbox` | 홈 상단 🔔 알림함 - 최근 알림 목록 조회 | O |
| `POST` | `/api/v1/notifications/inbox/read-all` | 알림함 전체 읽음 처리 | O |

## notifications

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/notifications/schedules` | 복약 알림 일정 목록 조회 | O |
| `POST` | `/api/v1/notifications/schedules` | 복약 알림 일정 등록 | O |
| `GET` | `/api/v1/notifications/schedules/family/{target_profile_id}` | 가족 구성원의 복약 알림 일정 목록 조회 (가족관리) | O |
| `POST` | `/api/v1/notifications/schedules/family/{target_profile_id}` | 가족 구성원 몫 복약 알림 등록 (가족관리) | O |
| `DELETE` | `/api/v1/notifications/schedules/{schedule_id}` | 복약 알림 일정 삭제 | O |
| `PATCH` | `/api/v1/notifications/schedules/{schedule_id}` | 복약 알림 일정 수정 | O |
| `DELETE` | `/api/v1/notifications/schedules/{schedule_id}/for-family` | 가족 구성원 몫 복약 알림 삭제 (가족관리) | O |
| `PATCH` | `/api/v1/notifications/schedules/{schedule_id}/for-family` | 가족 구성원 몫 복약 알림 수정/토글 (가족관리) | O |
| `GET` | `/api/v1/notifications/settings` | 알림 커스터마이징 설정 조회 | O |
| `PATCH` | `/api/v1/notifications/settings` | 알림 커스터마이징 설정 수정 | O |

## push

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/push/mark-taken` | 알림에서 바로 복용 완료 처리 |  |
| `POST` | `/api/v1/push/reduce-frequency` | 알림 빈도 줄이기 |  |
| `POST` | `/api/v1/push/register-fcm-token` | FCM 등록 토큰 저장 | O |
| `POST` | `/api/v1/push/subscribe` | 웹푸시 구독 등록 | O |
| `POST` | `/api/v1/push/unregister-fcm-token` | FCM 등록 토큰 해제 |  |
| `POST` | `/api/v1/push/unsubscribe` | 웹푸시 구독 해제 |  |
| `GET` | `/api/v1/push/vapid-public-key` | 웹푸시 구독용 VAPID 공개키 조회 |  |

## sleep

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/sleep/logs` | 오늘 수면 기록 저장 | O |
| `GET` | `/api/v1/sleep/recent` | 최근 7일(오늘 포함) 일별 수면 기록 조회 | O |
| `GET` | `/api/v1/sleep/today` | 오늘 수면 기록 조회 | O |

## users

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/users/me` | 내 정보 조회 | O |
| `PATCH` | `/api/v1/users/me` | 내 정보 수정 | O |
| `GET` | `/api/v1/users/me/consent` | 동의 현황 조회 | O |
| `PATCH` | `/api/v1/users/me/consent` | 동의 기록 | O |
| `GET` | `/api/v1/users/me/health-info` | 개인건강정보 조회 | O |
| `PATCH` | `/api/v1/users/me/health-info` | 개인건강정보 수정 | O |

## weekly-reports

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/weekly-reports` | 저장된 주간 AI 리포트 목록 조회 | O |

## 기타

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/_debug/trigger-error` | Debug Trigger Error |  |
