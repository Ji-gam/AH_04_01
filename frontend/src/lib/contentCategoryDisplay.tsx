import type { ContentCategory } from "../api/types";

import { cn } from "@/lib/utils";

// 컨텐츠 카테고리 한글 라벨 — InfoPage의 카테고리 탭과 ContentCard/InfoDetailPage의 칩이
// 모두 이 맵 하나로 파생된다(중복 정의 방지).
export const CONTENT_CATEGORY_LABELS: Record<ContentCategory, string> = {
  LIFESTYLE: "라이프스타일",
  FOOD: "푸드",
  MEDICAL_NEWS: "의학뉴스",
};

// DB에 실제 이미지가 없고 image_prompt(텍스트, 향후 T-LLM-4용)만 있어, 카테고리별 고정
// 플레이스홀더로 이미지 영역을 채운다(HTML 프로토타입에서 확정한 팔레트/아이콘 그대로).
const CATEGORY_STYLE: Record<ContentCategory, { gradient: string; icon: string }> = {
  LIFESTYLE: { gradient: "from-emerald-300 to-emerald-500", icon: "🏃" },
  FOOD: { gradient: "from-amber-300 to-amber-500", icon: "🍎" },
  MEDICAL_NEWS: { gradient: "from-sky-300 to-sky-500", icon: "📰" },
};

export function ContentCategoryImage({
  category,
  className,
}: {
  category: ContentCategory;
  className?: string;
}) {
  const style = CATEGORY_STYLE[category];
  return (
    <div
      className={cn(
        `flex items-center justify-center bg-gradient-to-br ${style.gradient}`,
        className,
      )}
      aria-hidden
    >
      <span className="text-3xl">{style.icon}</span>
    </div>
  );
}
