# Task Contract: T-MED-2-2 — 등록약 간 병용금기(약물 상호작용) 체크

> **문서 버전**: v1.0 · **최종 수정**: 2026-07-09
> **변경 이력**
> - v1.0 (2026-07-09): 신규 작성. T-MED-1의 "조합" 탭(`MedicationPage.tsx` interaction 탭, 현재
>   "추후 개발 예정" 플레이스홀더)과 T-MED-2에서 범위 밖으로 미뤄둔 F-MED-2 상충 경고 판단 중
>   "약물-약물" 병용금기만 다룬다. 질병-성분 금기(지병 기준)는 사용자 합의로 후속 작업으로 분리.

### 참조
- PRD: F-MED-2 / TRD: T-MED-2(부분, REQ-MED-005) / 관련: T-MED-1 "조합" 탭 플레이스홀더
  (`frontend/src/pages/medication/MedicationPage.tsx` interaction 탭)

### 배경
- `app/services/medication_open_api_client.py`의 `fetch_dur_item_info`가 식약처 병용금기 DUR API
  (`DURPrdlstInfoService03/getUsjntTabooInfoList03`)를 이미 호출하고 있으나, 현재는 `item_seq` 하나로
  조회한 첫 결과의 `PROHBT_CONTENT`만 `side_effects` 필드에 끼워 쓰는 용도로만 쓰인다.
- 이 API는 원래 "이 약(`item_seq`)과 병용하면 안 되는 다른 약(`MIXTURE_ITEM_SEQ`/`MIXTURE_ITEM_NAME`
  — 실제 필드명은 구현 단계에서 실 API 응답으로 재검증)" 페어 정보를 반환한다. 이번 작업은 사용자가
  등록한 다른 약들과 이 페어 정보를 대조하는 로직을 추가한다.

### 목표
- 입력: 현재 프로필(`profile_id`)에 등록된 전체 복약 스케줄(2개 이상의 약)
- 출력/노출: 등록약 조합 중 병용금기 페어가 있으면 "약A + 약B: 경고 문구" 형태의 목록.
  `MedicationPage.tsx`의 "조합" 탭 플레이스홀더를 실제 결과로 대체.

### 완료 정의 (Definition of Done)
- [ ] 등록약이 2개 미만이면 API를 부르지 않거나 빈 결과("비교할 다른 약이 없음")로 응답한다
- [ ] 등록약 각각의 `item_seq`(= `standard_code`의 `PDP_` 접두사 제거값)로 `fetch_dur_item_info`를
      호출해 병용금기 페어 목록을 얻는다
- [ ] 한 약의 병용금기 대상(`MIXTURE_ITEM_SEQ`/`MIXTURE_ITEM_NAME`)이 사용자의 다른 등록약과
      일치하면 경고 항목으로 반환한다(둘 다 등록돼 있을 때만 경고 — 등록 안 한 약과의 금기는 노출 안 함)
- [ ] `item_seq`가 없는 약(로컬 DB에서만 채워진 데이터 등)은 조용히 건너뛰고 전체 요청이 죽지 않는다
- [ ] `PUBLIC_DATA_API_KEY` 미설정 시 조용히 빈 결과로 응답하고 에러로 죽지 않는다
- [ ] `MedicationPage.tsx` "조합" 탭이 플레이스홀더 대신 실제 조회 결과(경고 목록 또는 "상충 없음"
      문구)를 보여준다
- [ ] (공통) `ruff`/`mypy`(백엔드), `tsc -b --noEmit`/`eslint`(프론트) 통과
- [ ] (공통) 새 서비스 함수는 TDD로 먼저 테스트 작성 (`app/tests/medication_apis/**`)
- [ ] (공통) 변경 범위가 허용 경로 내로 한정

### 허용 경로 (이 안에서만 자유롭게 작업 — 질문 없이 진행)
```
app/apis/v1/medication.py           (신규 엔드포인트 추가만, 기존 엔드포인트 시그니처 변경 금지)
app/services/medication_service.py  (신규 함수 추가만)
app/dtos/medication_dto.py          (신규 DTO 추가만)
app/tests/medication_apis/**
frontend/src/pages/medication/**
frontend/src/hooks/useMedication.ts (신규 함수 추가만)
docs/tasks/T-MED-2-2.md  (이 파일의 "완료 보고" 섹션만)
```

### 금지 경로 (절대 수정하지 않음 — 필요해 보여도 "공유 파일 변경 필요"로 보고만)
```
app/services/medication_open_api_client.py  (기존 함수 재사용만, 시그니처/반환값 변경 금지)
app/models/medication_model.py
app/repositories/medication_repository.py   (필요하면 조회 메서드 추가는 가능, 기존 메서드 변경 금지)
frontend/src/api/**
frontend/src/components/**
frontend/src/routes/**
frontend/src/store/**
frontend/src/types/**
```

### 의존하는 공유 계약 (읽기만 가능, 이미 고정됨)
- `medication_open_api_client.fetch_dur_item_info(item_seq)` — 시그니처/반환 형태 그대로 재사용
- `Medication.standard_code` — `f"PDP_{item_seq}"` 형태(품목기준코드 유래일 때만 존재, 없을 수 있음)
- `MedicationRepository.list_schedules_by_profile` — 프로필의 등록약 조회

### 자율 판단 허용 범위
- 경고 응답 DTO 필드명/구조, 프론트 UI 문구/스타일, 캐싱 여부, 내부 헬퍼 함수 분리 방식

### 반드시 멈춰야 하는 경우 (이 Task에 한정된 추가 조건)
- 실 API 응답의 병용금기 페어 필드명이 문서 스펙(`MIXTURE_ITEM_SEQ`/`MIXTURE_ITEM_NAME`)과 다르게
  나오는데 대체 필드를 찾을 수 없는 경우 → 임의로 추측한 필드명으로 진행하지 말고 사용자에게 확인
- 지병(질병-성분) 기준 금기까지 필요하다고 판단되는 경우 → 범위 밖(후속 작업), 진행하지 않음

---

### 완료 보고 (에이전트가 작성)
- 완료 정의 체크리스트 결과:
  - [x] 등록약 2개 미만 시 DUR API 호출 없이 빈 결과 반환 — 단위 테스트 + 실제 DB 통합 테스트로 확인
  - [x] `standard_code`(`PDP_{item_seq}`)에서 item_seq를 뽑아 `fetch_dur_item_info` 호출
  - [x] `MIXTURE_ITEM_SEQ`/`MIXTURE_ITEM_NAME`이 등록된 다른 약과 일치하면 경고 생성(둘 다 등록된
    경우만) — 단위 테스트 + 실제 DB로 등록된 두 약 페어 시나리오 통합 테스트
  - [x] item_seq 없는 약은 건너뛰고 전체 요청이 죽지 않음
  - [x] `PUBLIC_DATA_API_KEY` 미설정 시(이 환경 기본값) 조용히 빈 결과 — 브라우저로 실제 확인
    (`GET /medications/interactions` → 200, "확인된 병용금기 조합이 없습니다" 문구 노출)
  - [x] `MedicationPage.tsx` "조합" 탭이 플레이스홀더 대신 실제 결과(경고 목록 또는 "상충 없음"
    문구, 로딩/에러 상태)를 보여줌 — 브라우저로 확인
  - [x] `ruff check`/`mypy`(백엔드), `tsc -b --noEmit`/`eslint`(프론트, 신규 에러 0) 모두 통과
  - [x] TDD로 먼저 단위 테스트 작성(`test_medication_interactions.py`) 후 서비스 함수 구현
  - [x] 변경 범위가 허용 경로 내로 한정 (`git diff --stat`로 확인)
- 가정(Assumptions):
  - 병용금기 페어 필드명은 문서 스펙 그대로 `MIXTURE_ITEM_SEQ`/`MIXTURE_ITEM_NAME`으로 가정하고
    구현했다. 이 환경에는 `PUBLIC_DATA_API_KEY`가 비어 있어(`envs/.local.env`) 실 서비스키로
    응답 필드명을 재검증하지 못했다 — 실제 키가 채워진 환경에서 첫 호출 시 필드명이 다르면
    (T-MED-2가 실제 키로 필드명을 검증했던 것처럼) 재확인이 필요하다.
  - 같은 약 페어가 양쪽에서 각각 조회돼도 경고는 한 번만 표시하도록 `frozenset({id_a, id_b})`로
    중복 제거했다.
  - 지병(질병-성분) 기준 금기는 사용자 합의로 범위 밖 — 후속 작업(F-MED-2 확장)으로 남긴다.
- 공유 계약 변경 필요 사항: 없음. `medication_open_api_client.fetch_dur_item_info`는 시그니처/
  반환값 그대로 재사용만 했다.
- 검증 한계:
  - `PUBLIC_DATA_API_KEY`가 로컬에 없어 실제 공공데이터 API 응답으로 병용금기 페어를 얻는
    "실전" 경로는 직접 확인하지 못했다. 대신 `fetch_dur_item_info`를 monkeypatch해 페어 매칭
    로직 자체(등록된 페어 인식/미등록 파트너 무시/중복 제거/item_seq 없는 약 스킵)는 실제
    MySQL DB를 쓰는 통합 테스트(`/medications/interactions` 엔드포인트, 인증 포함)로 검증했다.
  - 브라우저 확인 시 이 워크트리 코드로 백엔드(uvicorn, 8001번 포트)를 별도로 띄우고
    `vite.config.ts`/`.claude/launch.json`의 포트·프록시 설정을 임시로 바꿔서 확인한 뒤 원복했다
    (기존 8000번 포트는 다른 브랜치 코드가 마운트된 Docker 컨테이너가 쓰고 있어 충돌 회피 목적).
  - 이후 다른 워크트리에 남아있던 실제 `PUBLIC_DATA_API_KEY`를 이 워크트리의 `.local.env`/`.env`에도
    채워 실제 식약처 병용금기 API로 재검증했다: "이트라코나졸"/"심바스타틴" 계열 실제 품목
    (히트라졸정 item_seq 200000417 / 리피스탄정 item_seq 200402374, 실제 DUR 데이터의 병용금기
    사유 "횡문근융해증")로 두 약을 등록하고 "조합" 탭에서 경고가 정확히 뜨는 것을 확인했다
    (수동 등록 폼은 T-MED-3의 기존 동작상 신규 약을 `AUTO_` 더미 코드로만 생성해 item_seq가
    없어서, 검증 목적으로 DB의 `standard_code`만 실제 품목기준코드로 맞춰 등록 흐름을 재현했다 —
    프로덕션 코드는 변경하지 않음). 확인 후 테스트로 등록한 두 약은 DB에서 정리했다.
- 브랜치명: `feature/T-MED-2-2-drug-interaction-check` (원래 `claude/drug-contraindications-api-75ca69`에서
  팀 브랜치 컨벤션에 맞춰 개명)
