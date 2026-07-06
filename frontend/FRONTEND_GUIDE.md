# React 프론트엔드 작업 가이드

> 백엔드의 "도메인 구조 작업 가이드.md"와 짝이 되는 문서입니다. 폴더 구조를 백엔드 도메인과 최대한 1:1로 맞췄습니다.

## 1. 실행 방법

```bash
npm install
cp .env.example .env   # 필요하면 VITE_API_BASE_URL 수정
npm run dev
```
- 백엔드가 `http://127.0.0.1:8000`에서 돌고 있으면 `vite.config.ts`의 프록시 설정 덕분에 CORS 신경 안 쓰고 바로 붙습니다.
- `npm run build`로 프로덕션 빌드, `npx tsc --noEmit`으로 타입 체크만 따로 할 수 있습니다.

## 2. 폴더 구조

```
src/
├── api/
│   ├── client.ts          ← axios 인스턴스. JWT 자동 첨부 + 401시 자동 재발급. 손댈 일 거의 없음.
│   └── endpoints/         ← 도메인별 API 호출 함수 (15개 도메인 전부 이미 만들어져 있음)
├── types/index.ts         ← 백엔드 스키마와 대응하는 TypeScript 타입
├── store/authStore.ts     ← 로그인 상태 (Zustand)
├── routes/
│   ├── router.tsx         ← 전체 라우트 정의 (새 화면 만들면 여기 등록)
│   └── ProtectedRoute.tsx ← 로그인 안 하면 /login으로 튕기는 가드
├── components/ui/
│   ├── Layout.tsx          ← 사이드바 + 메뉴 (새 메뉴 추가하려면 NAV_ITEMS 배열에 추가)
│   └── PlaceholderPage.tsx ← 아직 안 만든 화면에 쓰이는 "TODO" 표시용 컴포넌트
└── features/               ← 도메인별 화면 (15개 폴더, 백엔드 domains/와 이름 맞춤)
    ├── auth/               ← ✅ 완성 (로그인/회원가입)
    ├── schedule/           ← ✅ 완성 (목록+등록 폼, React Query 패턴 예시)
    └── (나머지 13개)        ← 🚧 PlaceholderPage만 있음, 조원이 채울 자리
```

## 3. 새 화면을 만들 때 (예: 응급 의료 카드)

1. **API 함수 확인**: `src/api/endpoints/emergencyCard.ts` 를 열어보면 `get()`, `upsert()` 함수가 이미 있어요. 새로 안 만들어도 됩니다.
2. **훅 만들기**: `src/features/schedule/useSchedules.ts` 를 복사해서 `src/features/emergency_card/useEmergencyCard.ts` 로 만들고, React Query의 `useQuery`/`useMutation`으로 감싸세요.
3. **화면 만들기**: `src/features/schedule/SchedulePage.tsx` 구조를 그대로 참고해서 `src/features/emergency_card/EmergencyCardPage.tsx` 를 채우세요 (지금은 `PlaceholderPage`만 렌더링하고 있음 — 이 부분을 실제 폼/목록으로 교체).
4. **디자인**: `var(--panel-bg)`, `var(--accent-cyan)` 같은 CSS 변수를 `style={{ }}`로 쓰는 방식을 그대로 따라 하면 톤이 자동으로 맞습니다 (변수는 `src/index.css`에 정의되어 있음). Tailwind 유틸 클래스(`flex`, `rounded-xl`, `p-4` 등)와 섞어 써도 됩니다.
5. 라우트는 이미 `router.tsx`에 등록되어 있어서 손 안 대도 됩니다 (컴포넌트 내용만 채우면 바로 반영됨).

## 4. 인증 흐름 참고

- 로그인 성공 → `access_token`을 **메모리(Zustand)**에만 저장합니다 (localStorage 사용 안 함 — XSS 공격 시 탈취 위험을 줄이기 위함).
- `refresh_token`은 브라우저가 자동으로 관리하는 **HttpOnly 쿠키**라 JS 코드에서 직접 만질 수 없습니다 (정상입니다, 원래 그렇게 설계된 것).
- 새로고침하면 `access_token`이 사라지는데, `App.tsx`가 시작할 때 자동으로 `/users/refresh`를 한 번 호출해서 다시 받아옵니다.
- API 호출 중 401이 오면 `api/client.ts`가 자동으로 갱신을 시도하고, 그래도 실패하면 로그인 페이지로 보냅니다. **이 로직은 건드릴 필요 없습니다.**

## 5. 지금 당장 안 되는 것 (백엔드 쪽 제약, 프론트에서 못 고침)

- **Google 소셜 로그인** — 백엔드에 OAuth 콜백 라우트가 없음
- **알약 이미지 검색** — pgvector 보류 상태라 항상 빈 결과
- **AI 챗봇 실시간 스트리밍** — SSE 아직 없음, 일반 JSON 응답만 옴
- **건강지표/병원예약/증상 목록 조회** — 백엔드에 GET API가 아직 없음 (등록만 가능)

이 부분들은 백엔드 도메인 폴더의 `router.py`에 있는 `# TODO(조원 구현)` 주석과 함께 백엔드 작업이 먼저 필요합니다.
