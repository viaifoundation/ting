#!/usr/bin/env python3
"""
Generate daily MP3s for a reading plan.

For each day's chapters, assembles audio from Everest CUV (or TTS) and
optionally appends comparison-translation TTS segments per chapter.

With --use-chapter-filename, wisdom-praise-* and psalms-proverbs-youversion-* use descriptive stems:
  {N}天智慧讚美第{dd}天-{chapters}  (rotate / single-voice)
  {N}天智慧讚美對照第{dd}天-{chapters}  (male_then_female, female_then_male; 對照 = parallel version)
N = plan days from JSON; dd = day index zero-padded; chapter groups joined with \"-\".
Other plan IDs use PLAN_FILENAME patterns; chapter groups default joiner \"-\" here.

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
from plan_utils import chapters_to_filename, BOOK_FILENAME_ABBR_ZH_TW, BOOK_FILENAME_ABBR, BOOK_FILENAME_ABBR_ZH_CN

# plan_id -> Traditional Chinese name pattern
PLAN_FILENAME_ZH_TW = {
    "chronological-1year": "歷史時序聆聽第{i}天",
    "chronological-90days": "90天歷史時序聆聽第{i}天",
    "psalms-30days": "讚美詩篇第{i}天",
    "nt-40days": "40天新約挑戰第{i:02d}天",
    "nt-psalms-proverbs-90days": "90天新約詩篇箴言挑戰第{i:02d}天",
    "psalms-proverbs-186days": "半年智慧讚美聆聽第{i}天",
}

# plan_id -> Simplified Chinese name pattern
PLAN_FILENAME_ZH_CN = {
    "chronological-1year": "历史时序聆听第{i}天",
    "chronological-90days": "90天历史时序聆听第{i}天",
    "psalms-30days": "赞美诗篇第{i}天",
    "nt-40days": "40天新约挑战第{i:02d}天",
    "nt-psalms-proverbs-90days": "90天新约诗篇箴言挑战第{i:02d}天",
    "psalms-proverbs-186days": "半年智慧赞美聆听第{i}天",
}


# Wisdom & Praise + YouVersion Psalms/Proverbs: short stems 智讚{N}-{d} / 智讚對{N}-{d}
WISDOM_PRAISE_STYLE_PLANS = frozenset(
    {
        "wisdom-praise-30days",
        "wisdom-praise-45days",
        "wisdom-praise-60days",
        "wisdom-praise-90days",
        "psalms-proverbs-youversion-31",
        "psalms-proverbs-youversion-372",
        "psalms-proverbs-62days",
        "psalms-proverbs-93days",
    }
)
# Chronological 1-Year: 年度歷史讀經第{d}天 / 年度歷史讀經對照第{d}天
CHRONO_STYLE_PLANS = frozenset({"chronological-1year", "chronological-6month", "chronological-90days"})

_CHAPTER_VOICE_DUP = frozenset(
    {"male_then_female", "female_then_male", "duplicate_random"}
)


def wisdom_praise_filename_label(plan_days: int, day: int, chapter_voice: str, lang: str = "zh-tw") -> str:
    """Descriptive stem: {N}天智慧讚美聆聽第{day}天 or {N}天智慧讚美聆聽對照第{day}天."""
    dd = str(day)
    is_tw = (lang == "zh-tw")
    praise = "智慧讚美聆聽" if is_tw else "智慧赞美聆听"
    compare = "對照" if is_tw else "对照"
    if chapter_voice in _CHAPTER_VOICE_DUP:
        return f"{plan_days}天{praise}{compare}第{dd}天"
    return f"{plan_days}天{praise}第{dd}天"


def chrono_filename_label(plan_id: str, day: int, chapter_voice: str, lang: str = "zh-tw") -> str:
    """Descriptive stem: 年度歷史時序聆聽第{d}天 or 半年歷史時序聆聽第{d}天."""
    prefix = "半年" if "6month" in plan_id else "年度"
    is_tw = (lang == "zh-tw")
    chrono = "歷史時序聆聽" if is_tw else "历史时序聆听"
    compare = "對照" if is_tw else "对照"
    if chapter_voice in _CHAPTER_VOICE_DUP:
        return f"{prefix}{chrono}{compare}第{day}天"
    return f"{prefix}{chrono}第{day}天"



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


def get_bgm_suffix_eng(speed: float, part_index: int, total_parts: int) -> str:
    """Get English suffix for BGM filename: 1.5x, 1.5xa, 1.5xb."""
    label = f"{speed}x"
    if total_parts == 1:
        return label
    part_char = chr(ord('a') + part_index)
    return f"{label}{part_char}"


def construct_base_name(plan_id, plan, day, chapters, plan_days, chapter_voice, start_date, filename_lang, use_chapter_filename):
    from datetime import timedelta
    d = start_date + timedelta(days=day - 1)
    _ch_join = "-"
    day_padded = f"{day:03d}" if plan_days >= 100 else f"{day:02d}"

    if filename_lang == "ascii":
        eng_ch_str = chapters_to_filename(
            chapters, abbr=BOOK_FILENAME_ABBR, between_groups="_"
        )
        return f"{plan_id}-day{day_padded}-{eng_ch_str}"

    elif filename_lang == "en":
        eng_ch_str = chapters_to_filename(
            chapters, abbr=BOOK_FILENAME_ABBR, between_groups="-"
        )
        plan_name_clean = plan.get("name", plan_id).replace(" ", "-")
        return f"{plan_name_clean}-Day-{day_padded}-{eng_ch_str}"

    elif filename_lang == "zh-cn":
        from plan_utils import BOOK_FILENAME_ABBR_ZH_CN
        if plan_id in WISDOM_PRAISE_STYLE_PLANS:
            label = wisdom_praise_filename_label(plan_days, day, chapter_voice, lang="zh-cn")
            if use_chapter_filename:
                ch_str = chapters_to_filename(
                    chapters, abbr=BOOK_FILENAME_ABBR_ZH_CN, between_groups=_ch_join
                )
                return f"{label}-{ch_str}"
            else:
                prefix = d.strftime("%Y%m%d")
                return f"{prefix}-{label}"
        elif plan_id in CHRONO_STYLE_PLANS:
            label = chrono_filename_label(plan_id, day, chapter_voice, lang="zh-cn")
            if use_chapter_filename:
                ch_str = chapters_to_filename(
                    chapters, abbr=BOOK_FILENAME_ABBR_ZH_CN, between_groups=_ch_join
                )
                return f"{label}-{ch_str}"
            else:
                prefix = d.strftime("%Y%m%d")
                return f"{prefix}-{label}"
        elif use_chapter_filename:
            ch_str = chapters_to_filename(
                chapters, abbr=BOOK_FILENAME_ABBR_ZH_CN, between_groups=_ch_join
            )
            name_fmt = PLAN_FILENAME_ZH_CN.get(plan_id, "聆听第{i}天")
            return f"{name_fmt.format(i=day)}-{ch_str}"
        else:
            prefix = d.strftime("%Y%m%d")
            name_fmt = PLAN_FILENAME_ZH_CN.get(plan_id, "聆听第{i}天")
            return f"{prefix}-{name_fmt.format(i=day)}"

    else:  # zh-tw (default local)
        if plan_id in WISDOM_PRAISE_STYLE_PLANS:
            label = wisdom_praise_filename_label(plan_days, day, chapter_voice, lang="zh-tw")
            if use_chapter_filename:
                ch_str = chapters_to_filename(
                    chapters, abbr=BOOK_FILENAME_ABBR_ZH_TW, between_groups=_ch_join
                )
                return f"{label}-{ch_str}"
            else:
                prefix = d.strftime("%Y%m%d")
                return f"{prefix}-{label}"
        elif plan_id in CHRONO_STYLE_PLANS:
            label = chrono_filename_label(plan_id, day, chapter_voice, lang="zh-tw")
            if use_chapter_filename:
                ch_str = chapters_to_filename(
                    chapters, abbr=BOOK_FILENAME_ABBR_ZH_TW, between_groups=_ch_join
                )
                return f"{label}-{ch_str}"
            else:
                prefix = d.strftime("%Y%m%d")
                return f"{prefix}-{label}"
        elif use_chapter_filename:
            ch_str = chapters_to_filename(
                chapters, abbr=BOOK_FILENAME_ABBR_ZH_TW, between_groups=_ch_join
            )
            name_fmt = PLAN_FILENAME_ZH_TW.get(plan_id, "聆聽第{i}天")
            return f"{name_fmt.format(i=day)}-{ch_str}"
        else:
            prefix = d.strftime("%Y%m%d")
            name_fmt = PLAN_FILENAME_ZH_TW.get(plan_id, "聆聽第{i}天")
            return f"{prefix}-{name_fmt.format(i=day)}"


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate daily MP3s from a reading plan. "
            "Wisdom-praise / YV Psalms-Proverbs: see module docstring for descriptive stems."
        )
    )
    parser.add_argument("plan_id", help="Plan ID (e.g. chronological-1year)")
    parser.add_argument("-o", "--output", required=True, help="Output directory")
    parser.add_argument(
        "--speech-volume",
        type=int,
        default=4,
        help=(
            "Speech gain in dB (applied per chunk in concat_daily, then again in BGM mix; "
            "default 4). Everest/David Yen each have a base lift in concat_daily."
        ),
    )
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
        default="rotate",
        help=(
            "Everest/David Yen; duplicate modes read each chapter twice. "
            "duplicate_random use descriptive stems (see module docstring)."
        ),
    )
    parser.add_argument(
        "--duplicate-random-seed",
        type=int,
        default=None,
        metavar="N",
        help="For duplicate_random: reproducible per-chapter order (omit = random)",
    )
    parser.add_argument("--bgm-splits", type=int, default=1,
                        help="Split BGM output into N files (1x->3, 1.5x->2, 2x->1)")
    parser.add_argument("--start-date", type=str, default="2026-02-17",
                        help="First day date YYYY-MM-DD")
    parser.add_argument("--start-day", type=int, default=1)
    parser.add_argument("--end-day", type=int, default=None)
    parser.add_argument(
        "--use-chapter-filename",
        action="store_true",
        help=(
            "Day+chapter base (e.g. 90天智慧讚美第01天-詩1-箴1; 對照 = parallel version)"
        ),
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
    parser.add_argument(
        "--audio-lang",
        type=str,
        choices=["zh-tw", "zh-cn", "en"],
        default="zh-tw",
        help="Voice/audio content language (default: zh-tw)",
    )
    parser.add_argument(
        "--filename-lang",
        type=str,
        choices=["ascii", "zh-tw", "zh-cn", "en"],
        default="ascii",
        help="Output filename language format (ascii, zh-tw, zh-cn, en; default: ascii)",
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
    if args.filename_lang == "zh-cn":
        name_fmt = PLAN_FILENAME_ZH_CN.get(args.plan_id, "聆听第{i}天")
    else:
        name_fmt = PLAN_FILENAME_ZH_TW.get(args.plan_id, "聆聽第{i}天")
    plan_days = plan["days"]
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
        _ch_join = "-"

        # Construct the language-aware base filename
        base_name = construct_base_name(
            args.plan_id, plan, day, chapters, plan_days,
            args.chapter_voice, start_date, args.filename_lang, args.use_chapter_filename
        )

        # 3. Audio generation and file mapping
        if args.bgm:
            splits = args.bgm_splits
            groups = split_chapters(chapters, splits)
            for i, group in enumerate(groups):
                spec = ",".join(group)
                
                # Determine suffix format based on filename language
                if args.filename_lang in ("ascii", "en"):
                    suffix = get_bgm_suffix_eng(args.speed, i, splits)
                else:
                    suffix = get_bgm_suffix(args.speed, i, splits)

                if args.no_speed_label:
                    filename = base_name
                else:
                    filename = f"{base_name}_{suffix}"

                # Append custom suffix
                if args.filename_suffix and "對照" in args.filename_suffix and args.filename_lang == "zh-cn":
                    filename += "-对照"
                elif args.filename_suffix:
                    filename += args.filename_suffix

                out_file = out_dir / f"{filename}.mp3"

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
                    cmd.extend(["--voice-rotation-start", str(day)])
                if args.duplicate_random_seed is not None:
                    cmd.extend(["--duplicate-random-seed", str(args.duplicate_random_seed)])

                # Run execution
                subprocess.run(cmd, check=True)
                print(f"Day {day}: Generated {out_file.name}")
        else:
            # Plain: 1x only, no speed suffix
            spec = ",".join(chapters)
            filename = base_name
            if args.filename_suffix:
                filename += args.filename_suffix
            out_file = out_dir / f"{filename}.mp3"

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
                cmd.extend(["--voice-rotation-start", str(day)])
            if args.duplicate_random_seed is not None:
                cmd.extend(["--duplicate-random-seed", str(args.duplicate_random_seed)])

            # Run execution
            subprocess.run(cmd, check=True)
            print(f"Day {day}: Generated {out_file.name}")

    print(f"Done. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
