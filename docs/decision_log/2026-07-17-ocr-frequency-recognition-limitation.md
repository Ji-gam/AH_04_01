# 알아둘 것: 처방전 "N회" 자동인식은 임시 구현이며 한계가 있음

**작성일**: 2026-07-17
**관련 기능**: 트랙커 > 가족 몫 등록 > 사진(처방전) 탭의 복용 시간대 자동 슬롯 생성

## 뭘 만들었는지

`frontend/src/components/family/FamilyTrackerView.tsx`의 `deriveTimeSlots()` 함수 -
처방전 사진을 OCR로 인식한 뒤, 원문 텍스트에서 "1일 2회" 같은 표기를 정규식으로 찾아서
그 횟수만큼 복용시간 입력 칸을 자동으로 만들어준다 (1회→1칸, 2회→2칸, 3회→3칸...).

## 확인된 한계

**활자(인쇄체)로 또렷하게 "1일 2회"라고 적힌 경우는 잘 인식된다.** 근데 실제 테스트에서
아래처럼 **손글씨/특수 폰트/동그라미 표시 등으로 강조된 숫자**는 인식이 안 되는 케이스를
확인했다:

- 처방전 원본: "1일 `2`회" (숫자가 손글씨체/필기체 스타일)
- 결과: 시간 칸이 1개만 생성됨 (2회로 인식 안 됨)

## 원인

이 기능은 **OCR(CLOVA)이 이미 뽑아낸 텍스트 안에서** 정규식으로 "N회" 패턴을 찾는 방식이다.
즉 이 함수 자체의 로직 문제가 아니라, **OCR 엔진이 애초에 해당 텍스트를 정확히 텍스트로
뽑아내지 못하면(손글씨/특이 폰트 등) 이 함수가 참고할 원문 자체가 없어서** 손쓸 방법이 없다.

## 왜 더 안 고치기로 했는지

1. 원인이 이 함수의 로직이 아니라 **OCR 엔진 자체의 한계**라, 여기서 더 파고들려면 정규식을
   손보는 수준이 아니라 완전히 다른 접근(이미지 특정 영역만 잘라 별도 처리, 손글씨에 강한
   다른 OCR/비전 모델로 교체 등)이 필요함 - 지금 하는 "가족관리 기능 개발"과는 결이 다른,
   훨씬 큰 별도 작업.
2. 인식 실패해도 **안전망이 있음** - 기본 1칸으로 시작하고 "+시간 추가"로 클릭 한 번이면
   되므로, 사용자가 완전히 막히는 상황은 아님. 들이는 노력 대비 얻는 게 크지 않음.
3. 처방전마다 표기 스타일이 워낙 다양해서(인쇄체/필기체/동그라미/원문자 등), 이번 케이스
   하나를 맞춘다고 다른 케이스도 맞는다는 보장이 없음.

## 결론

**임시 구현으로 남겨두고 지금은 더 손대지 않기로 함.** 나중에 OCR 정확도 개선이나 손글씨
인식이 팀 우선순위에 오르면, 그때 이 문서를 참고해서 다시 검토하면 됨. 코드 자체에는 이
배경 설명을 다 넣지 않았음(주석이 너무 길어져서) - 필요하면 이 문서를 팀과 공유.

---

# 부록 2: 웹푸시 - 탭/브라우저를 닫으면 발송이 지연되는 문제 (2026-07-18)

**증상**: 알림 시각에 탭이 닫혀있으면 그 순간엔 안 뜨고, 나중에 사이트를 다시 열면(약
30초 내) 그제서야 뜬다. 반대로 사이트가 열려있는 상태에서는 정확한 시각에 바로 뜬다.

**확인한 것**:
- 백엔드 발송 로직(`push_scheduler.py`, `push_service.py`) 자체는 정상 - 시간 매칭
  버그(HH:MM vs HH:MM:SS 형식 불일치) 1건은 실제 원인으로 확인되어 고쳐서 반영함.
- `webpush()`의 `ttl` 파라미터(재시도 유예시간)도 한때 의심해서 늘려봤으나, 이 증상은
  "전달 실패"가 아니라 "전달은 됐는데 표시가 늦은 것"에 가까워 보여 원인이 아닌 것으로
  판단, 변수를 줄이기 위해 기본값(0)으로 원복함.
- Windows 방해금지 모드: 꺼져있음, 원인 아님.
- Edge의 "브라우저 닫혀도 백그라운드 앱/확장 계속 실행": 이미 켜져있었음, 원인 아님.
- "백그라운드 앱 권한"(전원 최적화/항상) 설정을 시도했으나, 이건 UWP 스토어 앱 전용
  옵션이라 데스크톱 Edge에는 해당 메뉴 자체가 없음 - 적용 불가.

**결론**: 이 이상은 이 PC의 Windows 네트워크 절전/최신 대기 모드(Modern Standby) 등
시스템 레벨 변수가 조합된 것으로 보이며, 사용자마다 PC 환경이 달라 완벽히 통제하기
어려운 영역이라 판단해 여기서 멈추기로 함. Gmail/Slack 같은 실제 서비스도 브라우저
백그라운드 상태에 따라 이런 지연을 100% 막지는 못한다 - 웹푸시 자체의 태생적 한계에
가깝다. 실사용 환경(모바일 브라우저)에서는 이 정도로 심하게 안 나타날 가능성도 있음.

**"알려진 한계"로 남겨둠**: 발송 로직 자체는 정상이나, 브라우저/OS의 백그라운드 상태에
따라 몇 초~몇십 초 지연될 수 있음. 나중에 앱(Capacitor) 패키징 시 네이티브 푸시(APNs/FCM)
로 전환하면 이 문제는 대부분 해결될 것으로 예상됨(네이티브 푸시는 OS가 직접 관리해서
이런 브라우저발 지연이 없음).

---

# 부록: 이번 PR에서 "남의 파일"에 추가한 부분 (공유용)

**작성일**: 2026-07-17
**대상**: `feature/family-medication-screens` 브랜치 - 트랙커(복약 관리)와 복약알림 둘 다
건드렸어서, 각각 나눠서 정리함. 조원분들께 "여기 이렇게 건드렸다" 공유하고, 나중에 병합
충돌 났을 때 참고할 용도.

**공통 원칙**: 기존 함수/로직은 전부 그대로 두고, **새 함수/새 엔드포인트를 파일 끝에 "추가"만
하는 방식**으로 진행했다(딱 하나, `AlarmPage.tsx`만 예외 - 아래 설명). 이유는 다른 조원분이
관련 파일(특히 `medication_service.py`, `medication.py`)을 동시에 활발히 고치고 계셨어서,
같은 함수를 동시에 수정하면 병합 충돌 위험이 높다고 판단했기 때문.

## 1. 트랙커(복약 관리) 쪽

### 건드린 파일과 추가된 것

| 파일 | 추가된 것 | 위치 |
|---|---|---|
| `app/dtos/medication_dto.py` | `RecognitionConfirmForFamilyRequest` 클래스 | 파일 중간(기존 `RecognitionConfirmRequest` 바로 아래) - 새 클래스 추가라 위치 상관없음 |
| `app/services/medication_service.py` | `confirm_recognition_job_for_family`, `list_schedules_for_family`, `check_interactions_for_family`, `check_food_interactions_for_family`, `delete_schedule_for_family` (총 5개 메서드) | **`MedicationService` 클래스 맨 끝**(`search_medications` 뒤) |
| `app/apis/v1/medication.py` | 위 5개에 대응하는 라우터 5개 (`confirm-for-family`, `/medications/family/{id}`, `/medications/interactions/family/{id}`, `/medications/food-interactions/family/{id}`, `DELETE /medications/{id}/for-family`) | **파일 맨 끝**(`search_medications` 라우터 뒤) |

기존 함수(`quick_register_medication`, OCR 매칭 로직, `confirm_recognition_job`, `check_interactions`, `check_food_interactions`, `search_medications` 등)는 **단 한 줄도 수정 안 함**.

### 생길 수 있는 문제

- **거의 없음** - 파일 맨 끝에만 붙여서, 조원분이 지금 고치고 계실 만한 지점(등록/매칭 로직 근처)과 물리적으로 멀다.
- 그래도 이론상 가능한 시나리오: 조원분도 같은 시점에 파일 맨 끝에 뭔가 추가하셨다면, git이 "같은 지점에 서로 다른 코드를 넣으려 한다"고 충돌 마커를 띄울 수 있음(내용이 안 겹쳐도 **위치가 겹치면** 마커는 뜬다).

### 꼬였을 때 처리법
```
<<<<<<< HEAD
(내가 추가한 _for_family 함수들)
=======
(조원분이 추가한 다른 함수)
>>>>>>> origin/dev
```
이런 식으로 뜨면 **둘 다 남기면 끝**이다. 서로 다른 이름의 독립 함수라 로직 충돌은 없음.
마커(`<<<<<<<`, `=======`, `>>>>>>>`)만 지우고, 순서는 아무렇게나 둬도 상관없음.

## 2. 복약알림 쪽

### 건드린 파일과 추가된 것

| 파일 | 추가된 것 | 위치 |
|---|---|---|
| `app/services/notifications.py` | `list_schedules_for_family`, `create_schedule_for_family`, `_get_guarded_schedule`(내부 헬퍼), `update_schedule_for_family`, `delete_schedule_for_family` | **`NotificationScheduleService` 클래스 맨 끝**(기존 `delete_schedule` 뒤) |
| `app/apis/v1/notification_routers.py` | `GET/POST /notifications/schedules/family/{id}`, `PATCH/DELETE /notifications/schedules/{id}/for-family` | **파일 맨 끝** |
| `frontend/src/pages/AlarmPage/AlarmPage.tsx` | 아래 별도 설명 | **파일 여러 지점** (아래 참고) |

### ⚠️ AlarmPage.tsx는 다른 파일들과 패턴이 다름 - 주의해서 봐주세요

이 파일만 "파일 끝에 추가"가 아니라 **기존 구조 안에 부분적으로 끼워넣었다**:
- **import 블록**(파일 최상단): `FamilySwitcher` import 한 줄 추가
- **상태 선언부**(컴포넌트 최상단): `selectedFamily` state 한 줄 추가
- **핸들러 함수 사이**: 기존 `handleDelete` 함수 바로 다음에 `handleDeleteMed`(새 함수) 추가
- **JSX 헤더 부분**: 제목 옆에 `<FamilySwitcher />` 삽입, 그리고 "가족 화면으로 조기 반환"
  분기(`if (selectedFamily) return (...)`) 통째로 추가
- **`row.med` 렌더링 부분**: 기존 ✏️(수정) 버튼 바로 뒤에 🗑️(삭제) 버튼 추가

**다만 확인한 바로는** - 지금까지 dev에 올라온 커밋 중 이 파일(`AlarmPage.tsx`)을 건드린
게 없었음(git log 기준). 그래서 지금 시점엔 위험이 낮지만, **다른 조원분이 앞으로 이
파일을 고치실 수도 있으니** 패턴이 다르다는 것만 알아두면 좋을 것 같음.

### 생길 수 있는 문제

- 트랙커 쪽(파일 끝 추가)보다는 충돌 가능성이 **조금 더 높음** - import문, state 선언부,
  헤더 JSX처럼 "누구나 건드릴 법한" 흔한 지점을 살짝 건드렸기 때문.
- 근데 **핵심 로직(달력/알림-약 병합/모달 편집 등)은 전혀 안 건드림** - 그러니 설령 충돌이
  나도 "같은 줄에 서로 다른 한 줄을 추가하려 한" 정도의 가벼운 충돌일 가능성이 높음.

### 꼬였을 때 처리법

- **import/state 선언부 충돌**: 대부분 "둘 다 남기기"로 해결됨(예: 조원분이 추가한 import
  한 줄 + 내가 추가한 `FamilySwitcher` import 한 줄, 둘 다 유지).
- **헤더 JSX 충돌**(제목 옆 영역): 조원분이 그 자리에 다른 버튼/UI를 넣으셨다면, **레이아웃을
  수동으로 다시 짜야 할 수 있음**(예: `<FamilySwitcher />`랑 조원분이 넣은 버튼을 나란히
  배치) - 이 지점만큼은 기계적으로 "둘 다 붙여넣기"가 아니라 사람이 한 번 보고 배치를
  정리해야 할 가능성이 있음.
- **`row.med`/`row.alarm` 렌더링 부분 충돌**: 마찬가지로 둘 다 남기되, 버튼 순서(토글→수정→삭제)
  가 어색해지지 않는지 한 번 눈으로 확인.

## 3. 그 밖에 참고

- `frontend/src/pages/FamilyPage/FamilyPage.tsx`: 예전 버전(약등록/보기 있던 것)에서
  연결관리만 남기는 걸로 **전면 재작성**했음. 이 파일을 다른 브랜치에서도 건드렸다면,
  내용이 아예 다르므로 자동병합에 의존하지 말고 전체를 눈으로 한 번 비교해봐야 함.
- `frontend/src/pages/medication/MedicationPage.tsx`: 트랙커 쪽과 마찬가지로 import 1줄 +
  `FamilySwitcher`/`FamilyTrackerView` 렌더링 부분만 건드림(원래 있던 OCR/수동등록
  로직 자체는 그대로 살아있음, 다만 그 UI 앞에 "가족이면 여기서 끝(early return)"이라는
  조건 분기를 추가한 구조).

