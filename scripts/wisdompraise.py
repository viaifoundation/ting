#!/usr/bin/env python3
"""
Generate Psalms & Proverbs reading-plan audio (30/45/60/90-day JSON in assets/bible/plans/).

Default: each chapter is read twice — David Yen (male) then Everest (female) — see
`--chapter-voice`. Input is a day number or range (e.g. 1-5). Output uses 1.5x + BGM.

Translation comparison (--compare):
  After each chapter’s primary audio (both voices if male_then_female), append TTS for
  each translation in --trans (cuvc, cuvt, ncvs, lcvs, clbs).

Usage:
  python scripts/wisdompraise.py 1
  python scripts/wisdompraise.py 1-5 --plan wisdom-praise-90days
  python scripts/wisdompraise.py 1-30 --chapter-voice rotate
  python scripts/wisdompraise.py 1-5 --compare --trans cuvt,ncvs,clbs
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from plan_utils import (
    BOOK_CHINESE,
    BOOK_CHINESE_TW,
    chapters_to_chinese,
    chapters_to_english,
    load_plan,
)

DEFAULT_PLAN_ID = "wisdom-praise-30days"


def parse_day_range(spec: str) -> list[int]:
    """
    Parse a day specification into a list of day numbers.
    Accepts:
      - a single integer: "1" -> [1]
      - a range:          "1-5" -> [1, 2, 3, 4, 5]
    """
    spec = spec.strip()
    if "-" in spec:
        parts = spec.split("-", 1)
        try:
            start, end = int(parts[0]), int(parts[1])
        except ValueError:
            raise ValueError(f"Invalid day range: '{spec}'. Expected format: N or N-M")
        if start > end:
            raise ValueError(f"Start day {start} must be <= end day {end}")
        return list(range(start, end + 1))
    else:
        try:
            return [int(spec)]
        except ValueError:
            raise ValueError(f"Invalid day: '{spec}'. Expected an integer or range N-M")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Psalms & Proverbs 30-day plan audio (1.5x + BGM)",
        epilog="""
Examples:
  python scripts/wisdompraise.py 1
  python scripts/wisdompraise.py 1-5
  python scripts/wisdompraise.py 16-17
  python scripts/wisdompraise.py 1-30
""",
    )
    parser.add_argument(
        "days",
        type=str,
        help="Day number or range (e.g. 1-5); must fit the selected plan length",
    )
    parser.add_argument(
        "--plan",
        type=str,
        default=DEFAULT_PLAN_ID,
        metavar="PLAN_ID",
        help=(
            "Plan JSON id (default: wisdom-praise-30days). "
            "Also: wisdom-praise-45days, wisdom-praise-60days, wisdom-praise-90days"
        ),
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory (default: audio/psalms-proverbs-30days/)",
    )
    parser.add_argument("--speech-volume", type=int, default=4)
    parser.add_argument(
        "--use-tts",
        action="store_true",
        help="Use TTS audio instead of Everest",
    )
    parser.add_argument(
        "--chapter-voice",
        type=str,
        choices=[
            "male",
            "female",
            "rotate",
            "male_then_female",
            "female_then_male",
            "duplicate_random",
        ],
        default="male_then_female",
        help=(
            "male_then_female / female_then_male / duplicate_random: twice per chapter; "
            "rotate=alternate each chapter; male/female=single. Default: male_then_female"
        ),
    )
    parser.add_argument(
        "--duplicate-random-seed",
        type=int,
        default=None,
        metavar="N",
        help="For duplicate_random: reproducible per-chapter order (omit = random)",
    )
    parser.add_argument(
        "--interleave-tts",
        action="store_true",
        default=False,
        help="Interleave Everest CUV and TTS CUVC chapter by chapter (default: False)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        default=False,
        help=(
            "After each chapter, append TTS audio for comparison translations "
            "(default: False). Pairs with --trans to choose which ones."
        ),
    )
    parser.add_argument(
        "--trans",
        type=str,
        default="cuvc",
        help=(
            "Comma-separated translations to compare after each chapter "
            "(used with --compare). Supported: cuvc/cuvs (CUV Simplified, default), "
            "cuvt (CUV Traditional), ncvs (New Chinese Version), lcvs (Living Chinese), "
            "clbs (Chinese Living Bible). Example: 'cuvt,ncvs,clbs'"
        ),
    )
    args = parser.parse_args()

    # Parse day range
    try:
        requested_days = parse_day_range(args.days)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    plan_id = args.plan.strip()
    plan_path = REPO_ROOT / "assets" / "bible" / "plans" / f"{plan_id}.json"
    if not plan_path.exists():
        print(f"❌ Plan not found: {plan_path}")
        return 1

    plan = load_plan(plan_path)
    max_day = plan["days"]
    entries_by_day = {e["day"]: e for e in plan["entries"]}

    # Validate requested days
    invalid = [d for d in requested_days if d < 1 or d > max_day]
    if invalid:
        print(f"❌ Day(s) out of range (plan has {max_day} days): {invalid}")
        return 1

    # Collect entries
    days_to_generate = []
    for day_num in requested_days:
        entry = entries_by_day.get(day_num)
        if not entry or not entry.get("chapters"):
            print(f"⚠️  Day {day_num}: no chapters in plan, skipping.")
            continue
        days_to_generate.append((day_num, entry["chapters"]))

    if not days_to_generate:
        print("❌ No valid days to generate.")
        return 1

    out_dir = Path(args.output) if args.output else REPO_ROOT / "audio" / plan_id
    out_dir.mkdir(parents=True, exist_ok=True)

    generate = REPO_ROOT / "scripts" / "generate_plan_audio.py"

    # ── Print plan content ────────────────────────────────────────────────────
    print("\n" + "=" * 60, flush=True)
    print("Plan content", flush=True)
    print("=" * 60, flush=True)
    for day_num, chapters in days_to_generate:
        zh_cn = chapters_to_chinese(chapters, BOOK_CHINESE)
        zh_tw = chapters_to_chinese(chapters, BOOK_CHINESE_TW)
        en = chapters_to_english(chapters)
        print(f"\n--- Day {day_num} ---", flush=True)
        print("[en]",  flush=True)
        print(f"{plan.get('name', plan_id)} Day {day_num}: {en}\n", flush=True)
        print("[zh_cn]", flush=True)
        print(f"{plan.get('name_zh', '读经计划')} 第{day_num}天：{zh_cn}\n", flush=True)
        print("[zh_tw]", flush=True)
        print(f"{plan.get('name_zh_tw', '讀經計劃')} 第{day_num}天：{zh_tw}\n", flush=True)

    # ── Generate MP3 files (1.5x speed + BGM) ────────────────────────────────
    print("\n" + "=" * 60, flush=True)
    print("Generating MP3 files… (1.5x + BGM)", flush=True)
    print("=" * 60, flush=True)

    for day_num, chapters in days_to_generate:
        cmd = [
            sys.executable, str(generate),
            plan_id,
            "-o", str(out_dir),
            "--start-day", str(day_num),
            "--end-day",   str(day_num),
            "--speech-volume", str(args.speech_volume),
            "--use-chapter-filename",
            "--no-speed-label",
            "--speed", "1.5",
            "--bgm",
            "--bgm-splits", "1",
        ]
        if args.use_tts:
            cmd.append("--use-tts")
        if args.chapter_voice:
            cmd.extend(["--chapter-voice", args.chapter_voice])
        if args.interleave_tts:
            cmd.append("--interleave-tts")
        if args.compare:
            cmd.append("--compare")
            cmd.extend(["--trans", args.trans])
        if args.duplicate_random_seed is not None:
            cmd.extend(["--duplicate-random-seed", str(args.duplicate_random_seed)])

        subprocess.run(cmd, check=True)
        print(f"✅ Day {day_num}: generated", flush=True)

    print(f"\nDone. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
