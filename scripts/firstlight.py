#!/usr/bin/env python3
"""
For each day in a date range: print plan content ([en], [zh_cn], [zh_tw]) and generate MP3 files.
--preset 1 (default): 4 files (1x plain + 1.5x BGM + 2x BGM)
--preset 2: 4 files (1x plain + 1x BGM)
--preset 3: 7 files (all)
Plain: single file; BGM split into smaller files for easier download.
Default: today in Kiritimati (UTC+14) – the first timezone to see each new day.

Usage:
  python scripts/firstlight.py
  python scripts/firstlight.py --start-date 2026-02-27 --num-days 5
  python scripts/firstlight.py --start-date 2026-03-01 --end-date 2026-03-05
  python scripts/firstlight.py --plan chronological-1year --plan-start-date 2026-01-01
  python scripts/firstlight.py --preset 3   # all 7 files
"""

import argparse
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
        default="2026-02-17",
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
    parser.add_argument(
        "--preset",
        type=int,
        choices=[1, 2, 3],
        default=1,
        help="1=4 files (1x plain+1.5x+2x BGM), 2=4 files (1x plain+BGM), 3=7 files (all); default 1",
    )
    parser.add_argument("--use-tts", action="store_true", help="Use TTS audio instead of Everest")
    parser.add_argument(
        "--chapter-voice",
        type=str,
        choices=["male", "female", "rotate"],
        default="rotate",
        help="Voice source for Everest/David Yen (default: rotate)",
    )
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

    out_dir = Path(args.output) if args.output else REPO_ROOT / "audio" / args.plan
    out_dir.mkdir(parents=True, exist_ok=True)

    generate = REPO_ROOT / "scripts" / "generate_plan_audio.py"

    # Collect valid days in range (skip days with empty chapters – plan has gaps)
    days_to_generate = []
    d = start_date
    while d <= end_date:
        day_num = (d - plan_start).days + 1
        if 1 <= day_num <= max_day:
            entry = entries_by_day.get(day_num)
            if entry and entry.get("chapters"):
                days_to_generate.append((d, day_num, entry["chapters"]))
        d += timedelta(days=1)

    if not days_to_generate:
        first_d = start_date
        day_num_first = (first_d - plan_start).days + 1
        if day_num_first < 1:
            print(f"Date range {start_date}..{end_date} is before plan start ({plan_start}).")
            print(f"  Use --plan-start-date {start_date} to make {start_date} = day 1.")
        elif day_num_first > max_day:
            print(f"Date range {start_date}..{end_date} is past plan end (day {max_day}).")
        else:
            print(f"Day {day_num_first} ({first_d}) has no chapters in the plan (plan has gaps).")
            # Suggest next date with content
            for dn in range(day_num_first + 1, max_day + 1):
                if entries_by_day.get(dn, {}).get("chapters"):
                    next_d = plan_start + timedelta(days=dn - 1)
                    print(f"  Next day with content: Day {dn} ({next_d}). Try: --start-date {next_d}")
                    break
        return 1

    # 1. Print plan content for all given days
    print("\n" + "=" * 60, flush=True)
    print("Plan content (given days)", flush=True)
    print("=" * 60, flush=True)
    for d, day_num, chapters in days_to_generate:
        zh_cn = chapters_to_chinese(chapters, BOOK_CHINESE)
        zh_tw = chapters_to_chinese(chapters, BOOK_CHINESE_TW)
        en = chapters_to_english(chapters)
        print(f"\n--- Day {day_num} ({d}) ---", flush=True)
        print("[en]", flush=True)
        print(f"{plan.get('name', args.plan)} Day {day_num} ({d}): {en}\n", flush=True)
        print("[zh_cn]", flush=True)
        print(f"{plan.get('name_zh', '读经计划')} 第{day_num}天（{d}）：{zh_cn}\n", flush=True)
        print("[zh_tw]", flush=True)
        print(f"{plan.get('name_zh_tw', '讀經計劃')} 第{day_num}天（{d}）：{zh_tw}\n", flush=True)

    # 2. Generate MP3 files (preset controls which)
    preset = args.preset
    print("\n" + "=" * 60, flush=True)
    print("Generating MP3 files...", flush=True)
    print("=" * 60, flush=True)
    for d, day_num, chapters in days_to_generate:
        base = [
            sys.executable, str(generate),
            args.plan,
            "-o", str(out_dir),
            "--start-date", args.plan_start_date,
            "--start-day", str(day_num),
            "--end-day", str(day_num),
            "--speech-volume", str(args.speech_volume),
        ]
        if args.use_tts:
            base.append("--use-tts")
        if args.chapter_voice:
            base.extend(["--chapter-voice", args.chapter_voice])
        done = []
        if preset in (1, 2, 3):
            subprocess.run(base + ["--speed", "1"], check=True)
            done.append("plain")
        if preset in (2, 3):
            subprocess.run(base + ["--speed", "1", "--bgm", "--bgm-splits", "3"], check=True)
            done.append("原速(3)")
        if preset in (1, 3):
            subprocess.run(base + ["--speed", "1.5", "--bgm", "--bgm-splits", "2"], check=True)
            subprocess.run(base + ["--speed", "2", "--bgm", "--bgm-splits", "1"], check=True)
            done.extend(["加速(2)", "倍速"])
        print(f"✅ Day {day_num}: {' + '.join(done)}", flush=True)

    print(f"\nDone. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
