#!/usr/bin/env python3
"""
Concatenate chapter MP3s into one daily audio file.
Optional: add background music and adjust volumes.

Usage:
  python scripts/concat_daily.py --chapters "1:1,1:2,2:1" --output daily_001.mp3
  python scripts/concat_daily.py --chapters "1:1,1:2" --output day.mp3 --bgm --bgm-volume -20 --speech-volume 2

Chapter format: book:chapter (e.g. 1:1 = Genesis 1, 43:16 = John 16).
Requires: pydub, ffmpeg (for pydub mp3 support).
"""

import argparse
from pathlib import Path

import subprocess
import tempfile
from pydub import AudioSegment

# Import from repo root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audio_mixer


def _speedup_ffmpeg(seg: AudioSegment, speed: float) -> AudioSegment:
    """Speed up using ffmpeg atempo (preserves pitch). Chains atempo for speed > 2."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_in = f.name
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_out = f.name
    try:
        seg.export(tmp_in, format="wav")
        # atempo accepts 0.5–2.0; chain for higher speeds (e.g. 3x = atempo=2,atempo=1.5)
        parts = []
        r = speed
        while r > 2.0:
            parts.append("atempo=2")
            r /= 2.0
        if r > 1.0:
            parts.append(f"atempo={r}")
        filter_str = ",".join(parts) if parts else "atempo=1"
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in, "-filter:a", filter_str, tmp_out],
            check=True, capture_output=True
        )
        return AudioSegment.from_wav(tmp_out)
    finally:
        Path(tmp_in).unlink(missing_ok=True)
        Path(tmp_out).unlink(missing_ok=True)


def parse_chapters(spec: str):
    """Parse '1:1,1:2,43:16' -> [(1,1), (1,2), (43,16)]."""
    pairs = []
    for part in spec.split(","):
        part = part.strip()
        if ":" in part:
            b, c = part.split(":", 1)
            pairs.append((int(b.strip()), int(c.strip())))
    return pairs


def main():
    parser = argparse.ArgumentParser(
        description="Concatenate chapter MP3s into one daily audio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Concat only
  python scripts/concat_daily.py --chapters "1:1,1:2,1:3" -o day_001.mp3

  # With background music and volume adjustments
  python scripts/concat_daily.py --chapters "1:1,1:2" -o day.mp3 --bgm --bgm-volume -20 --speech-volume 2

  # From file (one "book:chapter" per line)
  python scripts/concat_daily.py --chapters-file plan_day_1.txt -o day_001.mp3
"""
    )
    parser.add_argument("--chapters", "-c", type=str, help="Comma-separated book:chapter (e.g. 1:1,1:2,43:16)")
    parser.add_argument("--chapters-file", "-f", type=str, help="File with one book:chapter per line")
    parser.add_argument("--output", "-o", type=str, required=True, help="Output MP3 path")
    parser.add_argument("--chapters-dir", type=str, default=None, help="Chapters dir (default: assets/bible/audio/chapters)")
    parser.add_argument("--gap-ms", type=int, default=500, help="Silence between chapters (ms)")

    # BGM
    parser.add_argument("--bgm", action="store_true", help="Add background music")
    parser.add_argument("--bgm-track", type=str, default=None, help="BGM filename (default: random from assets/bgm)")
    parser.add_argument("--bgm-dir", type=str, default="assets/bgm", help="BGM directory")
    parser.add_argument("--bgm-volume", type=int, default=-20, help="BGM volume in dB")
    parser.add_argument("--bgm-intro", type=int, default=4000, help="BGM intro delay (ms)")
    parser.add_argument("--bgm-tail", type=int, default=3000, help="BGM tail after speech (ms)")

    # Volume & speed
    parser.add_argument("--speech-volume", type=int, default=0, help="Speech volume adjustment in dB (0 = no change)")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed (e.g. 2.0 = 2x, must be >= 1.0)")

    args = parser.parse_args()

    # Resolve chapters
    if args.chapters_file:
        text = Path(args.chapters_file).read_text()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        spec = ",".join(lines)
    elif args.chapters:
        spec = args.chapters
    else:
        parser.error("Provide --chapters or --chapters-file")

    pairs = parse_chapters(spec)
    if not pairs:
        parser.error("No valid chapters parsed")

    # Paths
    repo_root = Path(__file__).resolve().parent.parent
    chapters_dir = Path(args.chapters_dir) if args.chapters_dir else repo_root / "assets" / "bible" / "audio" / "chapters"
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    if not chapters_dir.exists():
        print(f"❌ Chapters directory not found: {chapters_dir}")
        print("   Run: python scripts/download_everest_audio.py")
        return 1

    # Load and concatenate
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=args.gap_ms)

    for book, chapter in pairs:
        fname = f"{book:03d}_{chapter:03d}.mp3"
        path = chapters_dir / fname
        if not path.exists():
            print(f"⚠️ Missing: {path}")
            continue
        seg = AudioSegment.from_mp3(path)
        combined += seg + silence

    if len(combined) == 0:
        print("❌ No chapters loaded")
        return 1

    # Trim trailing silence
    combined = combined[:-args.gap_ms] if args.gap_ms > 0 else combined

    # Apply speed (use ffmpeg atempo - pydub speedup is very slow for long audio)
    if args.speed > 1.0:
        combined = _speedup_ffmpeg(combined, args.speed)

    # Apply BGM or speech volume
    if args.bgm:
        combined = audio_mixer.mix_bgm(
            combined,
            bgm_dir=str(repo_root / args.bgm_dir),
            volume_db=args.bgm_volume,
            intro_delay_ms=args.bgm_intro,
            specific_filename=args.bgm_track,
            tail_delay_ms=args.bgm_tail,
            speech_volume_db=args.speech_volume,
        )
    elif args.speech_volume != 0:
        combined = combined + args.speech_volume

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(output_path), format="mp3", bitrate="320k")
    print(f"✅ Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
