#!/usr/bin/env python3
"""
Generate daily MP3s for a reading plan.

For each day's chapters, assembles audio from Everest CUV (or TTS) and
optionally appends comparison-translation TTS segments per chapter.

Usage:
  python scripts/generate_plan_audio.py chronological-1year -o audio/
  python scripts/generate_plan_audio.py ninety-day-challenge -o audio/ --speech-volume 4
  python scripts/generate_plan_audio.py psalms-30days -o audio/ \\
    --compare --trans cuvt,ncvs
"""

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from plan_utils import chapters_to_filename, BOOK_FILENAME_ABBR_ZH_TW

# plan_id -> Chinese name pattern
PLAN_FILENAME = {
    "chronological-1year": "历史读经第{i}天",
    "chronological-90days": "90天历史读经第{i}天",
    "psalms-30days": "赞美诗篇第{i}天",
    "wisdom-praise-30days": "30天智慧讚美第{i:02d}天",
    "nt-40days": "40天新約挑戰第{i:02d}天",
    "nt-psalms-proverbs-90days": "90天新約詩篇箴言挑戰第{i:02d}天",
}
PLANS_DIR = REPO_ROOT / "assets" / "bible" / "plans"
CONCAT_SCRIPT = REPO_ROOT / "scripts" / "concat_daily.py"

# Speed -> Chinese label for BGM filenames
SPEED_LABEL = {1.0: "原速", 1.5: "加速", 2.0: "倍速"}
# Part position chars: 上(1st), 中(middle), 下(last)
PART_CHARS_2 = ("上", "下")
PART_CHARS_3 = ("上", "中", "下")


def split_chapters(chapters: list, k: int) -> list[list]:
    """Split chapters into k roughly equal groups (by count)."""
    n = len(chapters)
    base, r = divmod(n, k)
    sizes = [base + 1] * r + [base] * (k - r)
    result, idx = [], 0
    for s in sizes:
        result.append(chapters[idx : idx + s])
        idx += s
    return result


def get_bgm_suffix(speed: float, part_index: int, total_parts: int) -> str:
    """Get Chinese suffix for BGM filename: 原速上/中/下, 加速上/下, 倍速."""
    label = SPEED_LABEL.get(speed, f"{speed}x")
    if total_parts == 1:
        return label
    if total_parts == 2:
        return label + PART_CHARS_2[part_index]
    if total_parts == 3:
        return label + PART_CHARS_3[part_index]
    return f"{label}{part_index + 1}"


def main():
    parser = argparse.ArgumentParser(description="Generate daily MP3s from a reading plan")
    parser.add_argument("plan_id", help="Plan ID (e.g. chronological-1year)")
    parser.add_argument("-o", "--output", required=True, help="Output directory")
    parser.add_argument("--speech-volume", type=int, default=4,
                        help="Boost speech volume in dB (Everest is quiet, default 4)")
    parser.add_argument("--use-tts", action="store_true", help="Use TTS audio instead of Everest")
    parser.add_argument("--interleave-tts", action="store_true", help="Interleave Everest and TTS chapters")
    parser.add_argument(
        "--compare",
        action="store_true",
        default=False,
        help=(
            "Append TTS for additional translations after each chapter. "
            "Default: False. See --trans to configure which ones."
        ),
    )
    parser.add_argument(
        "--trans",
        type=str,
        default="cuvc",
        help=(
            "Comma-separated comparison translations (used with --compare). "
            "Supported: cuvc/cuvs, cuvt, ncvs, lcvs, clbs. Example: 'cuvt,ncvs' (default: cuvc)"
        ),
    )
    parser.add_argument("--bgm", action="store_true", help="Add background music")
    parser.add_argument("--bgm-volume", type=int, default=-20)
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed (e.g. 2.0 = 2x)")
    parser.add_argument("--chapter-voice", type=str, choices=["male", "female", "rotate"], default="rotate", help="Voice source for Everest/David Yen (default: rotate)")
    parser.add_argument("--bgm-splits", type=int, default=1,
                        help="Split BGM output into N files (1x->3, 1.5x->2, 2x->1)")
    parser.add_argument("--start-date", type=str, default="2026-02-17",
                        help="First day date YYYY-MM-DD")
    parser.add_argument("--start-day", type=int, default=1)
    parser.add_argument("--end-day", type=int, default=None)
    parser.add_argument(
        "--use-chapter-filename",
        action="store_true",
        help="Use day+chapter info for filename instead of date prefix (e.g. 30天智慧讚美第01天_詩1-5_箴1)",
    )
    parser.add_argument(
        "--no-speed-label",
        action="store_true",
        help="Omit the speed label (_加速 / _倍速) from BGM filenames",
    )
    parser.add_argument(
        "--filename-suffix",
        type=str,
        default="",
        help="Append this suffix to the base filename (before .mp3), e.g. '_對照文理和合本'",
    )
    args = parser.parse_args()

    plan_path = PLANS_DIR / f"{args.plan_id}.json"
    if not plan_path.exists():
        print(f"Plan not found: {plan_path}")
        print(f"Available: {[p.stem for p in PLANS_DIR.glob('*.json')]}")
        return 1

    plan = json.loads(plan_path.read_text())
    entries = plan["entries"]
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    start_date = date.fromisoformat(args.start_date)
    name_fmt = PLAN_FILENAME.get(args.plan_id, "读经第{i}天")
    start = args.start_day
    end = args.end_day or max(e["day"] for e in entries)

    for entry in entries:
        day = entry["day"]
        if day < start or day > end:
            continue
        chapters = entry.get("chapters", [])
        if not chapters:
            print(f"Day {day}: skip (no chapters)")
            continue
        d = start_date + timedelta(days=day - 1)
        if args.use_chapter_filename:
            ch_str = chapters_to_filename(chapters, abbr=BOOK_FILENAME_ABBR_ZH_TW)
            base_name = f"{name_fmt.format(i=day)}_{ch_str}"
        else:
            prefix = d.strftime("%Y%m%d")  # YYYYMMDD
            base_name = f"{prefix}_{name_fmt.format(i=day)}"
        if args.filename_suffix:
            base_name += args.filename_suffix

        if args.bgm:
            splits = args.bgm_splits
            groups = split_chapters(chapters, splits)
            for i, group in enumerate(groups):
                spec = ",".join(group)
                suffix = get_bgm_suffix(args.speed, i, splits)
                if args.no_speed_label:
                    out_file = out_dir / f"{base_name}.mp3"
                else:
                    out_file = out_dir / f"{base_name}_{suffix}.mp3"
                cmd = [
                    sys.executable, str(CONCAT_SCRIPT),
                    "-c", spec,
                    "-o", str(out_file),
                    "--speech-volume", str(args.speech_volume),
                    "--bgm", "--bgm-volume", str(args.bgm_volume),
                ]
                if args.speed > 1.0:
                    cmd.extend(["--speed", str(args.speed)])
                if args.use_tts:
                    cmd.append("--use-tts")
                if args.interleave_tts:
                    cmd.append("--interleave-tts")
                if args.compare:
                    cmd.append("--compare")
                    cmd.extend(["--trans", args.trans])
                if args.chapter_voice:
                    cmd.extend(["--chapter-voice", args.chapter_voice])
                subprocess.run(cmd, check=True)
                print(f"Day {day}: {out_file.name}")
        else:
            # Plain: 1x only, no suffix
            spec = ",".join(chapters)
            out_file = out_dir / f"{base_name}.mp3"
            cmd = [
                sys.executable, str(CONCAT_SCRIPT),
                "-c", spec,
                "-o", str(out_file),
                "--speech-volume", str(args.speech_volume),
            ]
            if args.speed > 1.0:
                cmd.extend(["--speed", str(args.speed)])
            if args.use_tts:
                cmd.append("--use-tts")
            if args.interleave_tts:
                cmd.append("--interleave-tts")
            if args.compare:
                cmd.append("--compare")
                cmd.extend(["--trans", args.trans])
            if args.chapter_voice:
                cmd.extend(["--chapter-voice", args.chapter_voice])
            subprocess.run(cmd, check=True)
            print(f"Day {day}: {out_file.name}")

    print(f"Done. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
