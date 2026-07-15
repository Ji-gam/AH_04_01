import { Link } from "react-router-dom";

import type { HealthContentResult } from "../../api/types";

import { Chip } from "@/components/ui/chip";
import { CONTENT_CATEGORY_LABELS, ContentCategoryImage } from "@/lib/contentCategoryDisplay";
import { cn } from "@/lib/utils";

export interface ContentCardProps {
  item: HealthContentResult;
  // "list" = 정보 탭 피드의 에디토리얼 리스트 행, "rail" = 상세화면 관련컨텐츠 가로스크롤의 고정 너비 카드.
  variant?: "list" | "rail";
  className?: string;
}

// content_date(YYYY-MM-DD)를 목록의 "3시간 전" 류 상대 표기에 맞춰 대략적인 일 단위로 보여준다
// (시각 단위 데이터가 없어 시간 단위 상대 표기는 만들 수 없다 — 오늘/어제/N일 전까지만).
function formatRelativeDate(dateStr: string): string {
  const diffDays = Math.floor(
    (Date.now() - new Date(`${dateStr}T00:00:00`).getTime()) / (1000 * 60 * 60 * 24),
  );
  if (diffDays <= 0) return "오늘";
  if (diffDays === 1) return "어제";
  return `${diffDays}일 전`;
}

export function ContentCard({ item, variant = "list", className }: ContentCardProps) {
  if (variant === "rail") {
    return (
      <Link
        to={`/info/${item.id}`}
        className={cn(
          "block w-36 shrink-0 overflow-hidden rounded-2xl bg-secondary text-foreground no-underline shadow-sm transition-transform active:scale-[0.98]",
          className,
        )}
      >
        <ContentCategoryImage category={item.category} className="h-20 w-full" />
        <div className="p-2.5">
          <div className="flex flex-wrap gap-1.5">
            <Chip tone="disease">{item.disease_code}</Chip>
            <Chip tone="category">{CONTENT_CATEGORY_LABELS[item.category]}</Chip>
          </div>
          <h2 className="mt-2 line-clamp-1 text-sm font-semibold">{item.title}</h2>
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.summary}</p>
        </div>
      </Link>
    );
  }

  // "list" — 에디토리얼 리스트 행: 카드 배경/그림자 없이 얇은 구분선 + 좌측 작은 정사각 썸네일.
  return (
    <Link
      to={`/info/${item.id}`}
      className={cn(
        "flex gap-3.5 border-b border-border py-4 text-foreground no-underline",
        className,
      )}
    >
      <ContentCategoryImage
        category={item.category}
        className="h-[76px] w-[76px] shrink-0 rounded-md"
      />
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex flex-wrap gap-1.5">
          <Chip tone="disease">{item.disease_code}</Chip>
          <Chip tone="category">{CONTENT_CATEGORY_LABELS[item.category]}</Chip>
        </div>
        <h2 className="text-[15px] font-bold leading-snug">{item.title}</h2>
        <p className="mt-1 line-clamp-1 text-[12.5px] text-muted-foreground">{item.summary}</p>
        <p className="mt-1.5 text-[11px] text-muted-foreground/75">
          {formatRelativeDate(item.content_date)}
        </p>
      </div>
    </Link>
  );
}
