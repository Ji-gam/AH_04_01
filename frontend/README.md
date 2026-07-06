# ReMedi Frontend — 인증(Auth) 파트 (Starter)

> 팀 `.agents/AGENTS.md`/`CONVENTIONS.md` 기준 프론트엔드가 아직 어디에도 없어서,
> 인증(로그인/회원가입/소셜로그인) 담당자가 최소한의 시작점(공유 구역 + 내 도메인)을 먼저 만든 버전입니다.
> **모노레포로 갈지 별도 저장소로 갈지 팀에서 아직 안 정해져서, 어느 쪽이든 옮기기만 하면 되도록 독립 실행 가능하게 구성했습니다.**

## 실행법

```bash
npm install
cp .env.example .env   # VITE_API_BASE_URL 확인 (기본: http://localhost:8000/api/v1)
npm run dev
```

⚠️ 백엔드는 반드시 `http://localhost:8000`으로 켜주세요 (`http://127.0.0.1:8000` 아님).
백엔드 쿠키의 `COOKIE_DOMAIN=localhost` 설정과 도메인이 일치해야 브라우저가 refresh_token 쿠키를 정상적으로 주고받습니다.

## 기술 스택 (AGENTS.md 지정 스택 그대로)

Vite + React + TypeScript, Vanilla CSS(Tailwind 안 씀), Zustand, react-router-dom, axios
(React Query 등 별도 데이터 페칭 라이브러리는 안 씀 — 스택에 없어서 최소 구성 유지)

## 폴더 구조

```
src/
├── features/auth/        ← 제 담당 도메인 (로그인/회원가입/홈 placeholder)
│   ├── LoginPage.tsx
│   ├── SignupPage.tsx
│   ├── HomePage.tsx        ← 로그인 성공 확인용 최소 화면, 나중에 대시보드로 교체 예정
│   ├── useAuth.ts
│   └── auth.css
│
├── api/                   ← [공유 구역] 제가 뼈대만 만들어둠, 다른 도메인 담당자가 이어서 씀
│   ├── client.ts            axios 인스턴스 (JWT 자동첨부 + 401시 자동 재발급)
│   └── endpoints/auth.ts    제 도메인 API 함수
│
├── store/authStore.ts     ← [공유 구역] 로그인 상태 (Zustand)
├── routes/                ← [공유 구역] 라우팅 (다른 화면 생기면 router.tsx에 추가)
├── types/auth.ts          ← [공유 구역] 인증 관련 타입
└── components/            ← [공유 구역] 아직 비어있음, 공통 UI 필요해지면 여기에
```

## 검증한 것

- `tsc --noEmit`, `npm run build` 통과
- **실제 OZ코딩스쿨 템플릿 백엔드(Tortoise+계층구조) 띄워서 진짜 네트워크로 검증**:
  회원가입 → 로그인(JWT 발급) → `/users/me` 조회 → 토큰 재발급(GET, 회전) → 로그아웃까지 전부 정상 동작 확인

## 알아두실 것

1. `api/`, `store/`, `routes/`, `types/`, `components/`는 **공유 구역**입니다. 지금은 최소 뼈대만 있어서,
   다른 도메인 담당자가 자기 파일을 추가하는 건 자유롭게 하시면 됩니다 (제 파일을 수정하실 땐 미리 얘기해주세요 — AGENTS.md 4번 규칙).
2. `getMe()` 함수는 엄밀히 "users" 도메인 API라 `api/endpoints/auth.ts`에 임시로 같이 뒀습니다. users 담당자 생기면 옮기는 게 맞습니다.
3. 소셜로그인 버튼은 `<a href>` 링크입니다 (axios 호출 아님) — 백엔드가 리다이렉트로 처리하는 구조라 그렇습니다.
4. 백엔드 로그인/회원가입은 **JSON body**, 토큰 재발급은 **GET**입니다 (예전 SQLAlchemy 버전과 다른 부분이니 주의).
