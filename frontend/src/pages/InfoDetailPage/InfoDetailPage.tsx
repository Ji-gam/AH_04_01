/**
 * '정보' 탭 상세화면(T-LLM-3-1) — /info/:id.
 * admin용 ContentDetailPage(/content-generation/:id)와 달리 location.state에 의존하지 않고
 * 항상 서버에서 id로 다시 조회한다 — 새로고침/직접 URL 접근에도 동작해야 하기 때문이다.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { contentApi } from "../../api/contentApi";
import type { HealthContentResult } from "../../api/types";

import { ContentCard } from "@/components/content/ContentCard";
import { ShareSheet } from "@/components/content/ShareSheet";
import { Chip } from "@/components/ui/chip";
import { CONTENT_CATEGORY_LABELS, ContentCategoryImage } from "@/lib/contentCategoryDisplay";

export default function InfoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const contentId = Number(id);

  const [item, setItem] = useState<HealthContentResult | null>(null);
  const [related, setRelated] = useState<HealthContentResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(contentId)) {
      setIsLoading(false);
      setNotFound(true);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setNotFound(false);
    setItem(null);

    contentApi
      .getContentById(contentId)
      .then((data) => {
        if (!cancelled) setItem(data);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [contentId]);

  useEffect(() => {
    if (!Number.isFinite(contentId)) return;
    let cancelled = false;

    contentApi
      .getRelatedContents(contentId)
      .then((data) => {
        if (!cancelled) setRelated(data.items);
      })
      .catch(() => {
        if (!cancelled) setRelated([]);
      });

    return () => {
      cancelled = true;
    };
  }, [contentId]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">불러오는 중...</p>
      </div>
    );
  }

  if (notFound || !item) {
    return (
      <div className="flex h-full flex-col px-4 pt-[calc(env(safe-area-inset-top)+12px)]">
        <Link to="/info" className="mb-4 text-sm text-muted-foreground no-underline">
          ← 뒤로가기
        </Link>
        <p className="py-8 text-center text-sm text-muted-foreground">콘텐츠를 찾을 수 없어요.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto pb-8">
      <div className="relative">
        <Link
          to="/info"
          aria-label="뒤로가기"
          className="absolute left-3.5 top-[calc(env(safe-area-inset-top)+12px)] z-10 flex h-8 w-8 items-center justify-center rounded-full bg-secondary text-secondary-foreground no-underline"
        >
          ‹
        </Link>
        <ContentCategoryImage category={item.category} className="aspect-[4/3] w-full" />
      </div>

      <h1 className="mx-4 mt-4 text-xl font-bold text-balance">{item.title}</h1>

      <p className="mx-4 mt-4 whitespace-pre-wrap text-sm leading-relaxed text-foreground">
        {item.body}
      </p>

      <p className="mx-4 mt-5 text-xs text-muted-foreground">{item.disclaimer}</p>

      {item.source_refs && item.source_refs.length > 0 && (
        <div className="mx-4 mt-5">
          <h2 className="mb-2 text-xs font-semibold text-muted-foreground">참고자료</h2>
          <ul className="flex flex-col gap-1">
            {item.source_refs.map((url, index) => (
              <li key={url}>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary underline underline-offset-2"
                >
                  원문 {index + 1}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mx-4 mt-5 flex justify-start gap-2">
        <Chip tone="disease">{item.disease_code}</Chip>
        <Chip tone="category">{CONTENT_CATEGORY_LABELS[item.category]}</Chip>
      </div>

      <div className="mt-5 flex justify-center">
        <ShareSheet title={item.title} />
      </div>

      {related.length > 0 && (
        <div className="mt-6">
          <h2 className="mx-4 mb-3 text-base font-bold">관련컨텐츠</h2>
          <div className="flex gap-3 overflow-x-auto px-4 pb-2">
            {related.map((relatedItem) => (
              <ContentCard key={relatedItem.id} item={relatedItem} variant="rail" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
