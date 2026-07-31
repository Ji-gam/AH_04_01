/**
 * T-LLM-6 카드뉴스 아이콘 맵: `icon_key`(백엔드가 준 값) → lucide 컴포넌트.
 *
 * LLM은 백엔드 `app/dtos/health_news_dto.py`의 `IconKey` 목록 안에서만 아이콘을 고른다.
 * 그래서 여기서는 해석할 게 없고 표만 있으면 된다 - 이 표가 "선택지를 객관식으로 못 박은"
 * 설계의 마지막 조각이다.
 *
 * 타입이 `Record<CardIconKey, LucideIcon>`이라, 백엔드에 아이콘이 추가됐는데 여기 빠뜨리면
 * `npm run typecheck`가 잡아준다. (아이콘 이름은 lucide 파일명 그대로라 kebab → PascalCase만 하면 된다.)
 */
import {
  Activity,
  Apple,
  Ban,
  Bed,
  BookOpen,
  Bone,
  Brain,
  CalendarCheck,
  Carrot,
  ChartLine,
  CigaretteOff,
  CircleCheck,
  ClipboardList,
  Clock,
  CloudRain,
  Coffee,
  Droplet,
  Dumbbell,
  Egg,
  Eye,
  Fish,
  FlaskConical,
  Footprints,
  Frown,
  Gauge,
  Heart,
  HeartPulse,
  Hospital,
  Info,
  Lightbulb,
  type LucideIcon,
  Microscope,
  Milk,
  Moon,
  Pill,
  Salad,
  Scale,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  Smile,
  Sparkles,
  Stethoscope,
  Syringe,
  TestTube,
  Thermometer,
  Timer,
  TrendingUp,
  TriangleAlert,
  Users,
  Utensils,
  Wheat,
  Wine,
} from "lucide-react";

import type { CardIconKey } from "../api/types";

export const CARD_NEWS_ICONS: Record<CardIconKey, LucideIcon> = {
  // 수면·시간
  moon: Moon,
  bed: Bed,
  timer: Timer,
  clock: Clock,
  "calendar-check": CalendarCheck,
  // 운동·활동
  dumbbell: Dumbbell,
  footprints: Footprints,
  activity: Activity,
  "heart-pulse": HeartPulse,
  "trending-up": TrendingUp,
  // 신체·장기
  heart: Heart,
  brain: Brain,
  bone: Bone,
  eye: Eye,
  stethoscope: Stethoscope,
  // 식이·음식
  apple: Apple,
  carrot: Carrot,
  salad: Salad,
  egg: Egg,
  fish: Fish,
  wheat: Wheat,
  milk: Milk,
  coffee: Coffee,
  droplet: Droplet,
  utensils: Utensils,
  // 금지·주의
  ban: Ban,
  "cigarette-off": CigaretteOff,
  wine: Wine,
  "triangle-alert": TriangleAlert,
  "shield-alert": ShieldAlert,
  // 약·치료
  pill: Pill,
  syringe: Syringe,
  thermometer: Thermometer,
  hospital: Hospital,
  // 검사·수치
  "flask-conical": FlaskConical,
  microscope: Microscope,
  "test-tube": TestTube,
  gauge: Gauge,
  "chart-line": ChartLine,
  // 문서·기록
  "clipboard-list": ClipboardList,
  "scroll-text": ScrollText,
  "book-open": BookOpen,
  // 안전·확인
  "shield-check": ShieldCheck,
  "circle-check": CircleCheck,
  info: Info,
  // 심리·사람
  smile: Smile,
  frown: Frown,
  "cloud-rain": CloudRain,
  users: Users,
  scale: Scale,
  // 강조
  sparkles: Sparkles,
  lightbulb: Lightbulb,
};

/**
 * 백엔드가 이 표에 없는 키를 보내는 일은 없어야 하지만(Literal로 막혀 있다), 배포 시점이
 * 어긋나 새 아이콘이 먼저 올 수는 있다. 그때 카드가 깨지는 대신 중립 아이콘을 쓴다 —
 * 백엔드의 FALLBACK_ICON_KEY와 같은 아이콘이다.
 */
export function cardNewsIcon(key: string): LucideIcon {
  return CARD_NEWS_ICONS[key as CardIconKey] ?? Info;
}

/**
 * 카드 배경 그라데이션. **LLM이 정하지 않는다** — 코드가 정하는 시각 요소라서, 어떤 응답이
 * 와도 카드가 못생겨질 수 없다. 슬라이드 순서로 순환시켜 덱 안에서 색이 반복되지 않게 한다.
 * 프로토타입(docs/dev/sample_card_news/)에서 쓴 조합을 그대로 옮겼다.
 */
export const CARD_GRADIENTS = [
  "linear-gradient(150deg, #6C63FF 0%, #3F3D9E 100%)",
  "linear-gradient(150deg, #FF6F91 0%, #C2456B 100%)",
  "linear-gradient(150deg, #2BB0A3 0%, #16706A 100%)",
  "linear-gradient(150deg, #F0932B 0%, #B45A12 100%)",
  "linear-gradient(150deg, #4A8FE7 0%, #275BA8 100%)",
] as const;

export function cardGradient(index: number): string {
  return CARD_GRADIENTS[index % CARD_GRADIENTS.length];
}
