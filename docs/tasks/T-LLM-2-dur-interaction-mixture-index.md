## Task ID: T-LLM-2-dur-interaction-mixture-index (T-LLM-2 하위 — 병용금기 상대성분 검색 공백)

> 작성자: 박지은(D스쿼드). 랭퓨즈 2단계(검색 span 계측) 실사용 테스트 중 실측으로 발견.
> 리더 승인 불필요 — `ai_worker/` 내부 파일만.

### 참조
- 실측(2026-07-28): "와파린 노인이 먹어도 돼?" → DUR 0건, 논문 0건.
- 관련: `ai_worker/source/_tuning.yaml`(metadata_columns), `ai_worker/services/retrieve_service.py`(`_build_filters`)

### 원인
병용금기 원본(`dur_usjnt_taboo.csv`)은 "성분A+성분B" 쌍을 `INGR_KOR_NAME`(주성분)/
`MIXTURE_INGR_KOR_NAME`(상대성분) 두 칸에 적는다. `_tuning.yaml`은 `INGR_KOR_NAME`만
`ingr_name` 메타데이터로 옮기고 `MIXTURE_INGR_KOR_NAME`은 안 옮긴다. 그래서 상대성분
쪽에만 등장하는 이름으로 물으면 검색 필터(`{"ingr_name": X}`)가 절대 못 찾는다 — 데이터는
있는데 반대쪽 칸에 있다는 이유만으로 0건.

실측 확인: 이 파일의 고유 성분 483개 중 **159개(33%)**가 상대성분 칸에만 있다(와파린 포함).

### 목표
- `MIXTURE_INGR_KOR_NAME`도 `mixture_ingr_name` 메타데이터로 추가 저장
- `_build_filters`의 성분 필터를 `ingr_name == X` 단독에서 `ingr_name == X OR
  mixture_ingr_name == X`로 확장 — 어느 쪽 칸에 있든 이름으로 찾아진다

### 완료 정의
- [x] `_tuning.yaml`에 `MIXTURE_INGR_KOR_NAME: mixture_ingr_name` 추가
- [x] `_build_filters`가 성분 필터를 `$or(ingr_name, mixture_ingr_name)`로 만든다(직접 성분
      매칭·브릿지 매칭 두 경로 다)
- [x] 로컬 재적재(`--force`, 내용 동일해도 메타데이터 갱신 위해 필요) 후 "와파린 병용금기"
      등으로 실측 확인 — 아래 완료 보고 참고
- [x] 기존 성분/제품 검색 무회귀
- [x] (공통) 테스트 함수명 영문, ruff/mypy 통과

### 허용 경로
```
ai_worker/source/_tuning.yaml
ai_worker/services/retrieve_service.py
ai_worker/tests/**
docs/tasks/T-LLM-2-dur-interaction-mixture-index.md
```

### 완료 보고 (구현 후 작성)
- 완료 정의 체크리스트 결과: 전 항목 충족. 로컬 `--force` 재적재(structured 30,798건 메타데이터
  갱신, 에러 0) 후 실측: `mixture_ingr_name=와파린` 문서 2건이 새로 검색 후보에 잡히고
  (전엔 0건), "와파린 병용금기"(3건)·"와파린 상호작용"(3건)·"메나테트레논이랑 와파린 같이
  먹어도 돼?"(1건)·"와파린 임산부가 먹어도 돼?"(1건) 전부 정상 반환 확인.
- 남은 관찰(이번 범위 밖): "와파린 노인이 먹어도 돼?"는 여전히 0건 — 원인은 이번 버그와
  무관. ①우리 데이터(`dur_odsn_atent.csv`, 노인주의)에 와파린 항목 자체가 없음(데이터 공백,
  MFDS 원본 문제로 추정) ②찾아진 임부금기/병용금기 문서 점수(0.374~0.399)가 임계값(0.35)을
  살짝 못 넘음 — DUR 정형 문구와 자연어 질의 간 임베딩 거리 문제로, T-LLM-2-rag-brand-name-bridge
  에서 이미 검토 후 "임계값은 안 건드린다"고 결론 낸 것과 같은 종류. 별개 이슈라 이번 스코프에
  안 넣음.
- 가정(Assumptions): 다른 DUR 파일엔 `mixture_ingr_name` 메타데이터 자체가 없으므로 `$or`의
  두 번째 절은 그 파일들에서 항상 미스(무해) — 실측(전체 재적재 후 무회귀 테스트)으로 확인.
- 공유 계약 변경 없음. `ai_worker/` 내부 파일만 변경.
- 브랜치명: `feat/T-LLM-2-dur-interaction-mixture-index`
