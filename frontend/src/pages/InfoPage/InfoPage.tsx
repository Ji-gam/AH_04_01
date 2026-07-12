/**
 * '정보' 탭 — T-LLM-3. 로그인 없이도 볼 수 있는 건강 콘텐츠 피드(카테고리별 누적).
 * personalized=false(비로그인 또는 등록된 질환 없음)면 질환 등록 유도 배너를 보여준다 —
 * 단, 질환 등록 기능 자체가 아직 없어(2026-07-08 기준) 지금은 시각적 안내만 한다.
 */
import { useEffect, useState } from "react";

import { contentApi } from "../../api/contentApi";
import type { ContentCategory, HealthContentResult } from "../../api/types";
import { useAuth } from "../../hooks/useAuth";

import { Button } from "@/components/ui/button";

const CATEGORY_TABS: { label: string; value: ContentCategory | undefined }[] = [
  { label: "전체", value: undefined },
  { label: "라이프스타일", value: "LIFESTYLE" },
  { label: "푸드", value: "FOOD" },
  { label: "의학뉴스", value: "MEDICAL_NEWS" },
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
            variant={category === tab.value ? "default" : "secondary"}
            onClick={() => setCategory(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {!isLoading && !personalized && (
        <div className="mx-4 mb-2 rounded-2xl bg-secondary px-4 py-3 text-sm text-secondary-foreground">
          아직 등록된 질환이 없어요. 질환을 등록하면 나에게 맞는 콘텐츠를 보여드려요.
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

        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <article
              key={`${item.disease_code}-${item.category}-${item.content_date}`}
              className="rounded-2xl bg-secondary p-4 shadow-sm"
            >
              <p className="text-xs text-muted-foreground">
                {item.disease_code} · {item.content_date}
              </p>
              <h2 className="mt-1 text-base font-semibold">{item.title}</h2>
              <p className="mt-1 text-sm text-secondary-foreground">{item.summary}</p>
              <p className="mt-3 whitespace-pre-wrap text-sm text-secondary-foreground">
                {item.body}
              </p>
              <p className="mt-3 text-xs text-muted-foreground">{item.disclaimer}</p>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
