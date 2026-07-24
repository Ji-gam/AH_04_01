# 결정 기록: 가족 몫 OCR 확정등록을 별도 함수로 분리 (의도적 코드 중복)

**작성일**: 2026-07-16
**관련 기능**: 가족관리 - 보호자가 처방전 사진으로 가족 구성원 몫 복약 등록

## 상황

`confirm_recognition_job`(OCR 확정등록)이 본인 몫으로만 등록하게 되어 있어서, 보호자가
가족 구성원 몫으로 등록하려면 이 함수를 확장해야 했습니다. 근데 이 시점에 다른 조원분이
`medication_service.py`의 OCR/수동 등록 매칭 로직(마스터 DB 불일치 수정 등)을 계속 활발히
고치고 계셔서, 같은 함수를 동시에 건드리면 병합 충돌 위험이 있었습니다.

## 결정

`confirm_recognition_job`을 수정하는 대신, **완전히 별도의 함수(`confirm_recognition_job_for_family`)
와 별도 엔드포인트(`POST /recognition/jobs/{job_id}/confirm-for-family`)를 새로 추가**했습니다.
로직은 90% 이상 동일하고 사실상 복붙 수준으로 중복됩니다.

## 왜 이렇게 했는지

| 대안 | 병합 충돌 위험 | 코드 중복 |
|---|---|---|
| A. `confirm_recognition_job`을 수정해서 target_profile_id 파라미터 추가 | 높음 (같은 함수를 동시에 수정) | 없음 |
| B. 공통 로직을 헬퍼 함수로 뽑아서 두 곳에서 호출 | 중간 (기존 함수 내부 구현을 바꿔야 함) | 없음 |
| **C. (채택) 완전히 새 함수/엔드포인트로 분리** | **낮음 (파일 끝에 새 코드만 추가)** | **있음 (의도적)** |

지금 상황(오늘 안에 기능을 끝내야 하고, 다른 조원이 관련 함수를 계속 고치는 중)에서는 **병합
안정성을 코드 중복보다 우선**시키는 게 맞다고 판단했습니다.

## 남은 문제 (다음 결정이 필요한 지점)

- `confirm_recognition_job`과 `confirm_recognition_job_for_family`가 앞으로 서로 다르게
  발전할 수 있습니다. 예: 조원분이 매칭 정확도를 개선해도, `_for_family` 버전은 자동으로
  좋아지지 않습니다.
- **제안**: 조원분의 OCR/매칭 로직 작업이 일단락되면, 그때 두 함수를 공통 헬퍼로 합칠지
  이 문서를 기준으로 같이 논의했으면 합니다.
- 그 전까지는 **`confirm_recognition_job_for_family`는 건드리지 않고, 개선은 항상
  `confirm_recognition_job` 쪽에만** 반영해주시면, 나중에 합칠 때 기준으로 삼기 편할 것
  같습니다.

## 추가 반영 (2026-07-16, 같은 날 후속)

같은 원칙을 `NotificationSchedule`(복약알림, `AlarmPage.tsx`) 도메인에도 적용했습니다.
이 도메인은 조원분이 최근 활발히 고치신 흔적이 없어서 상대적으로 안전하긴 했지만, 일관성을
위해 동일하게 "기존 메서드는 안 건드리고 `_for_family` 접미사가 붙은 새 메서드만 추가"하는
방식으로 진행했습니다.

- `app/services/notifications.py`: `list_schedules_for_family`, `create_schedule_for_family`,
  `update_schedule_for_family`, `delete_schedule_for_family` 추가 (파일 끝에 추가만, 기존
  4개 메서드는 그대로)
- `app/apis/v1/notification_routers.py`: `/notifications/schedules/family/{target_profile_id}`
  (GET/POST), `/notifications/schedules/{schedule_id}/for-family`(PATCH/DELETE) 4개
  엔드포인트 추가

또한 이번에 **가족관리(FamilyPage.tsx)에 있던 약 등록/조회/수정 UI는 전부 롤백**하고, 대신:
- 사진/검색 등록 → **트랙커(MedicationPage.tsx)**로 이동 (`FamilyRegisterSection.tsx`, 새 컴포넌트)
- 복약알림 보기/추가/토글/삭제 → **복약알림(AlarmPage.tsx)**로 이동, 가족 선택 시 화면
  전체가 `FamilyNotificationView.tsx`(새 컴포넌트)로 전환되는 방식

가족관리 화면은 이제 "연결(요청/승인/초대코드)"만 담당합니다.

## 추가 반영 (2026-07-16, 화면 UX 개편)

조원분 요청으로 "화살표 눌러서 펼쳐지는" 참가자목록 스타일 UI로 전환하고, 가족 화면을
본인 화면과 시각적으로 동일하게(달력+병합목록/4탭 전체) 만들었습니다.

- **`FamilySwitcher.tsx`(신규, 공용)**: "가족" 버튼 대신 화살표 하나로 "나 + 연결된 가족"
  목록이 펼쳐지고, 고르면 그 사람으로 화면이 전환됩니다. AlarmPage/MedicationPage 둘 다
  이 컴포넌트를 재사용합니다.
- **`FamilyNotificationView.tsx`(전면 재작성)**: 이제 본인 화면과 같은 `AlarmCalendar`/
  `ToggleSwitch` 컴포넌트를 그대로 재사용해서, 달력 + 약 복용시간까지 병합된 알림 목록을
  보여줍니다(그 사람 것만 - 본인 것과 안 섞임). 수정은 간단한 인라인 시간 수정으로 처리.
- **`FamilyTrackerView.tsx`(신규)**: 트랙커의 4개 탭(시간표/분석, 등록목록, 조합, 음식)을
  전부 가족 대상으로 조회하도록 새로 만들었습니다. 이걸 위해 `MedicationService`에
  `list_schedules_for_family`, `check_interactions_for_family`,
  `check_food_interactions_for_family`를 추가로 붙였습니다(기존 함수 재사용하는 얇은
  래퍼라 각각 몇 줄 안 됩니다).
- **`FamilyRegisterSection.tsx`는 삭제**했습니다 - 트랙커 화면 위에 별도 박스로 떠 있던
  방식 대신, 화면 전체가 전환되는 방식(`FamilyTrackerView`)으로 대체됐습니다.

위 재배치 이후, 예전 가족관리 "약 보기/수정" 기능에서만 쓰이던 아래 코드는 아무 화면에서도
안 불러서 삭제했습니다 (반쯤 만들다 만 게 아니라, 화면 자체가 없어졌으니 정리한 것):

- `app/dtos/family.py`의 `FamilyMemberMedicationItem`/`FamilyMemberMedicationSummary`
- `app/services/family_service.py`의 `get_member_medications`
- `app/apis/v1/family_routers.py`의 `GET /family/link/{link_id}/medications`
- `app/services/medication_service.py`의 `update_schedule_for_family`
- `app/apis/v1/medication.py`의 `PATCH /medications/{schedule_id}/for-family`
- `frontend/src/api/familyApi.ts`의 `getMemberMedications` 관련 타입/함수
- `frontend/src/api/familyMedicationApi.ts`의 `updateForFamily`

**`confirm_recognition_job_for_family`(사진 등록)와 `create_manual_schedule`의
`target_profile_id` 지원(검색 등록)은 지금도 트랙커 화면(`FamilyTrackerView.tsx`)이
그대로 쓰고 있어서 남겨뒀습니다.** `NotificationSchedule` 쪽 4개 메서드/엔드포인트도
복약알림 화면(`FamilyNotificationView.tsx`)이 전부 쓰고 있어서 그대로입니다.
