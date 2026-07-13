# FRONTEND_UI_GUIDE.md — 디자인 시스템 (Tailwind+shadcn)

v1.1 · 이력: `git log docs/FRONTEND_UI_GUIDE.md`. `CODING_RULES.md` §3-5의 실행상세. 상태: Tailwind+shadcn 인프라 설치완료, `InfoPage`가 첫 적용화면, `ChatPage`는 구방식(inline style) 유지중이며 별도PR로 마이그레이션 예정 — 다른 화면은 담당자가 이 문서대로 화면단위 소형PR로 이관.

1. 설치된 파일
`tailwind.config.js`=Tailwind설정(색상/radius/폰트를 CSS변수와 연결). `postcss.config.js`=빌드연동설정. `src/index.css`=디자인토큰 정의, `main.tsx`에서 1회 import. `components.json`=shadcn CLI설정. `src/lib/utils.ts`=`cn()`(Tailwind클래스 조건부병합, 항상 이걸로만). `src/components/ui/*.tsx`=shadcn표준부품(현재`button.tsx`,`input.tsx`). `tsconfig.json`/`vite.config.ts`=`@/`→`src/` alias.

2. 디자인 토큰 (`src/index.css` 정의 — 신규색 하드코딩 금지, 아래 이름으로만)
`bg-primary`/`text-primary-foreground`=주요강조색(iOS시스템블루계열) — 전송버튼,사용자채팅말풍선.
`bg-secondary`/`text-secondary-foreground`=옅은회색배경 — AI답변말풍선,보조버튼.
`bg-muted`/`text-muted-foreground`=흐린텍스트/배경 — 안내문,타임스탬프,placeholder.
`bg-destructive`=경고/삭제 등 위험동작 — 삭제버튼.
`border-border`=구분선 — 헤더/입력창 경계.
`rounded-2xl`,`rounded-full`=둥근정도 — 말풍선(2xl),버튼/입력창(full).
신규색 필요시(성공/경고 등) `src/index.css`의`:root`에 CSS변수 추가+`tailwind.config.js`의`colors`매핑 — 여러화면 영향이므로 팀공유 후 반영.

3. 폴더 규칙 — `components/ui/` vs `components/common/` (`CODING_RULES.md` §3-2에 한 단계 추가)
```
src/components/
├── ui/       # shadcn표준부품(Button,Input 등) — 원본 그대로 유지 원칙, 스타일 크게 변경시 팀공유 먼저(`CODING_RULES.md` §3-6과 동일 이유)
└── common/   # 서비스로직 포함 재사용컴포넌트(DisclaimerBanner 등) — §3-2 규칙 그대로(3곳+ 재사용시 승격)
```

4. 새 shadcn 부품 추가
```bash
npx shadcn@latest add card dialog switch
```
`components.json` 기준 `src/components/ui/`에 자동배치. 네트워크불가시 ui.shadcn.com에서 코드 직접복사해 같은 위치에 붙여넣기(동일결과). 추가후 §2 토큰에 없는 색 사용여부 확인, 있으면 기존토큰으로 교체.

5. 화면(Page) 스타일 작성 규칙
금지: `style={{...}}` 인라인객체, 신규`.css`파일, 클래스문자열 `+`/백틱 직접연결(`cn()` 사용).
```tsx
import { cn } from "@/lib/utils";
<div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
```
레이아웃=Tailwind클래스 직접(`flex`,`gap-2`,`px-4`). 조건부스타일=`cn()`. 버튼/입력창=신규제작 금지,`@/components/ui/button`,`@/components/ui/input` 사용.

6. Apple(HIG) 톤 (ChatPage 적용예시, 다른 화면도 동일톤 유지)
모서리=넉넉히 둥글게(버튼/입력창`rounded-full`, 카드/말풍선`rounded-2xl`). 그림자=`shadow-sm` 정도만(진한그림자 금지). 색=채도낮게(원색보다`secondary`/`muted` 톤다운 위주). 폰트=시스템폰트 우선(`-apple-system` 등 이미 기본값, 별도설정 불필요). 모바일PWA 안전영역=노치겹침 방지(`pt-[calc(env(safe-area-inset-top)+12px)]` 패턴, ChatPage 헤더/입력창 참고).

7. 화면 적용 체크리스트
`main.tsx`의 `src/index.css` import 확인(이미 완료, 프로젝트전체 1곳) → 화면 안 `style={{}}`를 Tailwind클래스로 전환 → 버튼/입력창을 `ui/` 부품으로 교체 → 색은 §2 토큰이름으로만 → `npm run lint`/`npm run build` 에러없음 확인 후 PR(페이지폴더 단위 소형PR).

8. 참고
적용예시 기준: `frontend/src/pages/ChatPage/ChatPage.tsx`. 색/레이아웃 규칙 이견시 문서수정 전 팀상의(여러화면 영향). `DisclaimerBanner.tsx`는 시각스타일만 Tailwind전환, 문구/노출로직 불변 — 소유자(T-LLM-1담당) 확인필요.
