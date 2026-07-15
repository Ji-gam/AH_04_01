/**
 * '정보' 탭 — T-LLM-3. 로그인 없이도 볼 수 있는 건강 콘텐츠 피드(카테고리별 누적).
 * personalized=false(비로그인 또는 등록된 질환 없음)면 질환 등록 유도 배너를 보여준다 —
 * 단, 질환 등록 기능 자체가 아직 없어(2026-07-08 기준) 지금은 시각적 안내만 한다.
 */
import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { contentApi } from "../../api/contentApi";
import type { ContentCategory, HealthContentResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";

import { ContentCard } from "@/components/content/ContentCard";
import { Button } from "@/components/ui/button";
import { CONTENT_CATEGORY_LABELS } from "@/lib/contentCategoryDisplay";

// 질환 등록 유도 배너 — 상단에 한 번, 그리고 !personalized일 때 카드 UI만 계속되는 걸 막기
// 위해 목록 중간에도 이 개수마다 한 번씩 반복 노출한다(UI 리듬).
const DISEASE_BANNER_INTERVAL = 4;

// 상단 개인화 안내 — 텍스트 배너(카드 목록의 좌우 여백 안에 그대로 노출).
function DiseaseRegistrationNotice() {
  return (
    <div className="rounded-2xl bg-secondary px-4 py-3 text-sm text-secondary-foreground">
      아직 등록된 질환이 없어요. 질환을 등록하면 나에게 맞는 콘텐츠를 보여드려요.
    </div>
  );
}

// 목록 중간 리듬용 배너 — 카드UI가 아닌 큰 이미지 전면형 히어로, 화면 가로폭 전체(edge-to-edge).
function DiseaseRegistrationHeroBanner() {
  return (
    <Link
      to="/health-info"
      className="relative -mx-4 block h-44 overflow-hidden text-white no-underline"
    >
      <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-primary to-[#E8557A]">
        <span className="text-7xl opacity-40" aria-hidden>
          💡
        </span>
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/15 to-transparent" />
      <div className="absolute inset-x-5 bottom-4">
        <p className="mb-1 text-xs font-bold opacity-90">안내</p>
        <p className="text-lg font-extrabold leading-snug">
          질환을 등록하고
          <br />
          나에게 맞는 콘텐츠 받아보기
        </p>
      </div>
    </Link>
  );
}

const CATEGORY_TABS: { label: string; value: ContentCategory | undefined }[] = [
  { label: "전체", value: undefined },
  ...(Object.entries(CONTENT_CATEGORY_LABELS) as [ContentCategory, string][]).map(
    ([value, label]) => ({
      label,
      value,
    }),
  ),
];

export default function InfoPage() {
  const { user } = useAuth();
  const [category, setCategory] = useState<ContentCategory | undefined>(undefined);
  const [items, setItems] = useState<HealthContentResult[]>([]);
  const [personalized, setPersonalized] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 상단 개인화 헤드라인 — 의학뉴스 중 가장 최근 1개 헤드라인만. 새 콘텐츠가 매일 시드되므로
  // 자연히 "오늘의 헤드라인"이 된다. 기존 카테고리 탭/누적 피드와는 별개로 항상 노출.
  const [headline, setHeadline] = useState<HealthContentResult | null>(null);

  useEffect(() => {
    contentApi
      .getContents("MEDICAL_NEWS", 1)
      .then((result) => setHeadline(result.items[0] ?? null))
      .catch(() => setHeadline(null));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    contentApi
      .getContents(category)
      .then((result) => {
        if (cancelled) return;
        setItems(result.items);
        setPersonalized(result.personalized);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "알 수 없는 오류");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [category]);

  return (
    <div className="flex h-full flex-col">
      <div className="px-4 pt-[calc(env(safe-area-inset-top)+12px)] pb-2">
        <h1 className="text-lg font-semibold">정보</h1>
      </div>

      {headline && (
        <div className="mx-4 mb-3 rounded-2xl bg-secondary px-4 py-3">
          <p className="text-xs font-medium text-muted-foreground">
            {user?.name ?? "회원"}님을 위한 컨텐츠
          </p>
          <p className="mt-1 text-sm font-semibold text-secondary-foreground">{headline.title}</p>
        </div>
      )}

      <div className="flex gap-2 overflow-x-auto px-4 pb-2">
        {CATEGORY_TABS.map((tab) => (
          <Button
            key={tab.label}
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => setCategory(tab.value)}
            className={`border border-white bg-white hover:bg-white ${
              category === tab.value ? "font-semibold text-primary" : "text-muted-foreground"
            }`}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {!isLoading && !personalized && (
        <div className="mx-4 mb-2">
          <DiseaseRegistrationNotice />
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {isLoading && (
          <p className="py-8 text-center text-sm text-muted-foreground">불러오는 중...</p>
        )}

        {!isLoading && error && (
          <p className="py-8 text-center text-sm text-destructive">
            콘텐츠를 불러오지 못했어요. ({error})
          </p>
        )}

        {!isLoading && !error && items.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">아직 콘텐츠가 없어요.</p>
        )}

        <div className="flex flex-col">
          {items.map((item, index) => {
            const isIntervalBoundary = (index + 1) % DISEASE_BANNER_INTERVAL === 0;
            const showMidListBanner =
              !personalized && isIntervalBoundary && index !== items.length - 1;
            return (
              <Fragment key={item.id}>
                <ContentCard item={item} />
                {showMidListBanner && <DiseaseRegistrationHeroBanner />}
              </Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
