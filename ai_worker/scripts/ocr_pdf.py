"""스캔본 PDF -> 읽을 수 있는 마크다운. **색인 밖의 전처리 도구다.**

사서는 요리를 안 한다: 드롭 폴더(`source/`)에 넣는 건 이미 다 된 문서여야 한다. 스캔본
PDF는 글자 레이어가 없어 그대로 넣으면 0건이 나오므로, 이 스크립트로 **미리 한 번**
`.md`로 만들어 넣는다. 그러면 그건 PDF의 부속 캐시가 아니라 그냥 책 한 권이고, 로더는
평범한 마크다운으로 읽는다.

한 번만 돌리고 결과 `.md`를 git에 커밋한다 — 그 뒤로는 몇 번을 재색인하든 LLM 비용이 0이다.
원본 스캔 PDF는 "다 된 문서"가 아니므로 `source/_not_rag/`에 둔다.

왜 두 단계인가(전부 실측, 2026-07-17):

  OCR 엔진 선택 — Docling이 아니라 PyMuPDF다. 텍스트레이어가 있는 PDF는 Docling이 잘
  처리하지만(문단 구조까지 살려 335청크), 스캔본에 Docling의 OCR을 태우면 글자 자체가
  깨진다("약 과 음식 ㅋㅋ 2 ㅋ 상 호 작 용 을"). PyMuPDF의 Tesseract 호출은 글자는
  정확히 읽고 띄어쓰기만 잃는다("약과음식상호작용을피하는복약안내서"). LLM이 고칠 수
  있는 건 후자(띄어쓰기)이지 전자(오독)가 아니므로 PyMuPDF를 쓴다.

  LLM 후처리 — 띄어쓰기가 뭉개진 한국어는 임베딩이 제대로 안 된다(토큰화가 띄어쓰기에
  의존). 그대로 넣으면 검색도 안 되고 잘못된 텍스트가 근거로 인용된다. LLM에 띄어쓰기
  복원 + 마크다운 재구조화를 시키면 읽을 수 있는 문서가 된다.

실행:
    uv run python -m ai_worker.scripts.ocr_pdf <PDF경로> [-o 출력.md]

기본 출력은 `source/<PDF이름>.md`다. 만들고 나면 원본 PDF를 `source/_not_rag/`로 내린다.
"""

import argparse
import asyncio
import logging
import unicodedata
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from ai_worker.core.config import settings

logger = logging.getLogger("ai_worker.scripts.ocr_pdf")

SOURCE_DIR = Path(__file__).parent.parent / "source"

# 스캔 해상도. 낮으면 OCR 정확도가 떨어지고, 높이면 느려진다.
_OCR_DPI = 300
_OCR_LANGUAGE = "kor"
# LLM 동시 호출 수. 페이지 수십 장을 순차로 돌리면 오래 걸리고, 너무 올리면 레이트리밋에 걸린다.
_CONCURRENCY = 8

# 복원과 창작의 경계를 프롬프트가 직접 그어야 한다. 둘을 뭉뚱그려 "추측하지 말라"고만 하면
# LLM이 겁을 먹고 "복 약안내ㅅ" 같은 명백한 오독까지 그대로 남겨, 정리를 시킨 의의가 없어진다.
# 반대로 그냥 "고쳐라"라고 하면 표지 장식처럼 신호 자체가 없는 곳을 지어낸다 — 이건 식약처
# 복약안내서이고 답변의 근거로 인용되므로, 지어낸 문장은 식약처가 하지 않은 의학적 지시가 된다.
_REWRITE_PROMPT = (
    "다음은 한국어 의약품 안내서를 OCR한 결과다. 띄어쓰기가 뭉개지고, 줄바꿈이 단어 중간을 끊었으며, "
    "글자가 잘못 읽힌 곳도 있다. 읽을 수 있는 한국어 마크다운으로 정리하라.\n\n"
    "고칠 것 — 정보는 원문에 있고 OCR이 뭉갠 것뿐이므로 복원한다:\n"
    "- 띄어쓰기와 줄바꿈을 바로잡는다('약과음식상호작용' -> '약과 음식 상호작용').\n"
    "- 문맥상 어떤 낱말인지 명백한 오독은 고친다('복 약안내ㅅ' -> '복약안내서').\n"
    "- 제목은 마크다운 헤딩으로, 목록은 목록으로 재구조화한다.\n\n"
    "하지 말 것 — 원문에 없는 정보를 만드는 일이다:\n"
    "- 원문에 없는 문장·수치·약품명·용법·주의사항을 지어내거나 덧붙이지 마라. 이 문서는 식약처 "
    "복약안내서이고 사용자 답변의 근거로 인용된다. 지어낸 내용은 식약처가 하지 않은 의학적 지시가 된다.\n"
    "- 문맥으로도 무슨 낱말인지 정할 수 없으면 추측하지 말고 그 자리에 [판독불가]를 남겨라.\n\n"
    "결과 마크다운만 출력하라."
)


def ocr_page_texts(path: Path) -> list[str]:
    """스캔본 PDF를 페이지별로 OCR한다(띄어쓰기는 뭉개진 상태). PyMuPDF가 내부적으로
    Tesseract를 호출하므로 `tesseract`와 `kor.traineddata`가 설치돼 있어야 한다."""
    import pymupdf

    doc = pymupdf.open(path)
    try:
        texts: list[str] = []
        for i in range(doc.page_count):
            page = doc[i]
            textpage = page.get_textpage_ocr(language=_OCR_LANGUAGE, dpi=_OCR_DPI, full=True)
            texts.append(page.get_text(textpage=textpage).strip())
            if (i + 1) % 10 == 0:
                logger.info(f"{path.name}: OCR {i + 1}/{doc.page_count} 페이지")
        return texts
    finally:
        doc.close()


async def _rewrite_one(llm: ChatOpenAI, text: str) -> str:
    if not text.strip():
        return ""
    try:
        response = await llm.ainvoke(
            [{"role": "system", "content": _REWRITE_PROMPT}, {"role": "user", "content": text}]
        )
    except Exception as e:
        # 한 페이지 실패가 전체를 죽이면 안 된다. 그 페이지는 OCR 원문 그대로 남기고
        # 다음 실행 때 다시 시도된다(빈 문자열로 두면 내용이 조용히 사라진다).
        logger.error(f"LLM 후처리 실패, OCR 원문 유지: {e}")
        return text
    return str(response.content).strip()


async def prepare(pdf_path: Path, out_path: Path | None = None) -> Path:
    """스캔본 PDF 하나를 OCR + LLM 후처리해 마크다운으로 저장한다.

    이미 있으면 아무것도 하지 않는다 — LLM 재과금을 막는 것이 이 파일의 존재 이유다.

    페이지 번호를 헤딩으로 남기지 않는다. 처음엔 `## N쪽`을 넣었는데, LLM이 정리하며 만든
    헤딩이 `#`/`##`/`###`를 이미 다 쓰고 있어 페이지 마커만 가려낼 레벨이 없었다. 게다가
    `metadata["page"]`를 읽는 코드가 어디에도 없었다 — LLM이 만든 헤딩이 곧 문서의 진짜
    구조이고, MarkdownLoader는 그 금을 따라 자른다."""
    out_path = out_path or SOURCE_DIR / f"{unicodedata.normalize('NFC', pdf_path.stem)}.md"
    if out_path.exists():
        logger.info(f"{out_path.name} 이미 있음, 건너뜁니다(LLM 재과금 없음).")
        return out_path

    if settings.OPENAI_API_KEY is None:
        raise ValueError("OPENAI_API_KEY가 없어 OCR 후처리를 할 수 없습니다.")

    logger.info(f"{pdf_path.name}: OCR 시작")
    pages = ocr_page_texts(pdf_path)

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        temperature=settings.OPENAI_TEMPERATURE,
    )
    logger.info(f"{pdf_path.name}: LLM 후처리 {len(pages)}페이지 (동시 {_CONCURRENCY})")
    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def _bounded(text: str) -> str:
        async with semaphore:
            return await _rewrite_one(llm, text)

    rewritten = await asyncio.gather(*(_bounded(t) for t in pages))
    body = "\n\n".join(t for t in rewritten if t.strip())
    header = (
        f"# {pdf_path.stem}\n\n"
        f"> 원본은 스캔본이라 pymupdf OCR + LLM 정리를 거친 텍스트다. 원본 PDF는 `_not_rag/`에 있다.\n\n"
    )
    out_path.write_text(header + body + "\n", encoding="utf-8")
    logger.info(
        f"{pdf_path.name}: {len(pages)}페이지 -> {out_path.name} 저장. git에 커밋하고 PDF는 _not_rag/로 내릴 것."
    )
    return out_path


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path, help="OCR할 스캔본 PDF 경로")
    parser.add_argument("-o", "--out", type=Path, default=None, help="출력 .md 경로(기본: source/<PDF이름>.md)")
    args = parser.parse_args()
    print(asyncio.run(prepare(args.pdf, args.out)))


if __name__ == "__main__":
    main()
