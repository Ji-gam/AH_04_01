# Task ID: T-AUTH-2 (구글/네이버/카카오 소셜 로그인)

### 참조
- PRD: F-AUTH-2 / TRD: T-AUTH-2

### 목표
- 입력: 소셜 제공자(구글/네이버/카카오) 로그인 결과(인가 코드)
- 출력/노출: JWT(access_token, profile_id) 발급 + refresh_token 쿠키. 신규 사용자는 User+Profile(SELF) 자동 생성, 기존 이메일과 일치하면 자동 연결.

### 완료 정의 (Definition of Done)
- [x] 지원하지 않는 provider 요청 시 404
- [x] 제공자 토큰 발급 실패/사용자 식별값 누락 시 400
- [x] 이미 소셜 계정으로 가입된 사용자는 그대로 로그인 처리
- [x] 이메일이 같은 기존 로컬 계정이 있으면 새 계정을 만들지 않고 자동 연결
- [x] 완전 신규 사용자는 User + 기본 Profile(relation=SELF)을 한 트랜잭션으로 생성 (T-ARCH-1 준수)
- [x] (공통) `profile_id` 기준 설계 — User 대신 Profile을 참조/발급
- [x] (공통) 로그인/재발급 응답 바디에 `access_token` + `profile_id` 포함, `refresh_token`은 바디에 없음(쿠키만)
- [x] (공통) 테스트를 먼저 작성 후 구현 — 단, 이번 건은 기존 코드 이식 작업이라 순서상 구현이 먼저였고 테스트를 뒤이어 채움 (아래 가정 참고)
- [x] (공통) `uv run pytest -v` 통과 (19 passed)
- [x] (공통) Ruff 포맷/lint + Mypy 타입체크 통과

### 완료 보고

**완료 정의 체크리스트 결과**: 전부 충족 (위 체크박스 참고)

**가정(Assumptions)**:
- 소셜 제공자가 성별/생년월일/휴대폰번호를 기본 스코프로 주지 않아, Profile 생성 시 임시값(성별=MALE, 생년월일=2000-01-01, 휴대폰번호="")으로 채움. 로그인 후 "프로필 완성" 화면 유도는 이번 Task 범위 밖으로 판단.
- CORS는 `allow_origins=["*"]`가 아니라 `config.FRONTEND_URL`(정확한 origin)로 좁혀서 구현함 — `allow_credentials=True`와 `"*"`는 브라우저가 동시 사용을 거부하므로(쿠키 인증이 아예 안 됨), AGENTS.md 3장의 "로컬은 `*` 허용"보다 이 방식이 실제로는 필수라고 판단함. (→ 아래 "공유 계약 변경 필요"에도 기재)
- 기존 코드(before/Tortoise 버전)에서 이미 구현되어 있던 로직을 SQLAlchemy+Profile 구조로 이식하는 작업이라, TDD 원칙(테스트 먼저 RED→GREEN)의 엄격한 순서를 따르지 못하고 구현 후 테스트를 채웠음.

**공유 계약 변경 필요 사항** (진행하지 않고 보고만 함):
1. **응답 포맷 불일치** — `CONVENTIONS.md` 3-2는 모든 응답이 `{success, data, message}` 봉투 형식이어야 한다고 규정하나, 현재 `signup`/`login`/`token/refresh`(이번 Task 포함)는 전부 평탄한(flat) JSON을 반환 중. 전체 auth 도메인 + 다른 스쿼드 엔드포인트에도 동일하게 적용되어야 하는 전역 변경이라, 이번 Task 범위에서 단독으로 고치지 않음.
2. **파일명 규칙 불일치** — `CONVENTIONS.md` 2장은 `services/{도메인}_service.py` 형식을 요구하나, 기존 `app/services/auth.py`, `app/services/jwt.py`가 이미 이 규칙 이전 방식으로 존재함. 신규 파일(`app/services/oauth.py`)도 기존 형제 파일들과의 일관성을 우선해 같은 방식(접미사 없음)으로 만듦 — 전체를 리네임하려면 여러 파일의 import가 같이 바뀌어야 해서 범위 밖으로 판단.
3. **에러코드 체계 미적용** — `CONVENTIONS.md` 3-2의 `error_code`(`AUTH_001` 형식)가 auth 도메인 어디에도 아직 없음(기존 signup/login 포함). 이번 Task의 신규 에러(404/400/500)도 기존 관례(`detail="문자열"`)를 그대로 따름 — 도메인 전체를 한 번에 통일하는 게 맞다고 판단해 별도 변경 안 함.
4. **인증 스택 문서 불일치** — `AGENTS.md` 2장은 "python-jose", "Argon2(argon2-cffi)"라고 적혀 있으나, 실제 코드는 `pyjwt` + `passlib[bcrypt]`를 사용 중(기존 코드부터 이미 그러함). 문서만 갱신하면 될 사안으로 보임.
5. (참고, 버그) `app/core/jwt/tokens.py`의 `RefreshToken.lifetime`이 `timedelta(days=config.REFRESH_TOKEN_EXPIRE_MINUTES)`로 되어 있어, 분 단위 설정값(14*24*60=20160)이 그대로 "일"로 계산되어 실제로는 약 55년짜리 토큰이 발급됨. `app/apis/v1/auth_routers.py`의 `login`도 쿠키 만료시각을 refresh_token이 아닌 access_token 기준으로 설정 중. 둘 다 `app/core/`(공유 구역)라 이번 Task에서 수정하지 않음.

**브랜치명**: `feat/T-AUTH-2-social-login`
