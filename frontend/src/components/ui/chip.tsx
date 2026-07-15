import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const chipVariants = cva(
  "inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium",
  {
    variants: {
      tone: {
        // 병환(질환) 카테고리 칩 — 색상만으로 구분하면 웹접근성(색맹 등) 문제가 있어
        // 배경색 + 테두리색을 함께 다르게 준다.
        disease: "border-primary bg-primary/10 text-primary",
        // 컨텐츠 카테고리 칩 (라이프스타일/푸드/의학뉴스).
        category: "border-muted-foreground/50 bg-secondary text-secondary-foreground",
      },
    },
    defaultVariants: {
      tone: "category",
    },
  },
);

export interface ChipProps
  extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof chipVariants> {}

const Chip = React.forwardRef<HTMLSpanElement, ChipProps>(({ className, tone, ...props }, ref) => (
  <span ref={ref} className={cn(chipVariants({ tone, className }))} {...props} />
));
Chip.displayName = "Chip";

export { Chip, chipVariants };
