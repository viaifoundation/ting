#!/usr/bin/env python3
"""
Generate TTS audio for Psalms using edge-tts and local bible.sqlite.
Outputs to assets/bible/audio/chapters_tts/019_XXX.mp3.
Pronounces Psalms chapters as "篇" instead of "章".
"""

import argparse
import asyncio
import os
import sqlite3
import edge_tts
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT.parent / "devotion_tts" / "assets" / "bible" / "db" / "bible.sqlite"
OUT_DIR = REPO_ROOT / "assets" / "bible" / "audio" / "chapters_tts"

VOICES = [
    "zh-CN-YunyangNeural",
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-YunxiaNeural"
]
RATE = "+0%"

async def generate_chapter_audio(book_num, chapter_num, text, out_file, voice):
    print(f"Generating {out_file.name} [{voice}] (length: {len(text)} chars)...")
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=RATE)
    await communicate.save(str(out_file))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1, help="Start chapter")
    parser.add_argument("--end", type=int, default=150, help="End chapter")
    parser.add_argument("--book", type=int, default=19, help="Book number (19 = Psalms)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} not found.")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Chinese numbers mapping if needed, but edge-tts handles digits well
    # e.g., edge-tts reads "第1篇" as "dì yì piān".

    async def run_all():
        for ch in range(args.start, args.end + 1):
            rows = conn.execute(
                "SELECT verse, cuvc FROM verses WHERE book=? AND chapter=? ORDER BY verse",
                (args.book, ch)
            ).fetchall()
            
            if not rows:
                print(f"No verses found for Book {args.book} Chapter {ch}.")
                continue
                
            # Filter empty verses and clean text (strip tags if any, though CUVC usually lacks tags)
            verses = []
            for r in rows:
                t = r["cuvc"]
                if t:
                    # Strip <FR> <WG> <WH> etc just in case
                    import re
                    t = re.sub(r'<[A-Za-z0-9]+>', '', t).strip()
                    verses.append(t)
                    
            if args.book == 19:
                prefix = f"诗篇第{ch}篇\n\n"
            else:
                prefix = f"第{ch}章\n\n"
                
            full_text = prefix + "\n".join(verses)
            voice = VOICES[(ch - 1) % len(VOICES)]
            
            out_file = OUT_DIR / f"{args.book:03d}_{ch:03d}.mp3"
            await generate_chapter_audio(args.book, ch, full_text, out_file, voice)
            
    asyncio.run(run_all())
    conn.close()
    print("Done!")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
