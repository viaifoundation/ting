#!/usr/bin/env python3
"""
Generate TTS audio for Bible chapters using edge-tts and local bible.sqlite.

Supported translation names (maps to DB columns):
  cuvc / cuvs  →  cuvc  (CUV Simplified Chinese)
  cuvt         →  cuvt  (CUV Traditional Chinese with Strong's tags)
  ncvs         →  ncvs  (New Chinese Version Simplified)
  lcvs         →  lcvs  (Living Chinese Version)
  clbs         →  clbs  (Chinese Living Bible Simplified)

Output directories per translation:
  assets/bible/audio/chapters_tts/         ← default (cuvc, backward-compat)
  assets/bible/audio/chapters_tts_<name>/  ← other translations

Pronounces Psalms (book 19) chapters as "篇" instead of "章".

Usage:
  python scripts/generate_psalms_tts.py                          # cuvc, all Psalms
  python scripts/generate_psalms_tts.py --start 1 --end 5
  python scripts/generate_psalms_tts.py --translation cuvt --book 19
  python scripts/generate_psalms_tts.py --translation ncvs --book 20 --start 1 --end 5
"""

import argparse
import asyncio
import os
import sqlite3
import edge_tts
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT.parent / "devotion_tts" / "assets" / "bible" / "db" / "bible.sqlite"
# Default output dir (cuvc, kept for backward compatibility)
DEFAULT_OUT_DIR = REPO_ROOT / "assets" / "bible" / "audio" / "chapters_tts"

# Supported translation name → DB column
TRANSLATION_COLUMNS: dict[str, str] = {
    "cuvc": "cuvc",   # CUV Simplified (default)
    "cuvs": "cuvc",   # alias for cuvc
    "cuvt": "cuvt",   # CUV Traditional (contains Strong's tags, stripped)
    "ncvs": "ncvs",   # New Chinese Version Simplified
    "lcvs": "lcvs",   # Living Chinese Version Simplified
    "clbs": "clbs",   # Chinese Living Bible Simplified
}

VOICES = [
    "zh-CN-YunyangNeural",
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-YunxiaNeural"
]
RATE = "+0%"


def get_out_dir(translation: str) -> Path:
    """Return the output directory for a given translation name."""
    if translation in ("cuvc", "cuvs"):
        return DEFAULT_OUT_DIR  # backward-compatible default
    return REPO_ROOT / "assets" / "bible" / "audio" / f"chapters_tts_{translation}"

async def generate_chapter_audio(book_num, chapter_num, text, out_file, voice):
    print(f"Generating {out_file.name} [{voice}] (length: {len(text)} chars)...")
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=RATE)
    await communicate.save(str(out_file))

def main():
    parser = argparse.ArgumentParser(
        description="Generate TTS audio for Bible chapters (edge-tts + local bible.sqlite)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Supported translations: cuvc (default/alias cuvs), cuvt, ncvs, lcvs, clbs

Examples:
  python scripts/generate_psalms_tts.py
  python scripts/generate_psalms_tts.py --start 1 --end 10
  python scripts/generate_psalms_tts.py --translation cuvt --book 19 --start 1 --end 5
  python scripts/generate_psalms_tts.py --translation ncvs --book 20 --start 1 --end 31"""
    )
    parser.add_argument("--start", type=int, default=1, help="Start chapter (default: 1)")
    parser.add_argument("--end", type=int, default=150, help="End chapter (default: 150)")
    parser.add_argument("--book", type=int, default=19, help="Book number (default: 19 = Psalms)")
    parser.add_argument(
        "--translation", "-t",
        type=str,
        default="cuvc",
        help="Translation to use: cuvc (default), cuvt, ncvs, lcvs, clbs (see --help for details)",
    )
    args = parser.parse_args()

    if args.translation not in TRANSLATION_COLUMNS:
        print(f"❌ Unknown translation '{args.translation}'. "
              f"Supported: {', '.join(sorted(TRANSLATION_COLUMNS))}")
        return 1
    col = TRANSLATION_COLUMNS[args.translation]

    if not DB_PATH.exists():
        print(f"❌ DB not found: {DB_PATH}")
        return 1

    out_dir = get_out_dir(args.translation)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Translation: {args.translation} (column: {col})")  
    print(f"Output dir:  {out_dir}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Chinese numbers mapping if needed, but edge-tts handles digits well
    # e.g., edge-tts reads "第1篇" as "dì yì piān".

    import re

    async def run_all():
        for ch in range(args.start, args.end + 1):
            rows = conn.execute(
                f"SELECT verse, {col} FROM verses WHERE book=? AND chapter=? ORDER BY verse",
                (args.book, ch)
            ).fetchall()

            if not rows:
                print(f"No verses found for Book {args.book} Chapter {ch}.")
                continue

            # Filter empty verses and strip Strong's/markup tags (e.g. <WH1234>)
            verses = []
            for r in rows:
                t = r[col]
                if t:
                    t = re.sub(r'<[A-Za-z0-9]+>', '', t).strip()
                    if t:
                        verses.append(t)

            if not verses:
                print(f"⚠️  No text for Book {args.book} Chapter {ch} in '{col}'.")
                continue

            if args.book == 19:
                prefix = f"诗篇第{ch}篇\n\n"
            else:
                prefix = f"第{ch}章\n\n"

            full_text = prefix + "\n".join(verses)
            voice = VOICES[(ch - 1) % len(VOICES)]

            out_file = out_dir / f"{args.book:03d}_{ch:03d}.mp3"
            await generate_chapter_audio(args.book, ch, full_text, out_file, voice)

    asyncio.run(run_all())
    conn.close()
    print("Done!")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
