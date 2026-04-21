#!/usr/bin/env python3
"""
Psalms + Proverbs reading-plan runner (script: psprov.py; ps = Psalms, prov = Proverbs).
Any plan length. Does not replace wisdompraise.py.

Voice modes (--voice-mode):
  male_female (default) — each chapter twice: male then female
  female_male — each chapter twice: female then male
  duplicate_random — each chapter twice, male-first vs female-first randomized per chapter
  male / female — single voice, one pass per chapter
  rotate — alternate by chapter, one pass per chapter (no duplicate)

YouVersion presets (--preset; sets plan + voice; ignores --plan / --voice-mode):
  yv31-rotate   — 31-day plan, rotate only (no repeat per chapter)
  yv31-mf       — 31-day plan, male then female (each chapter twice)
  yv372-rotate  — 372-day plan, rotate only
  yv372-mf      — 372-day plan, male then female

List presets:  python scripts/psprov.py --list-presets

Output MP3 bases (via generate_plan_audio --use-chapter-filename):
  {N}天智慧讚美第{dd}天-… OR {N}天智慧讚美對照第{dd}天-…
(male_female, female_male, duplicate_random); hyphens between parts.

Recommended default plan: wisdom-praise-90days. Alternatives: 60 / 45 / 30 days.

Usage:
  python scripts/psprov.py 1
  python scripts/psprov.py 1-7 --voice-mode male
  python scripts/psprov.py 1-90 --voice-mode rotate
  python scripts/psprov.py 1-31 --preset yv31-rotate
  python scripts/psprov.py 1-372 --preset yv372-mf
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

# Best balance of sustainability vs finishing Psalms + Proverbs: 90 days.
DEFAULT_PLAN_ID = "wisdom-praise-90days"

# YouVersion Psalms & Proverbs: preset name → (plan_id, voice_mode key)
YV_PRESETS: dict[str, tuple[str, str] | list[tuple[str, str]]] = {
    "yv31-rotate": ("psalms-proverbs-youversion-31", "rotate"),
    "yv31-mf": ("psalms-proverbs-youversion-31", "male_female"),
    "yv372-rotate": ("psalms-proverbs-youversion-372", "rotate"),
    "yv372-mf": ("psalms-proverbs-youversion-372", "male_female"),
    "yv-all": [
        ("psalms-proverbs-youversion-31", "male_female"),
        ("psalms-proverbs-youversion-31", "rotate"),
        ("psalms-proverbs-youversion-372", "male_female"),
        ("psalms-proverbs-youversion-372", "rotate"),
    ],
}

YV_PRESET_BLURBS: dict[str, str] = {
    "yv31-rotate": "YouVersion 31-day; alternate narrators each chapter (single pass)",
    "yv31-mf": "YouVersion 31-day; each chapter male→female (two passes)",
    "yv372-rotate": "YouVersion 372-day; alternate narrators (single pass)",
    "yv372-mf": "YouVersion 372-day; each chapter male→female (two passes)",
    "yv-all": "Bundle: generate both 31 and 372 days, in both male-then-female and rotate modes (4 files per day)",
}

# CLI --voice-mode → generate_plan_audio --chapter-voice
VOICE_MODE_TO_CHAPTER_VOICE = {
    "male_female": "male_then_female",
    "female_male": "female_then_male",
    "duplicate_random": "duplicate_random",
    "male": "male",
    "female": "female",
    "rotate": "rotate",
}

DEFAULT_VOICE_MODE = "male_female"

AUDIO_SUBDIR_BY_MODE = {
    "male_female": "male-female",
    "female_male": "female-male",
    "duplicate_random": "dup-random",
    "male": "male",
    "female": "female",
    "rotate": "rotate",
}


def format_presets_help() -> str:
    """Human-readable preset and plan reference for --list-presets / epilog."""
    lines = [
        "Presets (--preset NAME; overrides --plan and --voice-mode):",
        "",
    ]
    for name in sorted(YV_PRESETS.keys()):
        plan_id, vm = YV_PRESETS[name]
        blurb = YV_PRESET_BLURBS.get(name, "")
        lines.append(f"  {name}")
        lines.append(f"      plan: {plan_id}  |  voice-mode: {vm}")
        if blurb:
            lines.append(f"      {blurb}")
        lines.append("")
    lines.extend(
        [
            "Manual plans (use --plan PLAN_ID with --voice-mode):",
            f"  wisdom-praise-30days, wisdom-praise-45days, wisdom-praise-60days, "
            f"{DEFAULT_PLAN_ID}",
            "  psalms-proverbs-youversion-31, psalms-proverbs-youversion-372",
            "",
            "Voice modes (--voice-mode; ignored when --preset is set):",
            "  " + ", ".join(sorted(VOICE_MODE_TO_CHAPTER_VOICE.keys())),
            "",
            "  {N}天智慧讚美第{dd}天-<abbr>  OR  {N}天智慧讚美對照第{dd}天-<abbr>",
            "(對照 = parallel version; male_female, female_male, duplicate_random)",
            "",
        ]
    )
    return "\n".join(lines).rstrip()


def print_presets() -> None:
    print(format_presets_help())


def parse_day_range(spec: str) -> list[int]:
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
            "Psalms & Proverbs plan audio (30–372+ days). "
            "Default: duplicate male→female per chapter; or rotate / single voice. "
            f"Default plan: {DEFAULT_PLAN_ID}. "
            "Use --preset for YouVersion 31/372 schedules. "
            "Filenames: {N}天智慧讚美 (see --list-presets)."
        ),
        epilog="Run with --list-presets for all --preset names, --plan ids, and --voice-mode values.",
    )
    parser.add_argument(
        "days",
        type=str,
        nargs="?",
        default=None,
        help="Day number or range (e.g. 1-5); required unless --list-presets",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Print presets, manual plans, and voice modes; then exit",
    )
    parser.add_argument(
        "--preset",
        type=str,
        choices=list(YV_PRESETS.keys()),
        default=None,
        metavar="NAME",
        help=(
            "YouVersion Psalms+Proverbs: yv31-rotate / yv31-mf / yv372-rotate / yv372-mf / yv-all "
            "(overrides --plan and --voice-mode)"
        ),
    )
    parser.add_argument(
        "--plan",
        type=str,
        default=DEFAULT_PLAN_ID,
        metavar="PLAN_ID",
        help=(
            f"Default: {DEFAULT_PLAN_ID}. "
            "Also: wisdom-praise-60days, wisdom-praise-45days, wisdom-praise-30days, "
            "psalms-proverbs-youversion-31, psalms-proverbs-youversion-372"
        ),
    )
    parser.add_argument(
        "--voice-mode",
        type=str,
        choices=list(VOICE_MODE_TO_CHAPTER_VOICE.keys()),
        default=DEFAULT_VOICE_MODE,
        metavar="MODE",
        help=(
            "male_female (default): twice per chapter, male→female; "
            "female_male: twice, female→male; duplicate_random: twice, order random per chapter; "
            "male/female: single voice; rotate: alternate, no duplicate. "
            "Ignored if --preset is set."
        ),
    )
    parser.add_argument(
        "--duplicate-random-seed",
        type=int,
        default=None,
        metavar="N",
        help="With duplicate_random: seed for reproducible order per chapter (omit = non-deterministic)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output directory (default: audio/<plan_id>-<mode>/)",
    )
    parser.add_argument("--speech-volume", type=int, default=4)
    parser.add_argument("--use-tts", action="store_true")
    parser.add_argument(
        "--interleave-tts",
        action="store_true",
        help="Interleave Everest and TTS per chapter (unusual with double voice)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="After each chapter's primary audio, append comparison TTS per --trans",
    )
    parser.add_argument(
        "--trans",
        type=str,
        default="cuvc",
        help="Comma-separated translations for --compare",
    )
    args = parser.parse_args()

    if args.list_presets:
        print_presets()
        return 0

    if args.days is None:
        parser.error("argument days: required unless you pass --list-presets")

    if args.preset:
        configs = YV_PRESETS[args.preset]
        if isinstance(configs, tuple):
            configs = [configs]
    else:
        configs = [(args.plan.strip(), args.voice_mode)]

    try:
        requested_days = parse_day_range(args.days)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    plan_cache = {}
    generate_script = REPO_ROOT / "scripts" / "generate_plan_audio.py"

    print("\n" + "=" * 60, flush=True)
    print(f"Runner: {Path(__file__).name} | Days: {args.days} | preset: {args.preset or 'none'}")
    print("=" * 60, flush=True)

    for day_num in requested_days:
        print(f"\n--- Day {day_num} ---", flush=True)
        for p_id, v_mode in configs:
            if p_id not in plan_cache:
                p_path = REPO_ROOT / "assets" / "bible" / "plans" / f"{p_id}.json"
                if not p_path.exists():
                    print(f"⚠️  Plan not found: {p_id}, skipping.")
                    continue
                plan_cache[p_id] = load_plan(p_path)

            plan = plan_cache[p_id]
            max_day = plan["days"]
            if day_num > max_day:
                print(f"⏭️  {p_id} (max {max_day}): skipping.")
                continue

            entries_by_day = {e["day"]: e for e in plan["entries"]}
            entry = entries_by_day.get(day_num)
            if not entry or not entry.get("chapters"):
                print(f"⚠️  {p_id}: no chapters.")
                continue

            chapters = entry["chapters"]
            zh_cn = chapters_to_chinese(chapters, BOOK_CHINESE)
            en = chapters_to_english(chapters)
            sub = AUDIO_SUBDIR_BY_MODE[v_mode]
            out_dir = Path(args.output) if args.output else REPO_ROOT / "audio" / f"{p_id}-{sub}"
            out_dir.mkdir(parents=True, exist_ok=True)
            ch_voice = VOICE_MODE_TO_CHAPTER_VOICE[v_mode]

            print(f"[{p_id} | {v_mode}] {zh_cn} ({en})", flush=True)

            cmd = [
                sys.executable,
                str(generate_script),
                p_id,
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

    print(f"\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
