import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// FRONTEND_UI_GUIDE_v1.0.md 5번 — 조건부 Tailwind 클래스는 항상 이 함수로만 합친다.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
