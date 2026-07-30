#!/usr/bin/env python3
"""Light concurrent HTTP smoke test for catalog and book detail APIs."""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch(url: str, timeout: float) -> tuple[str, float, int | None, str | None]:
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            elapsed = time.perf_counter() - start
            return url, elapsed, response.status, None
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - start
        return url, elapsed, exc.code, str(exc)
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        return url, elapsed, None, str(exc)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((pct / 100) * (len(ordered) - 1)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description='Concurrent HTTP smoke test')
    parser.add_argument('--base', default='http://localhost:8000', help='Base URL')
    parser.add_argument('--workers', type=int, default=30)
    parser.add_argument('--requests', type=int, default=20, help='Requests per worker')
    parser.add_argument('--slug', default='', help='Book slug for detail endpoint')
    parser.add_argument('--timeout', type=float, default=15.0)
    args = parser.parse_args()

    base = args.base.rstrip('/')
    catalog_url = f'{base}/api/library/'
    detail_url = f'{base}/api/library/{args.slug}/' if args.slug else None
    urls = [catalog_url]
    if detail_url:
        urls.append(detail_url)

    jobs = []
    for _ in range(args.workers):
        for _ in range(args.requests):
            for url in urls:
                jobs.append(url)

    latencies: list[float] = []
    errors = 0
    server_errors = 0
    client_errors = 0
    status_counts: dict[int, int] = {}

    print(f'Firing {len(jobs)} requests with {args.workers} workers…')
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch, url, args.timeout) for url in jobs]
        for future in as_completed(futures):
            url, elapsed, status, err = future.result()
            latencies.append(elapsed)
            if err:
                if isinstance(err, str) and 'HTTP Error' in err:
                    # urllib raises on 4xx/5xx; treat 4xx as handled responses.
                    try:
                        status = int(err.split('HTTP Error ')[1].split(':')[0])
                    except (IndexError, ValueError):
                        status = None
                else:
                    errors += 1
                    print(f'ERROR {url}: {err}', file=sys.stderr)
                    continue
            if status is not None:
                status_counts[status] = status_counts.get(status, 0) + 1
                if status >= 500:
                    server_errors += 1
                elif status >= 400:
                    client_errors += 1

    total = time.perf_counter() - started
    ok = len(jobs) - errors - server_errors
    print('--- load_smoke summary ---')
    print(f'total_requests: {len(jobs)}')
    print(f'duration_sec: {total:.2f}')
    print(f'connection_error_count: {errors}')
    print(f'status_4xx_count: {client_errors}')
    print(f'status_5xx_count: {server_errors}')
    print(f'status_counts: {dict(sorted(status_counts.items()))}')
    if latencies:
        print(f'latency_p50_ms: {percentile(latencies, 50) * 1000:.1f}')
        print(f'latency_p95_ms: {percentile(latencies, 95) * 1000:.1f}')
        print(f'latency_max_ms: {max(latencies) * 1000:.1f}')
    print(f'handled_response_rate: {(len(jobs) - errors - server_errors) / len(jobs) * 100:.1f}%')
    return 1 if errors or server_errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
