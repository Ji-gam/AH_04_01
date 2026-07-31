/**
 * 건강정보 화면 — T-LLM-6. 수집된 건강 뉴스 피드(발행일 최신순).
 *
 * 기존 T-LLM-3(LLM이 매일 지어낸 팁카드)을 대체한 화면이다. 카테고리 탭과 질환 등록 유도
 * 배너는 걷어냈다 — 탭은 T-LLM-3의 LIFESTYLE/FOOD/MEDICAL_NEWS 축에 딸린 것이었고, 개인화는
 * 2단계라서 지금 기준으로 나눌 축이 없다.
 */
import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { healthNewsApi } from "../../api/healthNewsApi";
import type { HealthNewsFeedItem } from "../../api/types";

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getMonth() + 1}월 ${date.getDate()}일`;
}

function NewsRow({ item }: { item: HealthNewsFeedItem }) {
  return (
    <Link
      to={`/info/${item.id}`}
      className="flex gap-3 border-b border-border py-3.5 no-underline last:border-b-0"
    >
      {item.image_url ? (
        <img
          src={item.image_url}
          alt=""
          loading="lazy"
          className="h-[76px] w-[100px] shrink-0 rounded-xl object-cover"
        />
      ) : (
        <div className="flex h-[76px] w-[100px] shrink-0 items-center justify-center rounded-xl bg-secondary">
          <Sparkles size={20} className="text-primary opacity-60" aria-hidden />
        </div>
      )}
      <div className="flex min-w-0 flex-col justify-between">
        <h2 className="line-clamp-2 text-sm font-semibold leading-snug text-foreground">
          {item.title}
        </h2>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span>{item.source_name}</span>
          <span aria-hidden>·</span>
          <span>{formatDate(item.published_at)}</span>
          {item.has_card_summary && (
            <span className="ml-0.5 rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-semibold text-primary">
              카드요약
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

export default function InfoPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HealthNewsFeedItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    healthNewsApi
      .getFeed()
      .then((result) => {
        if (!cancelled) setItems(result.items);
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
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="px-4 pt-[calc(env(safe-area-inset-top)+12px)] pb-2">
        <button
          type="button"
          onClick={() => navigate("/")}
          className="mb-2 border-none bg-transparent p-0 text-sm text-muted-foreground"
        >
          ← 뒤로가기
        </button>
        <h1 className="text-lg font-semibold">건강정보</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">
          검증된 의료 매체의 건강 뉴스를 모아서 보여드려요.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {isLoading && (
          <p className="py-8 text-center text-sm text-muted-foreground">불러오는 중...</p>
        )}

        {!isLoading && error && (
          <p className="py-8 text-center text-sm text-destructive">
            뉴스를 불러오지 못했어요. ({error})
          </p>
        )}

        {!isLoading && !error && items.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            아직 수집된 뉴스가 없어요.
          </p>
        )}

        {items.map((item) => (
          <NewsRow key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}
