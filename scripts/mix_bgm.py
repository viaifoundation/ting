#!/usr/bin/env python3
"""
Mix background music with any existing audio file.
Useful for post-processing a daily/concat output.

Adapted from devotion_tts (https://github.com/viaifoundation/devotion_tts).

Usage:
  python scripts/mix_bgm.py -i daily_001.mp3 -o daily_001_bgm.mp3 --bgm --bgm-volume -20
  python scripts/mix_bgm.py -i speech.mp3 --bgm-track AmazingGrace.mp3 --speech-volume 2
"""

import argparse
import sys
from pathlib import Path

from pydub import AudioSegment

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audio_mixer


def main():
    parser = argparse.ArgumentParser(
        description="Mix existing audio with background music",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/mix_bgm.py -i daily_001.mp3
  python scripts/mix_bgm.py -i speech.mp3 --bgm-track OHolyNight.mp3 --bgm-volume -10
  python scripts/mix_bgm.py -i speech.mp3 --bgm --speech-volume 2
"""
    )
    parser.add_argument("--input", "-i", required=True, help="Input audio (mp3/wav/m4a)")
    parser.add_argument("--output", "-o", help="Output file (default: input_bgm.mp3)")
    parser.add_argument("--bgm", action="store_true", help="Enable background music")
    parser.add_argument("--bgm-track", type=str, default=None, help="BGM filename")
    parser.add_argument("--bgm-dir", type=str, default="assets/bgm", help="BGM directory")
    parser.add_argument("--bgm-volume", type=int, default=-20, help="BGM volume in dB")
    parser.add_argument("--bgm-intro", type=int, default=4000, help="BGM intro delay (ms)")
    parser.add_argument("--bgm-tail", type=int, default=3000, help="BGM tail (ms)")
    parser.add_argument("--speech-volume", type=int, default=0, help="Speech volume in dB")

    args = parser.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        print(f"❌ Input not found: {inp}")
        return 1

    out = args.output
    if not out:
        base = inp.stem
        out = f"{inp.parent / base}_bgm.mp3"

    repo_root = Path(__file__).resolve().parent.parent
    bgm_dir = repo_root / args.bgm_dir

    speech = AudioSegment.from_file(str(inp))

    if args.bgm:
        mixed = audio_mixer.mix_bgm(
            speech,
            bgm_dir=str(bgm_dir),
            volume_db=args.bgm_volume,
            intro_delay_ms=args.bgm_intro,
            specific_filename=args.bgm_track,
            tail_delay_ms=args.bgm_tail,
            speech_volume_db=args.speech_volume,
        )
    else:
        if args.speech_volume != 0:
            mixed = speech + args.speech_volume
        else:
            mixed = speech

    mixed.export(out, format="mp3", bitrate="192k")
    print(f"✅ Saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
