"""T-QUAL-1 비동기 처리 벤치마크 부하 드라이버.

httpx.AsyncClient(이미 프로젝트 의존성에 존재 — 신규 패키지 불필요)로 동시 요청을 보내고
동시성 레벨별 P50/P95/P99 지연시간과 처리량(req/s)을 측정한다.

사용 예:
    # bench_app.py의 3개 변형(async-io/blocking/threadpool) 비교
    uv run python benchmarks/run_load.py --target bench --concurrency 1,10,50,100

    # 실행 중인 실제 앱의 안전한 읽기 전용 엔드포인트 실측
    uv run python benchmarks/run_load.py --target live \
        --url http://localhost:8000/api/v1/medication/schedules \
        --token "Bearer <access_token>" --concurrency 1,10,50,100

결과는 콘솔에 Markdown 표로 출력되고, --csv-out 경로에 CSV로도 저장된다
(문서 docs/tasks/T-QUAL-1-async-benchmark.md 결과 표에 그대로 붙여넣기 위함).
"""

import argparse
import asyncio
import csv
import statistics
import sys
import time

import httpx

BENCH_APP_BASE = "http://localhost:8090"
BENCH_VARIANTS = ["async-io", "blocking", "threadpool"]


def percentile(values: list[float], pct: float) -> float:
    """단순 최근접 순위 방식 백분위수 (외부 통계 라이브러리 불필요)."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(pct / 100 * (len(ordered) - 1)))))
    return ordered[idx]


async def _fire_one(client: httpx.AsyncClient, url: str, headers: dict) -> float:
    start = time.perf_counter()
    resp = await client.get(url, headers=headers)
    elapsed = time.perf_counter() - start
    resp.raise_for_status()
    return elapsed


async def run_round(url: str, concurrency: int, headers: dict, timeout: float) -> tuple[list[float], float]:
    """`concurrency`개의 요청을 동시에 발사하고 (지연시간 리스트, 총 소요시간)을 반환."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        wall_start = time.perf_counter()
        results = await asyncio.gather(
            *[_fire_one(client, url, headers) for _ in range(concurrency)],
            return_exceptions=True,
        )
        wall_elapsed = time.perf_counter() - wall_start

    latencies = [r for r in results if isinstance(r, float)]
    errors = [r for r in results if not isinstance(r, float)]
    if errors:
        print(f"  [경고] {len(errors)}건 실패 (예: {errors[0]!r})", file=sys.stderr)
    return latencies, wall_elapsed


async def measure(url: str, concurrency_levels: list[int], rounds: int, headers: dict, timeout: float):
    rows = []
    for c in concurrency_levels:
        all_latencies: list[float] = []
        total_wall = 0.0
        for _ in range(rounds):
            latencies, wall = await run_round(url, c, headers, timeout)
            all_latencies.extend(latencies)
            total_wall += wall
        n = len(all_latencies)
        throughput = n / total_wall if total_wall > 0 else float("nan")
        rows.append(
            {
                "concurrency": c,
                "n": n,
                "p50_ms": round(percentile(all_latencies, 50) * 1000, 1),
                "p95_ms": round(percentile(all_latencies, 95) * 1000, 1),
                "p99_ms": round(percentile(all_latencies, 99) * 1000, 1),
                "throughput_rps": round(throughput, 1),
            }
        )
    return rows


def print_markdown_table(title: str, rows: list[dict]):
    print(f"\n### {title}\n")
    print("| 동시성 | 샘플 수 | P50 (ms) | P95 (ms) | P99 (ms) | 처리량 (req/s) |")
    print("| --- | --- | --- | --- | --- | --- |")
    for r in rows:
        print(
            f"| {r['concurrency']} | {r['n']} | {r['p50_ms']} | {r['p95_ms']} | "
            f"{r['p99_ms']} | {r['throughput_rps']} |"
        )


def write_csv(path: str, all_results: dict[str, list[dict]]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["variant", "concurrency", "n", "p50_ms", "p95_ms", "p99_ms", "throughput_rps"])
        for variant, rows in all_results.items():
            for r in rows:
                writer.writerow(
                    [variant, r["concurrency"], r["n"], r["p50_ms"], r["p95_ms"], r["p99_ms"], r["throughput_rps"]]
                )
    print(f"\nCSV 저장됨: {path}")


async def main_async(args):
    concurrency_levels = [int(x) for x in args.concurrency.split(",")]
    all_results: dict[str, list[dict]] = {}

    if args.target == "bench":
        for variant in BENCH_VARIANTS:
            url = f"{BENCH_APP_BASE}/bench/{variant}?delay={args.delay}&steps={args.steps}"
            print(f"\n측정 중: {variant} ({url})")
            rows = await measure(url, concurrency_levels, args.rounds, headers={}, timeout=args.timeout)
            print_markdown_table(variant, rows)
            all_results[variant] = rows
    else:
        if not args.url:
            print("오류: --target live 사용 시 --url이 필요합니다.", file=sys.stderr)
            sys.exit(1)
        headers = {"Authorization": args.token} if args.token else {}
        print(f"\n측정 중: live ({args.url})")
        rows = await measure(args.url, concurrency_levels, args.rounds, headers=headers, timeout=args.timeout)
        print_markdown_table("실제 엔드포인트", rows)
        all_results["live"] = rows

    if args.csv_out:
        write_csv(args.csv_out, all_results)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", choices=["bench", "live"], default="bench")
    parser.add_argument("--url", help="target=live일 때 요청할 전체 URL")
    parser.add_argument("--token", help='target=live일 때 Authorization 헤더 값 (예: "Bearer xxx")')
    parser.add_argument("--concurrency", default="1,10,50,100", help="쉼표로 구분된 동시성 레벨 목록")
    parser.add_argument("--rounds", type=int, default=3, help="동시성 레벨당 반복 라운드 수(샘플 안정화)")
    parser.add_argument("--delay", type=float, default=0.1, help="target=bench일 때 스텝당 시뮬레이션 지연(초)")
    parser.add_argument("--steps", type=int, default=3, help="target=bench일 때 순차 I/O 스텝 수")
    parser.add_argument("--timeout", type=float, default=30.0, help="요청 타임아웃(초)")
    parser.add_argument("--csv-out", default="benchmarks/results/latest.csv", help="CSV 출력 경로")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
