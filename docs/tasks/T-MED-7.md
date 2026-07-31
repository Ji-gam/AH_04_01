# Task ID: T-MED-7 (webp 등 CLOVA 미지원 이미지 포맷 변환)

### 배경

사용자가 복약안내문(처방전) 사진을 webp 포맷으로 업로드했을 때, 실제 사진 내용과 무관하게 항상 고정된
더미 텍스트("*타이레놀정", "*아스피린정")로 인식되는 문제가 보고됨. 실제 배포된 CLOVA 키로 재현한 결과,
`_build_clova_ocr_request`(`app/services/medication_service.py`)가 jpg/jpeg/png/pdf가 아닌 확장자는 실제
바이트 변환 없이 무조건 `format: "jpg"`로만 표시해 CLOVA에 전송하고 있었음. CLOVA는 "jpg"라고 표시된
webp 바이트를 디코딩하지 못해 `400 Request invalid`를 반환했고, 이게 조용히 더미 텍스트 폴백으로
이어져 사용자는 원인을 알 수 없는 상태였음.

### 참조

- 관련 코드: `app/services/medication_service.py` (`_build_clova_ocr_request`, `_convert_to_clova_supported_format`)
- 관련 이슈/PR: #101, #102

### 범위

- **포함**: CLOVA가 지원하지 않는 이미지 포맷(webp 등)을 png로 실제 변환한 뒤 전송. 변환 자체가
  실패하면(손상된 파일 등) 원본 바이트를 그대로 "jpg"로 보내 CLOVA의 거부 응답으로 실패가 드러나게 둔다
  (조용히 더미로 폴백하지 않는다는 T-MED-5 원칙 유지).
- **제외**: CLOVA가 지원하는 포맷 자체의 확장(HEIC 등 추가 포맷 지원), 이미지 전처리(회전/기울기 보정,
  해상도 조정) — 후속 과제.

### 완료 정의 (Definition of Done)

- [x] jpg/jpeg/png/pdf가 아닌 확장자는 Pillow로 png 변환 후 전송한다
- [x] 이미 지원되는 포맷은 변환 없이 원본 바이트를 그대로 보낸다
- [x] 변환 실패 시 원본 바이트를 그대로 "jpg"로 보내는 기존 폴백 경로를 유지한다
- [x] (공통) 테스트를 TDD로 작성했고 `uv run pytest`가 통과한다
