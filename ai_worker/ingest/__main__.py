"""`python -m ai_worker.ingest` 진입점. 모듈 docstring에 사용법이 있다."""

import argparse
import json

from ai_worker.ingest.manifest import load_manifest, scan_source_dir
from ai_worker.ingest.pipeline import ingest_all


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true", help="source/를 매니페스트와 대조만 하고 색인하지 않는다.")
    parser.add_argument("--force", action="store_true", help="내용이 같아도 다시 임베딩한다(임베딩 모델을 바꿨을 때).")
    args = parser.parse_args()

    if args.scan:
        print(json.dumps(scan_source_dir(load_manifest()), ensure_ascii=False, indent=2))
        return

    for result in ingest_all(force=args.force):
        print(result)


if __name__ == "__main__":
    main()
