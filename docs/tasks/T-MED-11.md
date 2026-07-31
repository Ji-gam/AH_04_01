# Task ID: T-MED-11 (약국명 오매칭 방지 + 더미 폴백 명시적 요청 한정)

### 배경

실제 처방전 사진으로 인식 결과를 확인하던 중 두 가지 오매칭이 발견됨: (1) 처방전 상단의 약국명
("SAMPLE*약국")이 실제 약품 후보로 잡혀 100% 매칭률로 표시됨, (2) CLOVA 미설정/호출 실패/빈 응답
환경에서 `_resolve_ocr_fields`가 조용히 더미 텍스트("*아스피린정" 등, confidence=1.0)로 폴백해,
`dummy_mode`를 명시적으로 요청하지 않았는데도 마치 실제로 인식된 약처럼 후보 목록에 나타남.

### 참조

- 관련 코드: `app/services/medication_service.py` (`_looks_like_drug_name`,
  `_fuzzy_match_unrecognized_fields`, `_resolve_ocr_fields`)
- 관련 이슈: #115

### 범위

- **포함**: 약국/병원/의원/한의원으로 끝나는 텍스트를 `_INSTITUTION_SUFFIX_PATTERN`으로 정의해
  `_looks_like_drug_name`(신규 등록 경로)과 `_fuzzy_match_unrecognized_fields`(퍼지 매칭 경로)
  양쪽에서 제외. `_resolve_ocr_fields`는 `dummy_mode=True`가 명시적으로 요청된 경우에만 더미
  텍스트를 반환하고, CLOVA 미설정/빈 응답은 빈 필드 목록을 반환해 기존 "OCR 근거 없음" 폴백
  (마스터 DB 상위 몇 개를 match_rate=0.3으로 참고 제시, T-MED-6)과 동일하게 처리되게 함.
- **제외**: 약국/병원명 판별 정확도 개선(주소/전화번호 패턴 등 추가 휴리스틱), OCR 전처리
  (전자레이아웃 분석 등) — 필요성이 확인되면 후속 과제.

### 완료 정의 (Definition of Done)

- [x] "*SAMPLE*약국"처럼 "*" 불릿이 붙은 약국명은 신규 약품으로 등록되지 않는다
- [x] "필독약국"처럼 불릿 없는 약국명도 퍼지 매칭으로 기존 약품에 매칭되지 않는다
- [x] `dummy_mode`를 명시 요청하지 않았는데 CLOVA가 미설정/실패/빈 응답이면, 더미 텍스트가
      confidence=1.0의 실제 인식 결과로 섞여 들어가지 않는다(기존 "근거 없음" 폴백과 동일하게 처리)
- [x] `dummy_mode=True` 명시 요청 시의 기존 동작(결정적 더미 후보 반환)은 회귀 없이 유지된다
- [x] (공통) 테스트를 TDD로 작성했고 `uv run pytest`가 통과한다

### 완료 보고

- 완료 정의 체크리스트: 전부 통과(`uv run pytest` 215 passed)
- 가정: 약국/병원/의원/한의원 4개 접미사만 우선 커버(다른 기관명 패턴은 후속 과제)
- 공유 계약 변경 필요 사항: 없음
- 브랜치명: `feature/T-MED-11-ocr-institution-name-dummy-fallback`
