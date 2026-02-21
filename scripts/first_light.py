#!/usr/bin/env python3
"""
Generate today's 90-day chronological reading (one day, both with and without BGM).
Uses Kiritimati (Christmas Island) timezone (UTC+14) – the first to see the new day.

Usage:
  python scripts/first_light.py
  python scripts/first_light.py --start-date 2026-02-17
"""

import argparse
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import zoneinfo

REPO_ROOT = Path(__file__).resolve().parent.parent
# Kiritimati (Christmas Island) – first timezone to see each new day
FIRST_TZ = zoneinfo.ZoneInfo("Pacific/Kiritimati")


def main():
    parser = argparse.ArgumentParser(
        description="Generate today's 90-day chronological reading (Kiritimati timezone)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2026-02-17",
        help="Plan start date YYYY-MM-DD (day 1)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory (default: output/chronological-90days)",
    )
    parser.add_argument("--speech-volume", type=int, default=4)
    parser.add_argument("--speed", type=float, default=2.0, help="Playback speed (default 2x)")
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    now = datetime.now(FIRST_TZ)
    today = now.date()

    # Plan day = 1 + (today - start_date).days, clamped to 1–90
    day_num = (today - start_date).days + 1
    if day_num < 1:
        print(f"Today {today} is before plan start {start_date}. Day 1 = {start_date}.")
        return 1
    if day_num > 90:
        print(f"Today {today} is past day 90. Plan runs {start_date} through day 90.")
        return 1

    out_dir = Path(args.output) if args.output else REPO_ROOT / "output" / "chronological-90days"
    out_dir.mkdir(parents=True, exist_ok=True)

    generate = REPO_ROOT / "scripts" / "generate_plan_audio.py"
    base = [
        sys.executable, str(generate),
        "chronological-90days",
        "-o", str(out_dir),
        "--start-date", args.start_date,
        "--start-day", str(day_num),
        "--end-day", str(day_num),
        "--speech-volume", str(args.speech_volume),
        "--speed", str(args.speed),
    ]

    # Without BGM
    subprocess.run(base, check=True)

    # With BGM
    subprocess.run(base + ["--bgm"], check=True)

    prefix = today.strftime("%Y%m%d")
    print(f"\n✅ Day {day_num} ({today}): {prefix}_90天历史读经第{day_num}天.mp3, {prefix}_90天历史读经第{day_num}天-bgm.mp3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
