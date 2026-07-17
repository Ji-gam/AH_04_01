"""RAG 씨딩 검증: 색인이 제대로 됐는지 실제 질문을 던져 확인한다.

`uv run python -m ai_worker.ingest` 다음에 한 번 돌린다. 색인은 "몇 건 넣었다"고 보고하지만
그게 검색이 된다는 뜻은 아니다 — 메타데이터 키가 하나 틀리면 문서는 들어가 있는데 영원히
안 뽑힌다(실제로 그런 상태로 오래 굴러갔다). 그래서 건수가 아니라 **질문으로** 확인한다.

기대 결과가 코드에 박혀 있으므로, 내 로컬이 팀과 같은지 눈으로 맞춰볼 수 있다.

실행:
    uv run python -m ai_worker.scripts.verify_rag
"""

import sys
from dataclasses import dataclass

from ai_worker.services import paper_retrieve_service as papers
from ai_worker.services import retrieve_service as dur


@dataclass(frozen=True)
class Case:
    query: str
    expect_hits: bool
    note: str


# 약을 지목한 질문은 결과가 나와야 하고, 일반 건강 질문은 0건이어야 한다.
# 0건이 정답인 케이스가 절반인 이유: 이 컬렉션은 "이 약이 안전한가"를 위한 자료이지 일반
# 건강 지식 베이스가 아니다. 필터 없이 전체를 유사도 검색하면 "혈당 관리 운동"이
# 항고혈압제와 매칭된다(실측 2026-07-16).
_DRUG_CASES = (
    Case("와파린 임신 중에 먹어도 되나요", True, "성분명 -> DUR 규칙"),
    Case("타이레놀은 부작용이 뭐야?", True, "약 이름 + 조사 -> e약은요"),
    Case("게보린 효능 알려줘", True, "약 이름 -> e약은요"),
    Case("겔포스 복용법", True, "브랜드가 제형어로 시작 -> e약은요"),
    Case("당뇨병 진단받았는데 어떡하죠", False, "약이 없으면 검색 생략"),
    Case("혈당 관리 운동 알려줘", False, "약이 없으면 검색 생략"),
    Case("안녕하세요", False, "약이 없으면 검색 생략"),
)

_PAPER_CASES = (
    Case("당뇨에 좋은 운동 알려줘", True, "질환 사전 -> 당뇨 논문"),
    Case("고혈압에 좋은 음식은?", True, "질환 사전 -> 심장/뇌혈관 논문"),
    Case("안녕하세요", False, "질환이 없으면 검색 생략"),
)


def _run(label: str, cases: tuple[Case, ...], search) -> int:
    print(f"\n{label}")
    print("-" * 72)
    failed = 0
    for case in cases:
        hits = len(search(case.query))
        ok = bool(hits) == case.expect_hits
        failed += not ok
        want = "1건 이상" if case.expect_hits else "0건"
        print(f"  {'OK ' if ok else '실패'} {case.query:26} -> {hits:2}건 (기대: {want:7}) {case.note}")
    return failed


def main() -> int:
    print("RAG 씨딩 검증 — 색인된 벡터에 실제 질문을 던진다(모킹 없음)")

    db = dur.ensure_db()
    ingredients = len(dur.db_holder["ingr_names"])
    drug_keys = len(dur.db_holder["drug_names"].entries)
    print(f"\n캐시된 성분명 {ingredients:,}종 / 약 이름 검색키 {drug_keys:,}종")
    if not ingredients or not drug_keys:
        print("  !! 이름 캐시가 비었다. 색인이 안 됐거나 메타데이터 키가 틀렸다.")
        print("     `uv run python -m ai_worker.ingest`를 먼저 돌렸는지 확인할 것.")
        return 1

    failed = _run("DUR + e약은요 (structured 컬렉션)", _DRUG_CASES, lambda q: dur.search_documents(db, q, limit=3))
    pdb = papers.ensure_paper_db()
    failed += _run("논문 (unstructured 컬렉션)", _PAPER_CASES, lambda q: papers.search_papers(pdb, q, limit=3))

    print()
    if failed:
        print(f"{failed}건 실패 — 팀과 다른 상태다. 색인을 다시 돌리거나(`--force`) 원인을 찾을 것.")
        return 1
    print("전부 통과. 팀과 같은 검색 결과를 재현하고 있다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
