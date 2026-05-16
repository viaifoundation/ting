#!/usr/bin/env python3
"""
Generate Chronological 6-Month reading plan audio (半年歷史讀經).

Two paired 186-day plans, two MP3 files per day:
  1. 半年歷史讀經第N天-{chapters}.mp3  — chronological reading
  2. 半年智慧讚美第N天-{psalms+proverbs}.mp3 — daily Psalms & Proverbs

Input is a day number (1–186) or a range (e.g. 1-5, 16-17).
Defaults: 1.5x speed, rotate voices, background music.
Day 76 is the Ps 119 special day (Ps 119 + Prov 1 + Prov 31, no Ps+Prov bonus).

Optionally generates an MP4 video alongside the MP3.

Usage:
  python scripts/chrono180.py 1              # Day 1 MP3s (chrono + Ps+Prov)
  python scripts/chrono180.py 1-7            # Days 1-7
  python scripts/chrono180.py 1-7 --mp4      # Days 1-7, also generate MP4 video
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from plan_utils import (
    BOOK_CHINESE,
    BOOK_CHINESE_TW,
    BOOK_FILENAME_ABBR_ZH_TW,
    chapters_to_chinese,
    chapters_to_english,
    chapters_to_filename,
    load_plan,
)

PLAN_ID = "chronological-6month"

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

def get_background_image() -> str | None:
    """Find the default background image, preferring .jpg then .png."""
    bg_dir = REPO_ROOT / "assets" / "background"
    jpg = bg_dir / "background.jpg"
    png = bg_dir / "background.png"
    if jpg.exists():
        return str(jpg)
    if png.exists():
        return str(png)
    return None

def create_mp4(mp3_path: str, mp4_path: str, bg_image: str, title: str) -> bool:
    """Run FFmpeg to create a video from audio and static image."""
    cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", bg_image,
        "-i", mp3_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-metadata", "artist=Bible Web App · VI AI Foundation",
        "-metadata", f"title={title}",
        "-metadata", "copyright=© 2025-2026 VI AI Foundation · 501(c)(3)",
        "-metadata", "comment=bibleweb.app | VI AI Foundation",
        "-metadata", "url=https://bibleweb.app",
        "-y", mp4_path
    ]
    
    print(f"🎬 Creating MP4: {Path(mp4_path).name}")
    try:
        # Check ffmpeg existence
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ MP4 Success!")
            return True
        else:
            print(f"❌ FFmpeg error:\n{result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ FFmpeg not found. Cannot create MP4.")
        return False
    except Exception as e:
        print(f"❌ Error creating MP4: {e}")
        return False

def main() -> int:
    parser = argparse.ArgumentParser(description="半年歷史讀經 + 半年智慧讚美 (186-day paired plans)")
    parser.add_argument("days", type=str, help="Day number (1–186) or range (e.g. 1-5)")
    parser.add_argument("--mp4", action="store_true", help="Generate MP4 video alongside chrono MP3")
    args = parser.parse_args()

    try:
        requested_days = parse_day_range(args.days)
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    # Load both plans
    chrono_path = REPO_ROOT / "assets" / "bible" / "plans" / f"{PLAN_ID}.json"
    psprov_path = REPO_ROOT / "assets" / "bible" / "plans" / "psalms-proverbs-186days.json"

    if not chrono_path.exists():
        print(f"❌ Plan not found: {chrono_path}. Run generate_6mo_plan.py first.")
        return 1
    if not psprov_path.exists():
        print(f"❌ Plan not found: {psprov_path}. Run generate_6mo_plan.py first.")
        return 1

    chrono_plan = load_plan(chrono_path)
    psprov_plan = load_plan(psprov_path)
    max_day = chrono_plan["days"]
    chrono_by_day = {e["day"]: e for e in chrono_plan["entries"]}
    psprov_by_day = {e["day"]: e for e in psprov_plan["entries"]}

    invalid = [d for d in requested_days if d < 1 or d > max_day]
    if invalid:
        print(f"❌ Day(s) out of range (plan has {max_day} days): {invalid}")
        return 1

    chrono_out = REPO_ROOT / "audio" / "chronological-6month-rotate"
    psprov_out = REPO_ROOT / "audio" / "psalms-proverbs-186days"
    chrono_out.mkdir(parents=True, exist_ok=True)
    psprov_out.mkdir(parents=True, exist_ok=True)
    generate_script = REPO_ROOT / "scripts" / "generate_plan_audio.py"

    bg_image = None
    if args.mp4:
        bg_image = get_background_image()
        if not bg_image:
            print("❌ Background image missing. Place background.jpg or .png in assets/background/")
            return 1

    for day_num in requested_days:
        chrono_entry = chrono_by_day.get(day_num)
        psprov_entry = psprov_by_day.get(day_num)

        # ── 1) Generate Chrono MP3 ────────────────────────────────────────
        if not chrono_entry or not chrono_entry.get("chapters"):
            print(f"⚠️  Day {day_num}: no chrono chapters, skipping.")
            continue

        chapters = chrono_entry["chapters"]
        ch_str = chapters_to_filename(chapters, abbr=BOOK_FILENAME_ABBR_ZH_TW, between_groups="-")

        cmd = [
            sys.executable, str(generate_script),
            PLAN_ID,
            "-o", str(chrono_out),
            "--start-day", str(day_num),
            "--end-day", str(day_num),
            "--use-chapter-filename",
            "--no-speed-label",
            "--speed", "1.5",
            "--bgm", "--bgm-splits", "1",
            "--chapter-voice", "rotate",
        ]

        print(f"\n{'─' * 50}")
        print(f"Day {day_num} — Chrono: {chapters_to_english(chapters)}")
        print(f"{'─' * 50}")
        subprocess.run(cmd, check=True)
        print(f"✅ 半年歷史讀經第{day_num}天-{ch_str}.mp3")

        # MP4 for chrono if requested
        if args.mp4:
            expected_filename = f"{chrono_plan['name_zh_tw']}第{day_num}天-{ch_str}.mp3"
            mp3_path = chrono_out / expected_filename
            if mp3_path.exists():
                mp4_path = mp3_path.with_suffix(".mp4")
                title = f"{chrono_plan['name_zh_tw']} Day {day_num} - {chapters_to_english(chapters)}"
                create_mp4(str(mp3_path), str(mp4_path), bg_image, title)
            else:
                print(f"❌ MP3 not found for MP4: {mp3_path}")

        # ── 2) Generate Ps+Prov MP3 ──────────────────────────────────────
        if not psprov_entry or not psprov_entry.get("chapters"):
            print(f"⏭️  Day {day_num}: Ps+Prov skipped (Ps 119 day)")
            continue

        psprov_chapters = psprov_entry["chapters"]
        pp_str = chapters_to_filename(psprov_chapters, abbr=BOOK_FILENAME_ABBR_ZH_TW, between_groups="-")

        cmd_pp = [
            sys.executable, str(generate_script),
            "psalms-proverbs-186days",
            "-o", str(psprov_out),
            "--start-day", str(day_num),
            "--end-day", str(day_num),
            "--use-chapter-filename",
            "--no-speed-label",
            "--speed", "1.5",
            "--bgm", "--bgm-splits", "1",
            "--chapter-voice", "rotate",
        ]

        print(f"\nDay {day_num} — Ps+Prov: {chapters_to_english(psprov_chapters)}")
        subprocess.run(cmd_pp, check=True)
        print(f"✅ 半年智慧讚美第{day_num}天-{pp_str}.mp3")

    print(f"\nDone.")
    print(f"  Chrono:  {chrono_out}")
    print(f"  Ps+Prov: {psprov_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

