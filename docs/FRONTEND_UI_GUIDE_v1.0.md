# FRONTEND_UI_GUIDE.md — 디자인 시스템 & UI 컴포넌트 사용규칙

> **문서 버전**: v1.0 · **작성**: 2026-07-08 (서현)
> **위치**: `docs/CODING_RULES.md` 3-5번(스타일링) 항목의 **구체적인 실행 방법**을 정리한 짝 문서입니다.
> 3-5번에서 "유틸리티 클래스(Tailwind 등) 하나로 통일한다"고 정한 것을, 실제로 **Tailwind CSS + shadcn/ui**로 확정하고
> 어떻게 쓰는지 정리했습니다.

> ℹ️ 아직 전체 화면에 적용된 상태는 아닙니다. 다른 화면(홈/추적/더보기)은 각 담당자가 이 문서를 보고 같은
> 방식으로 맞춰가면 됩니다. 화면 하나씩 작은 PR로 옮겨주세요 (`docs/CONTRIBUTING.md` 6번 — 탭 폴더 단위 PR
> 원칙 그대로 적용).
>
> **2026-07-08 갱신**: Tailwind+shadcn 인프라(설정 파일/토큰/`button`·`input` 부품)를 T-LLM-3(정보 탭) 작업
> 중 실제로 설치했습니다 — 이 문서가 설명하던 상태가 이제 코드로도 존재합니다. **InfoPage(정보)** 가 첫 적용
> 화면입니다. ChatPage는 아직 이 문서 이전 방식(인라인 style) 그대로이며, 별도 작업으로 마이그레이션 예정입니다.

---

## 0. 왜 Tailwind + shadcn인가 (용어 설명 포함)

- **Tailwind CSS**: `flex`, `rounded-2xl`, `px-4` 같은 "이름이 곧 스타일인" 클래스를 조합해서 화면을 꾸미는 도구입니다.
  버튼이나 카드 같은 완성된 부품은 안 주고, "재료"만 줍니다. 이미 `.css` 파일을 안 만들기로 한 팀 규칙(5번)과 맞습니다.
- **shadcn/ui**: Tailwind로 이미 만들어진 버튼/입력창 같은 "부품 코드"를 우리 프로젝트 안에 **직접 복사**해서 쓰는 방식입니다.
  (`npm install`로 받는 라이브러리가 아니라, `src/components/ui/` 안에 코드 파일이 그대로 들어옵니다.)
  그래서 나중에 우리 마음대로 코드를 고칠 수 있고, 매번 새 버전이 나올 때마다 깨질 걱정이 적습니다.

**우리가 이걸 쓰는 이유**: 초보 5인이 각자 버튼 스타일을 다르게 만들면 화면마다 느낌이 달라집니다. 부품을 미리 정해두면
"버튼은 이거 갖다 쓰면 끝"이라서 디자인이 자연스럽게 통일됩니다.

---

## 1. 설치된 것 / 새로 생긴 파일

| 파일 | 역할 |
| --- | --- |
| `tailwind.config.js` | Tailwind 설정. 색상/둥근 정도(radius)/폰트를 여기서 CSS 변수와 연결 |
| `postcss.config.js` | Tailwind를 빌드 과정에 끼워 넣는 설정 (건드릴 일 거의 없음) |
| `src/index.css` | **디자인 토큰(색상 값 등)이 정의된 곳**. `main.tsx`에서 한 번만 import 됨 |
| `components.json` | shadcn CLI 설정. 새 부품을 받을 때 이 설정을 보고 어디에 넣을지 결정함 |
| `src/lib/utils.ts` | `cn()` 함수. Tailwind 클래스를 조건부로 합칠 때 항상 이걸로만 합침 |
| `src/components/ui/*.tsx` | shadcn 표준 부품 (지금은 `button.tsx`, `input.tsx`) |
| `tsconfig.json` / `vite.config.ts` | `@/`로 시작하는 경로가 `src/`를 가리키도록 alias 추가 (`@/lib/utils` = `src/lib/utils.ts`) |

---

## 2. 디자인 토큰 — 색은 여기서만 가져다 쓴다

`src/index.css`에 정의되어 있고, Apple(iOS) 느낌을 참고해서 정했습니다. **새 색을 코드에 직접 쓰지 말고(`#3498db` 같은 것 금지),
아래 이름으로만 씁니다.**

| 토큰 (Tailwind 클래스) | 의미 | 예시 |
| --- | --- | --- |
| `bg-primary` / `text-primary-foreground` | 주요 강조색 (iOS 시스템 블루 계열) | 전송 버튼, 사용자 채팅 말풍선 |
| `bg-secondary` / `text-secondary-foreground` | 옅은 회색 배경 | AI 답변 말풍선, 보조 버튼 |
| `bg-muted` / `text-muted-foreground` | 흐린 텍스트/배경 | 안내문, 타임스탬프, placeholder |
| `bg-destructive` | 경고/삭제 등 위험 동작 | 삭제 버튼 |
| `border-border` | 구분선 | 헤더/입력창 경계선 |
| `rounded-2xl`, `rounded-full` | 둥근 정도 | 말풍선(2xl), 버튼/입력창(full) — Apple 스타일은 각지지 않고 넉넉하게 둥근 편 |

색을 더 추가해야 하면(예: 성공/경고 색) `src/index.css`의 `:root` 블록에 CSS 변수를 추가하고 `tailwind.config.js`의
`colors`에 매핑하세요. **혼자 결정하지 말고 팀 채널에 공유 후 반영합니다** (여러 화면에 영향을 주는 공통 값이라서).

---

## 3. 폴더 규칙 — `components/ui/` vs `components/common/`

`docs/CODING_RULES.md` 3-2번의 `components/common/`(3개 이상 페이지에서 쓰는 재사용 컴포넌트) 규칙에
**한 단계를 추가**합니다.

```
src/components/
├── ui/       # shadcn 표준 부품 (Button, Input 등) — "레고 블록" 그 자체
└── common/   # 우리 서비스 로직이 들어간 재사용 컴포넌트 (예: DisclaimerBanner) — 레고로 조립한 "완성품"
```

- `ui/` 안의 파일은 **shadcn 원본 그대로 두는 게 원칙**입니다. 스타일을 크게 바꾸고 싶으면 파일을 직접 고치지 말고
  팀에 먼저 얘기하세요 (`docs/CODING_RULES.md` 3-6번 "공통 모듈" 규칙과 같은 이유 — 여기 바뀌면 전체 화면에 영향).
- `common/`은 기존 규칙 그대로입니다 (페이지 폴더 안에서 시작 → 3곳 이상 재사용되면 승격).

---

## 4. 새 shadcn 부품이 필요할 때

카드, 다이얼로그(팝업), 스위치 같은 부품이 더 필요하면:

```bash
npx shadcn@latest add card dialog switch
```

`components.json` 설정을 보고 알아서 `src/components/ui/`에 파일을 넣어줍니다. 네트워크가 안 되는 환경이면,
[ui.shadcn.com](https://ui.shadcn.com) 사이트에서 코드를 직접 복사해서 같은 위치에 붙여넣어도 됩니다 — 어차피 shadcn은
"복사해서 쓰는" 방식이라 둘 다 결과가 같습니다.

받은 뒤에는 2번 표에 없는 새 색을 쓰고 있지 않은지 확인하고, 있다면 기존 토큰으로 바꿔주세요.

---

## 5. 화면(Page)에서 스타일 쓰는 법

**하면 안 되는 것**

- `style={{ ... }}` 인라인 스타일 객체 — 예전 코드 방식, 새로 쓰지 않기
- 새 `.css` 파일 생성
- 클래스 문자열을 `+`나 백틱으로 직접 이어붙이기 (`className={"a " + (b ? "c" : "")}` 대신 `cn()` 사용)

**이렇게 합니다** (`ChatPage.tsx` 참고)

```tsx
import { cn } from "@/lib/utils";

<div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
```

- 여백/정렬 등 레이아웃: Tailwind 클래스 직접 사용 (`flex`, `gap-2`, `px-4` 등)
- 조건부 스타일: `cn()`으로 합치기
- 버튼/입력창: 새로 만들지 말고 `@/components/ui/button`, `@/components/ui/input` 사용

---

## 6. Apple(HIG) 느낌을 내는 포인트 정리

ChatPage에 적용한 방식이고, 다른 화면도 같은 톤을 유지해주세요.

- 모서리를 넉넉하게 둥글림: 버튼/입력창은 `rounded-full`, 카드/말풍선은 `rounded-2xl`
- 그림자는 아주 옅게: `shadow-sm` 정도만, 진한 그림자 금지
- 색은 채도를 낮게: 원색보다 `secondary`/`muted` 같은 톤 다운된 배경 위주
- 폰트는 시스템 폰트 우선: `tailwind.config.js`에 `-apple-system` 등이 이미 기본값으로 들어가 있어서 별도 설정 불필요
- 모바일 PWA 안전 영역: 상단/하단바가 기기 노치와 겹치지 않도록 `pt-[calc(env(safe-area-inset-top)+12px)]` 같은 패턴 사용
  (ChatPage 헤더/입력창 참고)

---

## 7. 체크리스트 (내 화면에 적용할 때)

1. `main.tsx`에서 `src/index.css`가 import 되어 있는지 확인 (프로젝트 전체 1곳에서만 하면 됨, 이미 되어 있음)
2. 화면 안의 `style={{ }}`를 Tailwind 클래스로 바꾸기
3. 버튼/입력창은 `ui/` 부품으로 교체
4. 색은 2번 표의 토큰 이름으로만 쓰기
5. `npm run lint` / `npm run build` 로 에러 없는지 확인 후 PR (한 페이지 폴더 단위로 작게)

---

## 8. 참고

- 이 문서는 ChatPage 적용 예시를 기준으로 작성되었습니다 (`frontend/src/pages/ChatPage/ChatPage.tsx`).
- 색/레이아웃 규칙에 대한 이견이 있으면 이 문서를 고치기 전에 팀과 먼저 상의해주세요 — 여러 화면에 걸치는 결정입니다.
- `DisclaimerBanner.tsx`는 시각 스타일만 Tailwind로 바꿨고 문구/노출 로직은 그대로입니다. 소유자(T-LLM-1 담당자) 확인 부탁드립니다.
