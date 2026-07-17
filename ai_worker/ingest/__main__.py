"""`python -m ai_worker.ingest` 진입점. 모듈 docstring에 사용법이 있다."""

import argparse
import json

from ai_worker.ingest.pipeline import ingest_all, scan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true", help="색인하면 뭐가 들어갈지만 보여준다(색인 안 함).")
    parser.add_argument(
        "--force", action="store_true", help="내용이 같아도 다시 임베딩한다(청킹이나 모델을 바꿨을 때)."
    )
    args = parser.parse_args()

    if args.scan:
        print(json.dumps(scan(), ensure_ascii=False, indent=2))
        return

    for result in ingest_all(force=args.force):
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
