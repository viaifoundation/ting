#!/usr/bin/env python3
"""
Generate reading plan audio for a date range (default: today in Kiritimati).
Creates both with- and without-BGM versions per day.
Uses Pacific/Kiritimati (UTC+14) – the first timezone to see each new day.

Usage:
  python scripts/first_light.py
  python scripts/first_light.py --start-date 2026-02-27 --num-days 5
  python scripts/first_light.py --start-date 2026-03-01 --end-date 2026-03-05
  python scripts/first_light.py --plan chronological-1year --plan-start-date 2026-01-01
"""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import zoneinfo

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from plan_utils import (
    BOOK_CHINESE,
    BOOK_CHINESE_TW,
    chapters_to_chinese,
    chapters_to_english,
    load_plan,
)

FIRST_TZ = zoneinfo.ZoneInfo("Pacific/Kiritimati")

PLAN_FILENAME = {
    "chronological-1year": "历史读经第{i}天",
    "chronological-90days": "90天历史读经第{i}天",
}
PLAN_NAME_CN = {
    "chronological-1year": "历史读经",
    "chronological-90days": "90天历史读经",
}
PLAN_NAME_TW = {
    "chronological-1year": "歷史讀經",
    "chronological-90days": "90天歷史讀經",
}


def main():
    parser = argparse.ArgumentParser(
        description="Generate reading plan audio for date range (Kiritimati timezone)"
    )
    parser.add_argument(
        "--plan",
        type=str,
        default="chronological-90days",
        help="Plan ID (default: chronological-90days)",
    )
    parser.add_argument(
        "--plan-start-date",
        type=str,
        default="2026-02-27",
        help="Plan day 1 calendar date YYYY-MM-DD",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="First calendar date to generate (default: today in Kiritimati)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Last calendar date to generate (default: same as start-date)",
    )
    parser.add_argument(
        "--num-days",
        type=int,
        default=1,
        help="Number of days to generate (used if --end-date not set; default 1)",
    )
    parser.add_argument("-o", "--output", type=str, default=None)
    parser.add_argument("--speech-volume", type=int, default=4)
    parser.add_argument("--speed", type=float, default=2.0)
    args = parser.parse_args()

    plan_start = date.fromisoformat(args.plan_start_date)
    today = datetime.now(FIRST_TZ).date()

    start_date = date.fromisoformat(args.start_date) if args.start_date else today
    if args.end_date:
        end_date = date.fromisoformat(args.end_date)
    else:
        end_date = start_date + timedelta(days=args.num_days - 1)

    if start_date > end_date:
        print("start-date must be <= end-date")
        return 1

    plan_path = REPO_ROOT / "assets" / "bible" / "plans" / f"{args.plan}.json"
    if not plan_path.exists():
        print(f"Plan not found: {args.plan}")
        return 1

    plan = load_plan(plan_path)
    max_day = max(e["day"] for e in plan["entries"])
    entries_by_day = {e["day"]: e for e in plan["entries"]}

    out_dir = Path(args.output) if args.output else REPO_ROOT / "output" / args.plan
    out_dir.mkdir(parents=True, exist_ok=True)

    generate = REPO_ROOT / "scripts" / "generate_plan_audio.py"
    name_fmt = PLAN_FILENAME.get(args.plan, "读经第{i}天")
    plan_name_cn = PLAN_NAME_CN.get(args.plan, args.plan)
    plan_name_tw = PLAN_NAME_TW.get(args.plan, args.plan)

    d = start_date
    while d <= end_date:
        day_num = (d - plan_start).days + 1
        if day_num < 1 or day_num > max_day:
            d += timedelta(days=1)
            continue

        entry = entries_by_day.get(day_num)
        if not entry or not entry.get("chapters"):
            d += timedelta(days=1)
            continue

        chapters = entry["chapters"]
        zh_cn = chapters_to_chinese(chapters, BOOK_CHINESE)
        zh_tw = chapters_to_chinese(chapters, BOOK_CHINESE_TW)
        en = chapters_to_english(chapters)

        print(f"\n--- Day {day_num} ({d}) ---", flush=True)
        print("[en]", flush=True)
        print(f"Day {day_num} ({d}): {en}\n", flush=True)
        print("[zh_cn]", flush=True)
        print(f"第{day_num}天（{d}）：{zh_cn}\n", flush=True)
        print("[zh_tw]", flush=True)
        print(f"第{day_num}天（{d}）：{zh_tw}\n", flush=True)

        base = [
            sys.executable, str(generate),
            args.plan,
            "-o", str(out_dir),
            "--start-date", args.plan_start_date,
            "--start-day", str(day_num),
            "--end-day", str(day_num),
            "--speech-volume", str(args.speech_volume),
            "--speed", str(args.speed),
        ]

        subprocess.run(base, check=True)
        subprocess.run(base + ["--bgm"], check=True)

        prefix = d.strftime("%Y%m%d")
        print(f"✅ {prefix}_{name_fmt.format(i=day_num)}.mp3, {prefix}_{name_fmt.format(i=day_num)}-bgm.mp3")

        d += timedelta(days=1)

    print(f"\nDone. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
