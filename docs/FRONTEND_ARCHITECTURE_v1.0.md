# FRONTEND_ARCHITECTURE.md — AH_04_01 프론트엔드 협업 규칙

> **문서 버전**: v1.0 · **최종 수정**: 2026-07-07
> **변경 이력**
> - v1.0 (2026-07-07): `remedi_mweb_co`에서 이식. `frontend/`가 이 문서의 `pages/` 구조 그대로 실제 코드로 존재함(포팅 완료). 팀원 개인 이름은 역할 표기로 교체

> 이 문서는 `CODING_RULES_v1.0.md`(백엔드)의 **프론트엔드 짝 문서**입니다.
> 목적은 "예쁜 구조"가 아니라 **초보 5인이 동시에 작업해도 파일 충돌·구조 혼란이 안 나는 것**입니다.
> 각 섹션은 `베스트 프랙티스 → 우리 팀 조정 → 이유` 순서로 적혀 있습니다.

> ℹ️ **탭 구조는 가안입니다**: 5탭(홈 / 추적 / 상담 / Info / 더보기) 구성은 확정 아닙니다. UI/UX 영역이라 언제든 바뀔 수 있고, 바뀌어도 이 문서의 1~2, 4~7번(계층구조/상태관리/API연동/스타일/충돌방지 원칙)은 그대로 유효합니다.

---

## 0. 기본 스택

- React + Vite (SPA)
- React Router (클라이언트 사이드 라우팅, 서버는 `index.html` 1개만 서빙)
- Service Worker (Push 수신, 오프라인 캐싱)
- 인증: **JWT** (Access Token은 로그인 응답 body로, `Authorization: Bearer` 헤더로 요청에 첨부). Access Token은 메모리(React state)에만 두고 `localStorage`/`sessionStorage`에는 저장하지 않는다 — XSS로 토큰이 털릴 범위를 최소화하기 위함. Refresh Token은 백엔드가 `httpOnly` 쿠키로 내려주므로 JS에서 직접 읽거나 쓰지 않는다 — 프론트는 `fetch`/`axios` 호출에 `credentials: "include"`만 챙기면 된다 (`api/client.ts` 참고).

---

## 1. 계층 구조 — 백엔드의 "Router → Service → Repository"에 대응

```
Page (화면)  →  Hook (상태 + 판단 로직)  →  api/ 함수 (fetch)  →  서버
```

| 레이어 | 여기서 해도 되는 것 | 여기서 절대 하면 안 되는 것 |
| --- | --- | --- |
| Page (`pages/`) | 컴포넌트 조립, 레이아웃, Hook 호출 | `fetch` 직접 호출, 복잡한 판단 로직 |
| Hook (`hooks/`) | 상태 관리, 조건 분기, 여러 api 함수 조합 | JSX 반환 (Hook은 로직만, 화면은 Page가 그림) |
| api (`api/`) | fetch 호출, 요청/응답 형태 변환 | 화면 관련 판단 |

---

## 2. 상태 관리

**베스트 프랙티스**: Redux, Zustand 같은 전역 상태 라이브러리 + React Query.

**우리 팀 조정**: 전역 상태 라이브러리를 아예 도입하지 않는다. 상태는 기본적으로 **탭(페이지) 안에서만 로컬로 관리**하고, 정말 여러 탭이 공유해야 하는 것(로그인한 유저 정보 정도)만 Context/커스텀훅 1~2개로 최소화한다 (`hooks/useAuth.ts`).

**이유**: 상태관리 라이브러리는 개념이 하나 더 추가되는데, 초보 5인이 각자 다르게 쓰기 시작하면 "이 값은 어디서 바뀌는지" 추적이 오히려 더 어려워진다.

---

## 3. 폴더 구조 (탭 단위 소유권)

```
frontend/src/
├── App.tsx                    # React Router 설정 (5탭)
├── pages/
│   ├── HomePage/HomePage.tsx
│   ├── TrackPage/TrackPage.tsx + components/ (AdherenceHeatmapSection 등, 탭 내부는 섹션으로 구성)
│   ├── ChatPage/ChatPage.tsx
│   ├── InfoPage/InfoPage.tsx
│   └── MorePage/MorePage.tsx
├── components/common/           # 3개 이상 페이지에서 재사용될 때만 승격 (예: DisclaimerBanner)
├── api/                          # 엔드포인트당 함수 1개, api_spec_core_v1_v1.1.yaml과 1:1
├── hooks/                        # 페이지 전용이 아닌, 여러 곳에서 쓰는 훅만 (useAuth, useChatStream)
└── serviceWorker.ts
```

**규칙: 컴포넌트는 그 컴포넌트를 쓰는 페이지 폴더 안에 둔다.** 정말 여러 페이지에서 반복해서 쓰는 게 확인되면 그때 `components/common/`으로 옮긴다.

---

## 4. API 연동 레이어 & 타입

**우리 팀 조정**: React Query 같은 자동 캐싱 도구는 지금 도입하지 않는다. `api/` 폴더 함수 + 각 페이지 Hook에서 `loading / error / data` 3개 state를 다루는 동일한 패턴을 그대로 복사해서 쓴다. 타입도 백엔드 `app/dtos/*.py`를 보고 `api/types.ts`에 **수동으로** 정의한다 — 백엔드 스키마가 바뀌면 `api/types.ts`부터 고치고 팀에 공지한다.

---

## 5. 스타일링

유틸리티 클래스(Tailwind 등) 하나로 몰아준다. 컴포넌트별 커스텀 CSS 파일을 새로 만들지 않는다 — 클래스명 충돌과 중복 스타일을 방지하기 위함.

---

## 6. 공통 모듈 (소유자 지정 — 백엔드 `CLAUDE.md`와 동일한 취지)

| 공통 모듈 | 파일 | 제안 소유자 | 비고 |
| --- | --- | --- | --- |
| API 클라이언트 베이스 (fetch wrapper, 에러 응답 포맷 통일) | `api/client.ts` | 팀 협의 후 1인 지정 | 모든 `api/*.ts`가 이걸 통해서만 호출. 여기 바뀌면 전체 영향 |
| 인증 상태 공유 훅 | `hooks/useAuth.ts` | Auth 스쿼드 담당자 | 로그인 여부/유저 정보만 전역 공유 |
| 면책조항 등 규제성 공통 컴포넌트 | `components/common/DisclaimerBanner.tsx` | 담당자 지정 | 절대 임의 삭제/숨김 금지 |
| 스트리밍 훅 | `hooks/useChatStream.ts` | Chat/LLM 스쿼드 담당자 | ChatPage 전용이지만 로직이 복잡해서 소유자를 명시 |

**규칙**: 이 표에 있는 파일을 소유자가 아닌 사람이 고쳐야 할 일이 생기면, 직접 고치지 말고 소유자에게 요청한다. PR 제목에 `[공통모듈]` 태그를 붙인다.

---

## 7. Git 충돌 예방 (도구/규칙)

- **Prettier + ESLint를 CI에 강제 적용** → 포맷 차이로만 생기는 무의미한 diff 충돌을 원천 차단
- **PR은 한 페이지(탭) 폴더 위주로 작게 유지** → 여러 탭에 걸친 대형 PR 금지
- 커밋 메시지는 백엔드와 동일하게 `[T-ID] 설명` 형식 유지

---

## 8. 요약 (한 줄씩)

| 항목 | 정석 | 우리 팀 조정 | 핵심 이유 |
| --- | --- | --- | --- |
| 상태관리 | Redux/Zustand + React Query | 탭 로컬 state + Context/훅 최소 1~2개 | 개념 러닝커브, 소유 경계 명확화 |
| 컴포넌트 구조 | Atomic Design | 페이지 폴더 내 우선, 3+ 재사용 시 common 승격 | 분류 논쟁 방지, Git 충돌 격리 |
| API/타입 | React Query + 자동 타입생성 | 수동 fetch 패턴 + 수동 타입 정의 | API가 아직 자주 바뀌는 단계, 셋업비용 절감 |
| 스타일 | CSS-in-JS/디자인시스템 | 유틸리티 클래스 통일 | 클래스명 충돌 방지 |
| 충돌 방지 | 리뷰 중심 | Prettier/ESLint 강제 + 작은 PR | 자동화가 사람보다 안전 |

---

## 다음 액션 제안
1. 6번 공통 모듈 표의 소유자를 실제 팀원 이름으로 확정
2. `api/authApi.ts`/`api/types.ts`가 백엔드 `app/dtos/auth.py`/`app/dtos/users.py`(User/Profile 분리 반영)와 계속 맞는지, 도메인 추가할 때마다 확인
