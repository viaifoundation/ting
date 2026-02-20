#!/usr/bin/env python3
"""
Download Everest Audio Bible ZIPs, unzip, and arrange as one MP3 per chapter
in assets/bible/audio/chapters/ as BBB_CCC.mp3 (book 1-66, chapter 1..N).

Usage: python scripts/download_everest_audio.py [--dry-run] [--start N] [--end N]
Requires: requests (pip install requests)
"""

import argparse
import shutil
import zipfile
from pathlib import Path

import requests

BASE_URL = "https://www.everestaudiobible.org/mp3/website/Everest_Audio_Bible_48k"

# Everest book codes (NN_XXX) for books 1-66
EVEREST_CODES = [
    "", "01_GEN", "02_EXO", "03_LEV", "04_NUM", "05_DEU", "06_JOS", "07_JDG", "08_RUT",
    "09_1SA", "10_2SA", "11_1KI", "12_2KI", "13_1CH", "14_2CH", "15_EZR", "16_NEH",
    "17_EST", "18_JOB", "19_PSA", "20_PRO", "21_ECC", "22_SNG", "23_ISA", "24_JER",
    "25_LAM", "26_EZK", "27_DAN", "28_HOS", "29_JOL", "30_AMO", "31_OBA", "32_JON",
    "33_MIC", "34_NAM", "35_HAB", "36_ZEP", "37_HAG", "38_ZEC", "39_MAL", "40_MAT",
    "41_MRK", "42_LUK", "43_JHN", "44_ACT", "45_ROM", "46_1CO", "47_2CO", "48_GAL",
    "49_EPH", "50_PHP", "51_COL", "52_1TH", "53_2TH", "54_1TI", "55_2TI", "56_TIT",
    "57_PHM", "58_HEB", "59_JAS", "60_1PE", "61_2PE", "62_1JN", "63_2JN", "64_3JN",
    "65_JUD", "66_REV",
]

# Chapter count per book (index 0 unused)
BOOK_CHAPTERS = [
    0, 50, 40, 27, 36, 34, 24, 21, 4, 31, 24, 22, 25, 29, 36, 10, 13, 10, 42, 150,
    31, 12, 8, 66, 52, 5, 48, 12, 14, 3, 9, 1, 4, 7, 3, 3, 3, 2, 14, 4, 28, 16, 24,
    21, 28, 16, 16, 13, 6, 6, 4, 4, 5, 3, 6, 4, 3, 1, 13, 5, 5, 3, 5, 1, 1, 1, 22,
]


def main():
    parser = argparse.ArgumentParser(description="Download Everest Audio Bible and arrange by chapter")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--start", type=int, default=1, help="First book (1-66)")
    parser.add_argument("--end", type=int, default=66, help="Last book (1-66)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    zips_dir = repo_root / "assets" / "bible" / "audio" / "zips"
    chapters_dir = repo_root / "assets" / "bible" / "audio" / "chapters"
    temp_extract = repo_root / "assets" / "bible" / "audio" / ".tmp_extract"

    zips_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir.mkdir(parents=True, exist_ok=True)
    temp_extract.mkdir(parents=True, exist_ok=True)

    print("Everest Audio Bible download -> chapters")
    print(f"  Zips:      {zips_dir}")
    print(f"  Chapters:  {chapters_dir}")
    print(f"  Books:     {args.start} .. {args.end}")
    if args.dry_run:
        print("  (dry run - no downloads)")
    print()

    failed = []

    for book in range(args.start, args.end + 1):
        if book >= len(EVEREST_CODES) or book < 1:
            continue
        code = EVEREST_CODES[book]
        expect_chapters = BOOK_CHAPTERS[book] if book < len(BOOK_CHAPTERS) else 0
        zip_name = f"{code}.zip"
        zip_path = zips_dir / zip_name

        if not code:
            print(f"Book {book}: skip (no code)")
            continue

        if args.dry_run:
            print(f"Book {book} ({code}): would download and extract ({expect_chapters} chapters)")
            continue

        # Download if missing
        if not zip_path.exists():
            print(f"Book {book} ({code}): downloading... ", end="", flush=True)
            try:
                r = requests.get(f"{BASE_URL}/{zip_name}", timeout=120, stream=True)
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                print("ok")
            except requests.RequestException as e:
                print(f"FAILED ({e})")
                failed.append(f"{book}:{zip_name}")
                if zip_path.exists():
                    zip_path.unlink()
                continue
        else:
            print(f"Book {book} ({code}): zip exists ", end="", flush=True)

        # Extract and arrange
        for f in temp_extract.iterdir():
            if f.is_file():
                f.unlink()
            else:
                shutil.rmtree(f)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_extract)
        except zipfile.BadZipFile as e:
            print(f"  unzip FAILED ({e})")
            failed.append(f"{book}:unzip")
            continue

        mp3s = sorted(temp_extract.rglob("*.mp3"))
        count = len(mp3s)
        if count == 0:
            print("  no MP3 files found")
            failed.append(f"{book}:no_mp3")
            continue

        if count != expect_chapters:
            print(f"  WARNING: expected {expect_chapters} chapters, found {count}")

        for ch, src in enumerate(mp3s, 1):
            dest = chapters_dir / f"{book:03d}_{ch:03d}.mp3"
            shutil.copy2(src, dest)
        print(f"  -> {count} chapters written")

    if temp_extract.exists():
        shutil.rmtree(temp_extract, ignore_errors=True)

    if failed:
        print(f"\nFailed: {' '.join(failed)}")
        return 1
    print(f"\nDone. Chapter files in {chapters_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
