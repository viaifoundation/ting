#!/usr/bin/env python3
"""
Daily Ting runner:
1. Computes reading plan day numbers for the target date (default: today in PDT).
2. Generates all 7 audio + text files (and optional MP4) into audio/<YYYYMMDD>/:
   - qt.py: 半年歷史時序 + 半年智慧讚美 (2 audios)
   - chrono.py: 年度歷史時序 (1 audio)
   - psprov.py: 31天 & 372天 智慧讚美 (輪流 + 對照, 4 audios)
3. Uploads the audio files to WordPress (https://ting.weiai.ai/).

Usage:
  python scripts/daily.py                 # Today's reading in PDT
  python scripts/daily.py 20260921        # Specific date
  python scripts/daily.py --date 2026-09-21
  python scripts/daily.py --no-upload     # Generate files only, skip WP upload
  python scripts/daily.py --mp4           # Also generate MP4 videos
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Anchor mapping: 2026-09-21 is day (127, 127, 150) ────────────────────────
ANCHOR_DATE = date(2026, 9, 21)
ANCHOR_QT_DAY = 127
ANCHOR_CHRONO_DAY = 127
ANCHOR_PSPROV_DAY = 150


def get_today_pdt() -> date:
    """Return today's date in America/Los_Angeles (PDT/PST)."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("America/Los_Angeles")
        return datetime.now(tz).date()
    except Exception:
        return datetime.now().date()


def parse_target_date(val: str | None) -> date:
    """Parse date string (YYYYMMDD or YYYY-MM-DD), default to today in PDT."""
    if not val:
        return get_today_pdt()
    cleaned = val.strip().replace("-", "")
    try:
        return datetime.strptime(cleaned, "%Y%m%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: '{val}'. Expected YYYYMMDD or YYYY-MM-DD.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daily Ting audio generation and WordPress upload orchestrator."
    )
    parser.add_argument(
        "pos_date",
        nargs="?",
        default=None,
        help="Target date (YYYYMMDD or YYYY-MM-DD, default: today in PDT)",
    )
    parser.add_argument(
        "--date",
        dest="flag_date",
        default=None,
        help="Target date (YYYYMMDD or YYYY-MM-DD, default: today in PDT)",
    )
    parser.add_argument(
        "--qt-day",
        type=int,
        default=None,
        help=f"Explicit day number for qt.py (default: computed from date)",
    )
    parser.add_argument(
        "--chrono-day",
        type=int,
        default=None,
        help=f"Explicit day number for chrono.py (default: computed from date)",
    )
    parser.add_argument(
        "--psprov-day",
        type=int,
        default=None,
        help=f"Explicit day number for psprov.py (default: computed from date)",
    )
    parser.add_argument(
        "--mp4",
        action="store_true",
        help="Enable MP4 video generation",
    )
    parser.add_argument(
        "--no-upload",
        "--skip-upload",
        dest="no_upload",
        action="store_true",
        help="Skip uploading audio to WordPress",
    )

    args = parser.parse_args()

    date_input = args.flag_date or args.pos_date
    try:
        target_date = parse_target_date(date_input)
    except ValueError as err:
        print(f"❌ {err}")
        return 1

    date_str = target_date.strftime("%Y%m%d")
    date_display = target_date.strftime("%Y-%m-%d")

    # Compute plan day numbers based on delta from anchor
    delta_days = (target_date - ANCHOR_DATE).days
    qt_day = args.qt_day if args.qt_day is not None else (ANCHOR_QT_DAY + delta_days)
    chrono_day = args.chrono_day if args.chrono_day is not None else (ANCHOR_CHRONO_DAY + delta_days)
    psprov_day = args.psprov_day if args.psprov_day is not None else (ANCHOR_PSPROV_DAY + delta_days)

    out_dir = REPO_ROOT / "audio" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    print("═" * 68)
    print(f"🎧 Ting Daily Orchestrator — {date_display} ({date_str})")
    print(f"   Output Directory : {out_dir}")
    print(f"   Day Numbers      : qt={qt_day}, chrono={chrono_day}, psprov={psprov_day}")
    print(f"   MP4 Video        : {'Enabled' if args.mp4 else 'Disabled'}")
    print(f"   WordPress Upload : {'Skip' if args.no_upload else 'Enabled'}")
    print("═" * 68)

    # 1. Run qt.py (半年歷史時序 + 半年智慧讚美)
    print(f"\n▶ [1/3] Running qt.py for Day {qt_day}...")
    cmd_qt = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "qt.py"),
        str(qt_day),
        "--date", date_str,
    ]
    if args.mp4:
        cmd_qt.append("--mp4")
    subprocess.run(cmd_qt, check=True)

    # 2. Run chrono.py (年度歷史時序)
    print(f"\n▶ [2/3] Running chrono.py for Day {chrono_day}...")
    cmd_chrono = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "chrono.py"),
        str(chrono_day),
        "--date", date_str,
    ]
    if args.mp4:
        cmd_chrono.append("--mp4")
    subprocess.run(cmd_chrono, check=True)

    # 3. Run psprov.py (31天 & 372天 智慧讚美: 輪流 + 對照)
    print(f"\n▶ [3/3] Running psprov.py for Day {psprov_day}...")
    cmd_psprov = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "psprov.py"),
        str(psprov_day),
        "--date", date_str,
    ]
    subprocess.run(cmd_psprov, check=True)

    # List generated files
    generated_mp3s = sorted(list(out_dir.glob("*.mp3")))
    print("\n" + "─" * 68)
    print(f"📁 Generated {len(generated_mp3s)} audio file(s) in {out_dir}:")
    for f in generated_mp3s:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"   • {f.name} ({size_mb:.1f} MB)")
    print("─" * 68)

    # 4. Upload to WordPress
    if args.no_upload:
        print("\n⏭️  Skipping WordPress upload (--no-upload specified).")
    else:
        print(f"\n▶ [Upload] Uploading {len(generated_mp3s)} audio files to WordPress...")
        upload_script = REPO_ROOT / "scripts" / "fast_upload_today.js"
        cmd_upload = [
            "node",
            str(upload_script),
            "--date", date_str,
        ]
        subprocess.run(cmd_upload, check=True)

    print("\n" + "═" * 68)
    print(f"🎉 All Ting daily tasks completed successfully for {date_display}!")
    print("═" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
