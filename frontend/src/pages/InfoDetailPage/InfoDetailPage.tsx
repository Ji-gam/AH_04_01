/**
 * 건강정보 상세화면 — T-LLM-6. /info/:id.
 *
 * 사용자 여정 2~4단계에 해당한다: 원문이 길게 나오고, [카드요약보기]로 카드뉴스 모달을 열고,
 * [음성으로듣기]는 아직 준비중이다.
 *
 * 본문은 평문(`body_text`)이고 단락은 빈 줄로 구분돼 있다. 백엔드가 수집 시점에 HTML을
 * 걷어내므로 여기서 dangerouslySetInnerHTML을 쓸 필요가 없다 — 외부 사이트가 우리 앱에
 * 스크립트를 심는 통로를 만들지 않기 위한 설계다.
 */
import { Volume2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { healthNewsApi } from "../../api/healthNewsApi";
import type { HealthNewsDetailResult } from "../../api/types";

import { CardNewsModal } from "@/components/content/CardNewsModal";
import { ShareSheet } from "@/components/content/ShareSheet";
import { Button } from "@/components/ui/button";

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}.${date.getMonth() + 1}.${date.getDate()}`;
}

export default function InfoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const newsId = Number(id);

  const [item, setItem] = useState<HealthNewsDetailResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [isCardOpen, setIsCardOpen] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(newsId)) {
      setIsLoading(false);
      setNotFound(true);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setNotFound(false);
    setItem(null);

    healthNewsApi
      .getById(newsId)
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
  }, [newsId]);

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
        <p className="py-8 text-center text-sm text-muted-foreground">기사를 찾을 수 없어요.</p>
      </div>
    );
  }

  const paragraphs = item.body_text.split("\n\n").filter((p) => p.trim().length > 0);

  return (
    <>
      <div className="flex h-full flex-col overflow-y-auto pb-10">
        <div className="relative">
          <Link
            to="/info"
            aria-label="뒤로가기"
            className="absolute left-3.5 top-[calc(env(safe-area-inset-top)+12px)] z-10 flex h-8 w-8 items-center justify-center rounded-full bg-secondary text-secondary-foreground no-underline"
          >
            ‹
          </Link>
          {item.image_url && (
            <img src={item.image_url} alt="" className="aspect-[4/3] w-full object-cover" />
          )}
        </div>

        {/* figcaption에 "사진=게티이미지뱅크" 같은 출처 표기가 들어있어 사진과 함께 보여준다. */}
        {item.image_caption && (
          <p className="mx-4 mt-2 text-[11px] leading-snug text-muted-foreground">
            {item.image_caption}
          </p>
        )}

        <h1 className="mx-4 mt-4 text-xl font-bold text-balance">{item.title}</h1>

        <p className="mx-4 mt-1.5 text-xs text-muted-foreground">
          {item.source_name} · {formatDate(item.published_at)}
        </p>

        <div className="mx-4 mt-4 flex gap-2">
          <Button
            type="button"
            size="sm"
            onClick={() => setIsCardOpen(true)}
            disabled={!item.card_summary}
            className="flex-1"
          >
            {item.card_summary ? "카드요약보기" : "카드요약 준비중"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled
            className="flex-1"
            title="준비중인 기능이에요"
          >
            <Volume2 size={15} className="mr-1" aria-hidden />
            음성으로듣기
          </Button>
        </div>

        <div className="mx-4 mt-5 flex flex-col gap-3.5">
          {paragraphs.map((paragraph, index) => (
            <p key={index} className="text-sm leading-relaxed text-foreground">
              {paragraph}
            </p>
          ))}
        </div>

        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mx-4 mt-5 text-xs text-primary underline underline-offset-2"
        >
          {item.source_name}에서 원문 보기
        </a>

        <p className="mx-4 mt-4 text-xs text-muted-foreground">{item.disclaimer}</p>

        <div className="mt-5 flex justify-center">
          <ShareSheet title={item.title} />
        </div>
      </div>

      {isCardOpen && item.card_summary && (
        <CardNewsModal news={item} onClose={() => setIsCardOpen(false)} />
      )}
    </>
  );
}
