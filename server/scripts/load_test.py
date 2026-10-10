"""Measure /v1/transcribe latency against a running API: Phase 3's exit check.

    cd server
    uv run python scripts/load_test.py <base-url> <voice-note> [--requests 20] [--concurrency 1]

Installs one token, sends the same note N times, C at a time, and prints the
round trip (what the app waits for) and the server's own `processing_ms`, as
p50 / p95 / max, plus the status codes. Use a note you may send to the server
and to its ASR provider: never someone else's voice. Each request counts
against that token's daily quota (60 by default), so keep N below it.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter
from pathlib import Path

import httpx


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


async def run(base_url: str, note: Path, requests: int, concurrency: int) -> None:
    audio = note.read_bytes()
    slots = asyncio.Semaphore(concurrency)
    round_trips: list[float] = []
    processing: list[float] = []
    statuses: Counter[int] = Counter()

    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=120) as client:
        token = (await client.post("/v1/install")).raise_for_status().json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        async def one() -> None:
            async with slots:
                started = time.perf_counter()
                response = await client.post(
                    "/v1/transcribe",
                    headers=headers,
                    files={"audio": (note.name, audio, "audio/ogg")},
                )
                round_trips.append(time.perf_counter() - started)
                statuses[response.status_code] += 1
                if response.status_code == 200:
                    processing.append(response.json()["processing_ms"] / 1000)

        await asyncio.gather(*(one() for _ in range(requests)))

    print(f"{requests} requests, {concurrency} at a time, note {note.name} ({len(audio)} bytes)")
    print(f"status codes: {dict(sorted(statuses.items()))}")
    for label, values in (("round trip", round_trips), ("server", processing)):
        if values:
            print(
                f"{label:>10}: p50 {statistics.median(values):.2f} s"
                f"  p95 {percentile(values, 95):.2f} s  max {max(values):.2f} s"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("base_url", help="e.g. https://sma3ni-api.onrender.com")
    parser.add_argument("note", type=Path, help="a voice note you may send (never committed)")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(run(args.base_url, args.note, args.requests, args.concurrency))


if __name__ == "__main__":
    main()
