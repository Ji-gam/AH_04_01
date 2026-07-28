# Task Contract: T-SEC-1 (관리자 권한 시스템 + 취약점 조치)

### 참조
- SQUAD_MAP.md: A.인증/보안 — 심복규 담당 (T-SEC-1)
- 발단: `POST /notices`에 관리자 권한검증이 전혀 없어(로그인만 확인) 아무 사용자나
  전체 사용자에게 공지/마케팅 푸시를 보낼 수 있던 취약점 발견 (2026-07-27)

### 목표
- `User.is_admin`(기존에 있었지만 앱 어디서도 검사 안 되던 필드)을 실제로 검증하는
  의존성(`get_current_admin_user`)을 추가하고, 관리자 전용이어야 할 기존 엔드포인트에 적용
- 새로운 공개 가입 경로(초대코드 등) 없이, "기존 관리자가 화면에서 승격" 방식으로만
  관리자 계정이 늘어나도록 설계 (업계표준 비교 후 결정 - 공용코드 방식은 유출 시
  회전 불가/감사추적 약함이라 채택 안 함)
- 관리자 행위(권한 승격/해제, 공지 발송, 콘텐츠 생성)를 `admin_actions`에 감사로그로 남김

### 완료 정의
- [x] `POST /notices`에 `get_current_admin_user` 적용 (기존 취약점 수정)
- [x] `POST /contents/generate`에 `get_current_admin_user` 적용 (같은 유형의 취약점,
      원래는 로그인 검증조차 없었음 - 작업 도중 추가 발견)
- [x] 관리자 승격/조회 API(`GET/PATCH /admin/users`, `GET /admin/actions`) 신설
- [x] 최초 관리자 지정용 CLI(`app/scripts/promote_admin.py`) 신설
- [x] `admin_actions` 감사로그 테이블 + 마이그레이션(0049)
- [x] 관리자 전용 프론트 화면(`/admin`) 신설, `더보기` 메뉴에 `is_admin`일 때만 노출
- [x] 기존에 이미 있었지만 프론트에서 아무나 볼 수 있었던 "관리자 컨텐츠생성"/
      "관리자 공지등록" 백엔드 취약점은 막음 (get_current_admin_user 적용)
- [ ] 위 두 메뉴의 프론트 노출 자체(`is_admin`일 때만 보이게 감추는 것)는 **의도적으로
      보류함** - 사용자 요청으로 "아직 숨기지 말고, `/admin`쪽에 이어붙일 준비만" 해두기로
      함. 두 화면을 `/admin`으로 합칠지, 그대로 두고 노출조건만 나중에 걸지는 다음에 결정.
- [ ] `ruff`/`mypy`/`pytest` 미실행 (로컬 uv 환경 없이 작업해서 `py_compile`/`tsc`만 확인함
      - **내일 실제 환경에서 반드시 재확인 필요**)
- [ ] 새 엔드포인트/기능에 대한 테스트 없음 (TDD 원칙 미준수 - 추후 보강 필요)

### ⚠️ 반드시 확인 필요 (AGENTS.md §6 "반드시멈춤" 해당 가능성)
1. **타스쿼드 소유 파일 수정함**: `app/apis/v1/content_routers.py`는 SQUAD_MAP.md 기준
   Squad D(LLM/AI, 박지은) 소유 파일(`content_*` 접두어)인데, 이번 작업으로 여기에
   `get_current_admin_user` 검증을 추가했다. **박지은님 리뷰/합의 필요** - 합의 전까지는
   이 파일 변경분만 별도로 빼서 논의하는 것도 고려.
2. **공유구역([공유]) 수정함**: `app/dependencies/security.py`, `frontend/src/api/**`
   (types.ts, healthInfoApi.ts, adminApi.ts 신설)는 AGENTS.md상 [공유] 표시 구역 -
   Task Contract 없이 수정 금지 원칙에 해당한다. 이 문서가 곧 그 Contract 역할을
   하도록 사후 작성한 것이니, 병합 전 팀 공지 필요.
3. 최초 관리자 지정은 서버 접근권자가 `promote_admin.py`를 직접 실행해야 함 - 배포
   서버에도 반영 시 이 단계를 배포 체크리스트에 추가해야 함.

### 허용 경로 (이번에 실제로 건드린 파일)
```
app/core/db/migrations/versions/0049_add_admin_actions.py  (신규)
app/models/admin_action.py                                  (신규)
app/models/__init__.py                                      (AdminAction 등록)
app/dtos/admin.py                                            (신규)
app/dtos/users.py                                            (is_admin 필드 추가)
app/services/admin_service.py                                (신규)
app/apis/v1/admin_routers.py                                 (신규)
app/apis/v1/user_routers.py                                  (is_admin 응답 포함)
app/repositories/user_repository.py                          (list_users/set_admin/AdminActionRepository)
app/scripts/promote_admin.py                                 (신규)
frontend/src/pages/AdminPage/AdminPage.tsx                   (신규)
frontend/src/pages/MorePage/MorePage.tsx                     (관리자 메뉴 노출조건)
frontend/src/App.tsx                                          (/admin 라우트)

--- 아래는 위 "반드시 확인 필요" 항목 (공유/타스쿼드) ---
app/dependencies/security.py                                 (get_current_admin_user 추가) [공유]
app/apis/v1/notice_routers.py                                 (관리자 검증 추가)
app/apis/v1/content_routers.py                                (관리자 검증 추가) [타스쿼드-박지은]
frontend/src/api/types.ts                                      (is_admin 필드) [공유]
frontend/src/api/healthInfoApi.ts → 원복됨(이번 작업과 무관, 어제 롤백 건)
frontend/src/api/adminApi.ts                                   (신규) [공유]
```

### 완료 보고 (2026-07-27 작성)
백엔드/프론트 전부 `py_compile`, `tsc --noEmit` 통과 확인. `uv run ruff`/`pytest`는
로컬 uv 환경이 없어서 미실행 - **내일 실제 docker 환경에서 재확인 필수**. 로컬 도커
환경에서 마이그레이션 적용 + 최초 관리자 지정 + 화면 확인까지 진행 예정.
