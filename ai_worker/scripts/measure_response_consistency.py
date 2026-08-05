"""
동일 입력 반복 시 응답 일관성 측정(분석 도구, 프로덕션 코드 아님 — 어디서도 import되지 않는다).

같은 질문을 N회 반복해 파이프라인을 3개 층으로 나눠 재현성을 측정한다. 층을 나누는 이유는
이 파이프라인의 결정성이 층마다 다르게 설계돼 있기 때문이다 — 규칙 기반 해석과 벡터 검색은
완전히 결정적이어야 하고, LLM 생성은 표현 변주를 의도적으로 허용한다
(`chat_agent._build_llm()`이 temperature를 고정하지 않는 이유 참고). 따라서 "전체가 똑같은가"가
아니라 "결정적이어야 할 층이 실제로 결정적인가 + 변주 허용 층에서도 사실이 흔들리지 않는가"를
측정해야 의미가 있다.

  층 1  규칙 기반 질의 해석 — disease_query_resolver.resolve_diseases (LLM/네트워크 없음)
  층 2  벡터 검색 — retrieve_service.search_documents + paper_retrieve_service.search_papers
        (로컬 HF 임베딩 + Chroma, 문서 집합과 유사도 점수까지 비교)
  층 3  LLM 생성 — chat_agent.stream_chat_answer (출처 목록 / 답변 속 수치 / 표현 유사도)

층 3의 "사실 안정성"은 답변에서 정규식으로 추출한 수치 집합으로 판정한다. 질문별 정답
키워드를 손으로 적는 방식은 채점자가 임의로 정하는 셈이라, 반복 간 수치가 흔들리는지를
보는 편이 더 객관적이다("최대 28일"이 매번 나오면 28이 매번 추출된다).

실행:
    uv run python -m ai_worker.scripts.measure_response_consistency --layers 12
    uv run python -m ai_worker.scripts.measure_response_consistency --layers all --repeat 5

층 1·2만 돌리면 네트워크/API 키가 전혀 필요 없다(로컬 Chroma + 캐시된 임베딩 모델).
층 3은 OPENAI_API_KEY가 필요하고 질문수 x 반복수 만큼 LLM을 호출한다.
"""

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Any

from ai_worker.core.config import settings
from ai_worker.schemas.retrieval_schema import DocumentChunk
from ai_worker.services.disease_query_resolver import resolve_diseases
from ai_worker.services.paper_retrieve_service import ensure_paper_db, search_papers
from ai_worker.services.retrieve_service import ensure_db, search_documents

# 대표 질문 5개. 검색 경로가 갈리는 유형을 골고루 덮는다 — 브랜드명(성분 브릿지 경유),
# 성분명 직접, 질환 정보(논문 컬렉션), 다른 질환(질환 필터가 실제로 구분하는지), 그리고
# 어떤 컬렉션도 타지 않아야 하는 대조군.
QUESTIONS: list[tuple[str, str]] = [
    ("brand", "인데놀 복용 중인데 주의할 점이 있나요?"),
    ("ingredient", "졸피뎀 장기 복용하면 위험한가요?"),
    ("disease_diabetes", "당뇨에 좋은 운동이 있을까요?"),
    ("disease_liver", "지방간은 어떻게 관리해야 하나요?"),
    ("control_smalltalk", "오늘 날씨 좋네요"),
]

# 답변 속 "사실"로 볼 수 있는 값만 잡는다 — 단위가 붙은 수량만 인정한다.
# 맨 처음엔 `\d+`로 모든 숫자를 잡았는데, 마크다운 번호 목록("1. ", "2. ")이 전부 사실로
# 집계돼 안정성이 부풀려졌다(실측: 번호 목록을 쓰는 답변은 공통수치가 1,2,3,4로 나옴).
# 단위를 요구하면 "최대 28일", "10%" 같은 실제 수량만 남는다.
QUANTITY_PATTERN = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:일|주일|주|개월|달|년|시간|분|초|회|번|알|정|캡슐|포|"
    r"mg|밀리그램|g|그램|kg|ml|리터|%|퍼센트|세|kcal)"
)


def extract_quantities(text: str) -> frozenset[str]:
    """단위가 붙은 수량만 뽑아 공백을 지운 형태로 정규화한다("28 일" == "28일")."""
    return frozenset(re.sub(r"\s+", "", m) for m in QUANTITY_PATTERN.findall(text))


def chunk_fingerprint(chunk: DocumentChunk) -> tuple[str, str]:
    """청크의 동일성 지표. 내용 해시와 유사도 점수를 함께 본다 — 같은 문서가 나왔더라도
    점수가 흔들리면 임베딩/색인 단계에 비결정성이 있다는 뜻이므로 구분해야 한다."""
    digest = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()[:12]
    score = "none" if chunk.score is None else f"{chunk.score:.6f}"
    return (digest, score)


def all_identical(values: list[Any]) -> bool:
    return all(v == values[0] for v in values[1:])


def mean_pairwise_similarity(texts: list[str]) -> tuple[float, float]:
    """반복 답변들 사이의 문자 수준 유사도(평균, 최소). 변주의 폭을 수치로 보여주는 값이며
    높아야 좋은 지표가 아니다 — 층 3은 변주를 허용하는 층이다."""
    pairs = list(combinations(texts, 2))
    if not pairs:
        return (1.0, 1.0)
    ratios = [SequenceMatcher(None, a, b).ratio() for a, b in pairs]
    return (sum(ratios) / len(ratios), min(ratios))


def measure_layers_1_and_2(repeat: int) -> list[dict]:
    dur_db = ensure_db()
    paper_db = ensure_paper_db()

    results = []
    for label, question in QUESTIONS:
        diseases_runs, dur_runs, paper_runs = [], [], []
        for _ in range(repeat):
            diseases_runs.append(tuple(resolve_diseases(question)))
            dur_runs.append(
                tuple(chunk_fingerprint(c) for c in search_documents(dur_db, question, settings.RAG_RETRIEVAL_LIMIT))
            )
            paper_runs.append(
                tuple(chunk_fingerprint(c) for c in search_papers(paper_db, question, settings.PAPER_RETRIEVAL_LIMIT))
            )
        results.append(
            {
                "label": label,
                "question": question,
                "diseases": list(diseases_runs[0]),
                "diseases_identical": all_identical(diseases_runs),
                "dur_hit_count": len(dur_runs[0]),
                "dur_identical": all_identical(dur_runs),
                "paper_hit_count": len(paper_runs[0]),
                "paper_identical": all_identical(paper_runs),
            }
        )
    return results


async def collect_one_answer(question: str) -> tuple[str, tuple[str, ...]]:
    """stream_chat_answer를 끝까지 소비해 (답변 전문, 출처 이름 목록)을 만든다."""
    from ai_worker.tasks.chat_agent import stream_chat_answer

    answer_parts: list[str] = []
    sources: tuple[str, ...] = ()
    async for chunk in stream_chat_answer(question, context={}, history=[], injected_context=[]):
        if chunk["type"] == "token":
            answer_parts.append(chunk["content"])
        elif chunk["type"] == "sources":
            sources = tuple(sorted(s.get("name", "") for s in chunk["sources"]))
    return ("".join(answer_parts), sources)


async def measure_layer_3(repeat: int) -> list[dict]:
    results = []
    for label, question in QUESTIONS:
        answers, source_runs, quantity_runs = [], [], []
        for _ in range(repeat):
            answer, sources = await collect_one_answer(question)
            answers.append(answer)
            source_runs.append(sources)
            quantity_runs.append(extract_quantities(answer))

        mean_sim, min_sim = mean_pairwise_similarity(answers)
        # 반복 전체에 등장한 수량 중, 모든 반복에 빠짐없이 등장한 비율. 어떤 회차에도
        # 수량이 없으면 비율을 계산할 수 없다 — 1.0(완전 안정)으로 두면 "수치를 아예 말하지
        # 않는 답변"이 만점을 받아버리므로 None(해당 없음)으로 구분한다.
        seen: Counter[str] = Counter()
        for quantities in quantity_runs:
            seen.update(quantities)
        stable = [q for q, c in seen.items() if c == repeat]
        stability = len(stable) / len(seen) if seen else None

        results.append(
            {
                "label": label,
                "question": question,
                "sources_identical": all_identical(source_runs),
                "source_count": len(source_runs[0]),
                "answer_len_min": min(len(a) for a in answers),
                "answer_len_max": max(len(a) for a in answers),
                "text_similarity_mean": round(mean_sim, 3),
                "text_similarity_min": round(min_sim, 3),
                "quantity_stability": None if stability is None else round(stability, 3),
                "quantities_seen": sorted(seen, key=lambda s: (len(s), s)),
                "quantities_all_runs": sorted(stable, key=lambda s: (len(s), s)),
            }
        )
    return results


def print_report(repeat: int, layer12: list[dict] | None, layer3: list[dict] | None) -> None:
    print(f"\n{'=' * 78}\n동일 입력 반복 일관성 측정 — 질문 {len(QUESTIONS)}개 x {repeat}회\n{'=' * 78}")

    if layer12:
        print("\n[층 1] 규칙 기반 질의 해석 — resolve_diseases")
        for r in layer12:
            mark = "일치" if r["diseases_identical"] else "불일치"
            print(f"  {r['label']:20s} {mark}  판별 질환={r['diseases'] or '없음'}")

        print("\n[층 2] 벡터 검색 — 문서 집합 + 유사도 점수까지 비교")
        print(f"  {'질문':20s} {'DUR':>16s} {'논문':>16s}")
        for r in layer12:
            dur = f"{'일치' if r['dur_identical'] else '불일치'}({r['dur_hit_count']}건)"
            paper = f"{'일치' if r['paper_identical'] else '불일치'}({r['paper_hit_count']}건)"
            print(f"  {r['label']:20s} {dur:>16s} {paper:>16s}")
        n = len(layer12)
        d_ok = sum(r["diseases_identical"] for r in layer12)
        s_ok = sum(r["dur_identical"] and r["paper_identical"] for r in layer12)
        print(f"\n  층 1 일치: {d_ok}/{n}    층 2 일치: {s_ok}/{n}")

    if layer3:
        print("\n[층 3] LLM 생성 — 표현은 변주 허용, 출처와 수치는 안정해야 함")
        print(f"  {'질문':20s} {'출처':>8s} {'수량안정':>9s} {'표현유사도':>12s} {'답변길이':>13s}")
        for r in layer3:
            src = "일치" if r["sources_identical"] else "불일치"
            sim = f"{r['text_similarity_mean']:.2f}/{r['text_similarity_min']:.2f}"
            length = f"{r['answer_len_min']}~{r['answer_len_max']}"
            stab = "해당없음" if r["quantity_stability"] is None else f"{r['quantity_stability']:.0%}"
            print(f"  {r['label']:20s} {src:>8s} {stab:>9s} {sim:>12s} {length:>13s}")
        n = len(layer3)
        print(f"\n  출처 일치: {sum(r['sources_identical'] for r in layer3)}/{n}")
        print("  * 표현유사도는 평균/최소이며, 낮은 값이 결함이 아니다(변주 허용 층)")
        print("  * 수량안정 = 단위 붙은 수량(28일, 10% 등) 중 모든 회차에 등장한 비율")
        print("    '해당없음'은 어떤 회차에도 수량 언급이 없었다는 뜻(계산 불가)")
        for r in layer3:
            if r["quantities_seen"]:
                print(f"    - {r['label']}: 등장 {r['quantities_seen']} / 공통 {r['quantities_all_runs'] or '없음'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="동일 입력 반복 일관성 측정")
    parser.add_argument("--repeat", type=int, default=5, help="질문당 반복 횟수 (기본 5)")
    parser.add_argument("--layers", choices=["12", "3", "all"], default="12", help="측정할 층 (기본 12)")
    parser.add_argument("--out", type=Path, default=None, help="결과 JSON 저장 경로")
    args = parser.parse_args()

    layer12 = measure_layers_1_and_2(args.repeat) if args.layers in ("12", "all") else None
    layer3 = asyncio.run(measure_layer_3(args.repeat)) if args.layers in ("3", "all") else None

    print_report(args.repeat, layer12, layer3)

    if args.out:
        payload = {"repeat": args.repeat, "layer_1_2": layer12, "layer_3": layer3}
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n결과 저장: {args.out}")


if __name__ == "__main__":
    main()
