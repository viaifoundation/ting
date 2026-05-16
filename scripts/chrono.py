#!/usr/bin/env python3
"""
Generate Chronological 1-Year reading plan audio (年度歷史讀經).

Input is a day number (1–365) or a range (e.g. 1-5, 16-17).
Produces one file per day at 1.5x speed with background music.
Filename format: 年度歷史讀經第001天-創1-3.mp3

Voice modes (--voice-mode):
  rotate (default) — alternate male/female each chapter (single pass)
  male             — single male voice
  female           — single female voice
  compare          — each chapter twice: male then female (對照)

Usage:
  python scripts/chrono.py 1              # Day 1, rotate (default)
  python scripts/chrono.py 1-7            # Days 1-7, rotate
  python scripts/chrono.py 1 --voice-mode male      # Male only
  python scripts/chrono.py 1 --voice-mode female    # Female only
  python scripts/chrono.py 1 --voice-mode compare   # Male then female
"""

from __future__ import annotations

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

PLAN_ID = "chronological-1year"

# CLI --voice-mode → generate_plan_audio --chapter-voice
VOICE_MODE_TO_CHAPTER_VOICE = {
    "male": "male",
    "female": "female",
    "rotate": "rotate",
    "compare": "male_then_female",
}

DEFAULT_VOICE_MODE = "rotate"

AUDIO_SUBDIR_BY_MODE = {
    "male": "male",
    "female": "female",
    "rotate": "rotate",
    "compare": "compare",
}


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
            raise ValueError(f"Invalid day range: '{spec}'. Expected N or N-M")
        if start > end:
            raise ValueError(f"Start day {start} must be <= end day {end}")
        return list(range(start, end + 1))
    try:
        return [int(spec)]
    except ValueError:
        raise ValueError(f"Invalid day: '{spec}'. Expected an integer or range N-M")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "年度歷史讀經 Chronological 1-Year plan audio. "
            "Default: rotate (alternate male/female each chapter). "
            "Filenames: 年度歷史讀經第{dd}天 (or 對照 for compare)."
        ),
        epilog="""
Examples:
  python scripts/chrono.py 1              # Day 1, rotate (default)
  python scripts/chrono.py 1-7            # Days 1-7
  python scripts/chrono.py 1 --voice-mode male
  python scripts/chrono.py 1 --voice-mode compare
""",
    )
    parser.add_argument(
        "days",
        type=str,
        help="Day number (1–365) or range (e.g. 1-5, 16-17)",
    )
    parser.add_argument(
        "--voice-mode",
        type=str,
        choices=list(VOICE_MODE_TO_CHAPTER_VOICE.keys()),
        default=DEFAULT_VOICE_MODE,
        metavar="MODE",
        help=(
            "rotate (default): alternate male/female each chapter; "
            "male/female: single voice; "
            "compare: each chapter twice, male→female (對照)."
        ),
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory (default: audio/chronological-1year-<mode>/)",
    )
    parser.add_argument("--speech-volume", type=int, default=4)
    parser.add_argument("--use-tts", action="store_true", help="Use TTS audio instead of Everest")
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
        help="After each chapter's primary audio, append TTS comparison per --trans",
    )
    parser.add_argument(
        "--trans",
        type=str,
        default="cuvc",
        help="Comma-separated translations for --compare",
    )
    parser.add_argument(
        "--duplicate-random-seed",
        type=int,
        default=None,
        metavar="N",
        help="For compare mode: reproducible per-chapter order (omit = deterministic male→female)",
    )
    args = parser.parse_args()

    try:
        requested_days = parse_day_range(args.days)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    plan_path = REPO_ROOT / "assets" / "bible" / "plans" / f"{PLAN_ID}.json"
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

    v_mode = args.voice_mode
    ch_voice = VOICE_MODE_TO_CHAPTER_VOICE[v_mode]
    sub = AUDIO_SUBDIR_BY_MODE[v_mode]
    out_dir = Path(args.output) if args.output else REPO_ROOT / "audio" / f"chronological-1year-{sub}"
    out_dir.mkdir(parents=True, exist_ok=True)

    generate_script = REPO_ROOT / "scripts" / "generate_plan_audio.py"

    # ── Print plan content ────────────────────────────────────────────────────
    print(f"\n{'=' * 60}", flush=True)
    print(f"年度歷史讀經 Chronological 1-Year | voice: {v_mode} | days: {args.days}", flush=True)
    print("=" * 60, flush=True)
    for day_num, chapters in days_to_generate:
        zh_cn = chapters_to_chinese(chapters, BOOK_CHINESE)
        zh_tw = chapters_to_chinese(chapters, BOOK_CHINESE_TW)
        en = chapters_to_english(chapters)
        print(f"\n--- Day {day_num} ---", flush=True)
        print("[en]", flush=True)
        print(f"{plan.get('name', PLAN_ID)} Day {day_num}: {en}\n", flush=True)
        print("[zh_cn]", flush=True)
        print(f"{plan.get('name_zh', '读经计划')} 第{day_num}天：{zh_cn}\n", flush=True)
        print("[zh_tw]", flush=True)
        print(f"{plan.get('name_zh_tw', '讀經計劃')} 第{day_num}天：{zh_tw}\n", flush=True)

    # ── Generate MP3 files (1.5x speed + BGM) ────────────────────────────────
    print(f"\n{'=' * 60}", flush=True)
    print("Generating MP3 files… (1.5x + BGM)", flush=True)
    print("=" * 60, flush=True)

    for day_num, chapters in days_to_generate:
        cmd = [
            sys.executable,
            str(generate_script),
            PLAN_ID,
            "-o", str(out_dir),
            "--start-day", str(day_num),
            "--end-day", str(day_num),
            "--speech-volume", str(args.speech_volume),
            "--use-chapter-filename",
            "--no-speed-label",
            "--speed", "1.5",
            "--bgm",
            "--bgm-splits", "1",
            "--chapter-voice", ch_voice,
        ]
        if args.use_tts:
            cmd.append("--use-tts")
        if args.interleave_tts:
            cmd.append("--interleave-tts")
        if args.compare:
            cmd.append("--compare")
            cmd.extend(["--trans", args.trans])
        if args.duplicate_random_seed is not None:
            cmd.extend(["--duplicate-random-seed", str(args.duplicate_random_seed)])

        subprocess.run(cmd, check=True)
        zh_tw = chapters_to_chinese(chapters, BOOK_CHINESE_TW)
        print(f"✅ Day {day_num}: 年度歷史讀經第{day_num}天-{zh_tw} [{v_mode}]", flush=True)

    print(f"\nDone. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
