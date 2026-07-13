# Task ID: T-MED-9 (CLOVA 글자 오인식 구제용 마스터 DB 유사도 매칭)

### 배경

T-MED-7/T-MED-8 수정 후에도 실제 처방전 사진 6개 중 1개("노스판패취10㎍/h")가 여전히 누락됨. 서버
로그로 필드 단위 원문을 확인한 결과, CLOVA OCR이 "패취"를 "매취"로 잘못 읽어("노스판매취10ug/h")
용량/제형 접미사 조건을 하나도 만족하지 못한 것이 원인이었다. 정규식 접미사 목록을 아무리 늘려도
다음 번 다른 글자 오인식은 여전히 못 잡는 근본적 한계라, 접근 자체를 바꿔야 했다.

### 참조

- 관련 코드: `app/services/medication_service.py` (`_fuzzy_match_unrecognized_fields`,
  `_best_fuzzy_candidate`, `_korean_only`), `app/repositories/medication_repository.py`
  (`list_medication_names`)
- 선행 작업: T-MED-8
- 관련 이슈/PR: #106, #107

### 범위

- **포함**: `_looks_like_drug_name`을 통과 못한 OCR 필드에 한해, 숫자/기호를 뗀 한글 부분만 마스터
  DB 약품명(마찬가지로 한글만 추출)과 편집거리(difflib) 기반 유사도로 비교하는 별도 경로. 임계값
  0.8(실측: 오탈자 케이스 ≈0.8, 노이즈 텍스트 대부분 0.3 미만). 이미 기존 경로로 처리된 필드나
  괄호/대괄호 성분·제조사명 표기 줄은 대상에서 제외. 새 AUTO_ 레코드는 만들지 않고 기존 마스터 DB
  레코드에만 매칭(모호한 텍스트로 엉뚱한 약 생성 위험 회피).
- **제외**: Tier1 SQLite(`dur_drug_light.db`) 연동 — 후속 태스크(T-MED-10)로 분리.

### 완료 정의 (Definition of Done)

- [x] `_looks_like_drug_name`이 거른 텍스트도, 마스터 DB 약품명과 한글 기준 유사도 0.8 이상이면
      기존 레코드에 매칭된다
- [x] 새 AUTO_ 레코드를 만들지 않는다(기존 DB에 있는 것만 인정)
- [x] 무관한 설명 문구(처방전 지시사항 등)로 인한 오매칭이 없다
- [x] (공통) 테스트를 TDD로 작성했고 `uv run pytest`가 통과한다
