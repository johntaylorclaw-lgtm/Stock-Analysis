from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from time import perf_counter

from stock_maintainance.features.build import build_features


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_PATH = ROOT / "logs" / "phase3_history_build_progress.jsonl"


def safe_print(message: str) -> None:
    try:
        print(message, flush=True)
    except BrokenPipeError:
        pass


def parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"invalid date: {value}")


def month_chunks(start: date, end: date) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    current = start
    while current <= end:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        chunk_end = min(end, next_month - timedelta(days=1))
        chunks.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return chunks


def completed_chunks(log_path: Path) -> set[tuple[str, str]]:
    if not log_path.exists():
        return set()
    done: set[tuple[str, str]] = set()
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("status") == "success":
            done.add((item["start_date"], item["end_date"]))
    return done


def append_log(log_path: Path, item: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2006-01-04")
    parser.add_argument("--end-date", default="2026-05-26")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--module", action="append")
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    args = parser.parse_args()

    chunks = month_chunks(parse_date(args.start_date), parse_date(args.end_date))
    log_path = Path(args.log_path)
    if not log_path.is_absolute():
        log_path = ROOT / log_path
    done = completed_chunks(log_path) if args.resume else set()
    safe_print(f"phase3 history chunks: {len(chunks)}; resume_done={len(done)}")

    for index, (chunk_start, chunk_end) in enumerate(chunks, start=1):
        key = (chunk_start.isoformat(), chunk_end.isoformat())
        if key in done:
            safe_print(f"[{index}/{len(chunks)}] skip {key[0]} to {key[1]}")
            continue
        safe_print(f"[{index}/{len(chunks)}] build {key[0]} to {key[1]}")
        started = perf_counter()
        try:
            result = build_features(
                modules=args.module,
                start_date=key[0],
                end_date=key[1],
                mode="history",
                allow_confirmed_history=True,
            )
            elapsed = perf_counter() - started
            rows = {
                item["module"]: item.get("rows_written", 0)
                for item in result.get("results", [])
            }
            append_log(
                log_path,
                {
                    "status": "success",
                    "start_date": key[0],
                    "end_date": key[1],
                    "elapsed_sec": round(elapsed, 3),
                    "rows_written": rows,
                }
            )
            safe_print(f"[{index}/{len(chunks)}] success {elapsed:.1f}s")
        except Exception as exc:
            elapsed = perf_counter() - started
            append_log(
                log_path,
                {
                    "status": "failed",
                    "start_date": key[0],
                    "end_date": key[1],
                    "elapsed_sec": round(elapsed, 3),
                    "error": str(exc),
                }
            )
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
