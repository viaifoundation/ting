#!/usr/bin/env python3
"""
Concatenate chapter MP3s into one daily audio file.
Optional: add background music, adjust volumes, and append translation comparisons.

Usage:
  python scripts/concat_daily.py --chapters "1:1,1:2,2:1" --output daily_001.mp3
  python scripts/concat_daily.py --chapters "1:1,1:2" --output day.mp3 --bgm --bgm-volume -20 --speech-volume 2

  # Play each chapter in CUV Everest, then compare with cuvt and ncvs TTS:
  python scripts/concat_daily.py --chapters "19:1,19:2" -o day.mp3 \
    --compare --trans cuvt,ncvs

Chapter format: book:chapter (e.g. 1:1 = Genesis 1, 43:16 = John 16).
Requires: pydub, ffmpeg (for pydub mp3 support), edge-tts (for TTS generation).
"""

import argparse
import random
import time
from pathlib import Path

import subprocess
import tempfile
import json
from pydub import AudioSegment

# Import from repo root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audio_mixer

# Recorded CUV narration (assets/bible/audio/chapters vs chapters_davidyen):
# Everest is mastered quieter; David Yen tends to read hotter. Gains are applied before
# --speech-volume. Keep these in sync with devotion_tts/chapter_narration_gain.py.
NARRATION_BOOST_DAVIDYEN_DB = -1.0  # male (David Yen)
NARRATION_BOOST_EVEREST_DB = 8.5  # female (Everest)

# Translation name → DB column (must match generate_psalms_tts.TRANSLATION_COLUMNS)
TRANSLATION_COLUMNS: dict[str, str] = {
    "cuvc": "cuvc",   # CUV Simplified (default primary)
    "cuvs": "cuvc",   # alias for cuvc
    "cuvt": "cuvt",   # CUV Traditional
    "ncvs": "ncvs",   # New Chinese Version Simplified
    "lcvs": "lcvs",   # Living Chinese Version
    "clbs": "clbs",   # Chinese Living Bible Simplified
}


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


def _load_mp3(path: Path, max_retries: int = 2) -> AudioSegment:
    """Load MP3 with retry for intermittent ffprobe JSONDecodeError."""
    last_err = None
    for attempt in range(max_retries):
        try:
            return AudioSegment.from_mp3(str(path))
        except json.JSONDecodeError as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
            else:
                raise RuntimeError(
                    f"Failed to load {path}: ffprobe returned invalid output (try re-downloading the chapter)"
                ) from e
    raise last_err


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
    parser.add_argument("--chapters-dir-davidyen", type=str, default=None, help="David Yen chapters dir")
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
            "Everest (female) / David Yen (male). "
            "male_then_female / female_then_male: same chapter twice in that order. "
            "duplicate_random: twice per chapter, order randomized. "
            "rotate: alternate each chapter, single pass."
        ),
    )
    parser.add_argument(
        "--duplicate-random-seed",
        type=int,
        default=None,
        metavar="N",
        help=(
            "With duplicate_random: optional seed so each chapter's order is reproducible; "
            "omit for non-deterministic order (SystemRandom)."
        ),
    )
    parser.add_argument("--voice-rotation-start", type=int, default=0, help="Starting index for voice rotation (e.g. use day number)")
    parser.add_argument("--use-tts", action="store_true", help="Use TTS chapters instead of Everest")
    parser.add_argument("--interleave-tts", action="store_true", help="Interleave Everest and TTS chapters (Everest then TTS)")
    parser.add_argument(
        "--compare",
        action="store_true",
        default=False,
        help=(
            "After each chapter, append TTS audio for comparison translations. "
            "Use --trans to specify which ones (default: cuvc). "
            "The primary CUV audio plays first (Everest or TTS), then each comparison translation."
        ),
    )
    parser.add_argument(
        "--trans",
        type=str,
        default="cuvc",
        help=(
            "Comma-separated translation names for comparison (used with "
            "--compare). Supported: cuvc/cuvs, cuvt, ncvs, lcvs, clbs. "
            "Example: 'cuvt,ncvs,clbs' (default: cuvc)"
        ),
    )
    parser.add_argument("--gap-ms", type=int, default=500, help="Silence between chapters/segments (ms)")

    # BGM
    parser.add_argument("--bgm", action="store_true", help="Add background music")
    parser.add_argument("--bgm-track", type=str, default=None, help="BGM filename (default: rotate from assets/bgm)")
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

    # Validate compare-translation names
    compare_translations: list[str] = []
    if args.compare:
        raw_names = [n.strip() for n in args.trans.split(",") if n.strip()]
        if not raw_names:
            raw_names = ["cuvc"]
        for name in raw_names:
            if name not in TRANSLATION_COLUMNS:
                print(f"⚠️  Unknown or unavailable translation '{name}'. "
                      f"Skipping. Supported: {', '.join(sorted(TRANSLATION_COLUMNS))}")
                continue
            compare_translations.append(name)
        print(f"🔄 Translation comparison enabled: {', '.join(compare_translations)}")

    # Paths
    repo_root = Path(__file__).resolve().parent.parent
    default_dir = "chapters_tts" if args.use_tts else "chapters"
    chapters_dir = Path(args.chapters_dir) if args.chapters_dir else repo_root / "assets" / "bible" / "audio" / default_dir
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    if not args.interleave_tts and not compare_translations and not chapters_dir.exists():
        print(f"❌ Chapters directory not found: {chapters_dir}")
        if args.use_tts:
            print("   Run: python scripts/generate_psalms_tts.py")
        else:
            print("   Run: python scripts/download_everest_audio.py")
        return 1

    tts_dir = repo_root / "assets" / "bible" / "audio" / "chapters_tts"
    everest_dir = repo_root / "assets" / "bible" / "audio" / "chapters"
    davidyen_dir = Path(args.chapters_dir_davidyen) if args.chapters_dir_davidyen else repo_root / "assets" / "bible" / "audio" / "chapters_davidyen"

    # Load and concatenate
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=args.gap_ms)

    # Voice rotation counter (initialized from arg to allow cross-day continuity)
    voice_rotation_idx = args.voice_rotation_start

    _dup_modes = ("male_then_female", "female_then_male", "duplicate_random")
    if args.chapter_voice in _dup_modes and args.use_tts:
        print(
            f"⚠️  --chapter-voice {args.chapter_voice} with --use-tts: "
            "each chapter plays once (single TTS voice)."
        )

    for book, chapter in pairs:
        fname = f"{book:03d}_{chapter:03d}.mp3"

        if args.interleave_tts:
            # 1. Everest
            path_ev = everest_dir / fname
            if path_ev.exists():
                seg_ev = _load_mp3(path_ev)
                seg_ev = seg_ev + NARRATION_BOOST_EVEREST_DB
                if args.speed > 1.0:
                    seg_ev = _speedup_ffmpeg(seg_ev, args.speed)
                combined += seg_ev + silence
            else:
                print(f"⚠️ Missing Everest: {path_ev}")

            # 2. Primary TTS (cuvc)
            path_tts = tts_dir / fname
            if not path_tts.exists():
                print(f"  Generating missing TTS on the fly: {fname}")
                subprocess.run([
                    sys.executable, str(repo_root / "scripts" / "generate_psalms_tts.py"),
                    "--book", str(book), "--start", str(chapter), "--end", str(chapter)
                ], check=False)

            if path_tts.exists():
                combined += _load_mp3(path_tts) + silence
            else:
                print(f"⚠️ Missing TTS (Generation failed): {path_tts}")

            # 3. Comparison translations (if enabled)
            for trans_name in compare_translations:
                trans_dir = (repo_root / "assets" / "bible" / "audio" / "chapters_tts"
                             if trans_name in ("cuvc", "cuvs")
                             else repo_root / "assets" / "bible" / "audio" / f"chapters_tts_{trans_name}")
                path_trans = trans_dir / fname
                if not path_trans.exists():
                    print(f"  Generating missing {trans_name} TTS on the fly: {fname}")
                    subprocess.run([
                        sys.executable, str(repo_root / "scripts" / "generate_psalms_tts.py"),
                        "--book", str(book), "--start", str(chapter), "--end", str(chapter),
                        "--translation", trans_name,
                    ], check=False)
                if path_trans.exists():
                    combined += _load_mp3(path_trans) + silence
                else:
                    print(f"⚠️ Missing {trans_name} TTS (generation failed): {path_trans}")

        else:
            mode = args.chapter_voice

            def append_primary_for_source(current_source: str) -> None:
                nonlocal combined
                path_ev = everest_dir / fname
                path_dy = davidyen_dir / fname
                if current_source == "davidyen":
                    path = path_dy if path_dy.exists() else path_ev
                    is_davidyen = path == path_dy
                else:
                    path = path_ev if path_ev.exists() else path_dy
                    is_davidyen = path == path_dy

                if not path.exists() and args.use_tts:
                    print(f"  Generating missing TTS on the fly: {fname}")
                    subprocess.run([
                        sys.executable, str(repo_root / "scripts" / "generate_psalms_tts.py"),
                        "--book", str(book), "--start", str(chapter), "--end", str(chapter)
                    ], check=False)
                    path = tts_dir / fname
                    is_davidyen = False

                if not path.exists():
                    print(f"⚠️ Missing: {path}")
                    return

                seg = _load_mp3(path)
                if not args.use_tts and path.parent != tts_dir:
                    base_boost = (
                        NARRATION_BOOST_DAVIDYEN_DB
                        if is_davidyen
                        else NARRATION_BOOST_EVEREST_DB
                    )
                    seg = seg + base_boost
                if args.speech_volume != 0:
                    seg = seg + args.speech_volume
                if args.speed > 1.0 and not args.use_tts and path.parent != tts_dir:
                    seg = _speedup_ffmpeg(seg, args.speed)
                combined += seg + silence

            # Per-chapter: one or two primary passes, then optional comparison TTS
            if mode == "male_then_female" and not args.use_tts:
                source_order = ("davidyen", "everest")
            elif mode == "female_then_male" and not args.use_tts:
                source_order = ("everest", "davidyen")
            elif mode == "duplicate_random" and not args.use_tts:
                if args.duplicate_random_seed is not None:
                    lr = random.Random((args.duplicate_random_seed, book, chapter))
                else:
                    lr = random.SystemRandom()
                if lr.random() < 0.5:
                    source_order = ("davidyen", "everest")
                else:
                    source_order = ("everest", "davidyen")
            elif mode in _dup_modes:
                source_order = ("everest",)  # single TTS pass with --use-tts
            else:
                if mode == "rotate":
                    current_source = "everest" if voice_rotation_idx % 2 == 0 else "davidyen"
                    voice_rotation_idx += 1
                elif mode == "male":
                    current_source = "davidyen"
                else:
                    current_source = "everest"
                source_order = (current_source,)

            for current_source in source_order:
                append_primary_for_source(current_source)

            # Comparison translations (non-interleave mode): once per logical chapter
            for trans_name in compare_translations:
                trans_dir = (repo_root / "assets" / "bible" / "audio" / "chapters_tts"
                             if trans_name in ("cuvc", "cuvs")
                             else repo_root / "assets" / "bible" / "audio" / f"chapters_tts_{trans_name}")
                path_trans = trans_dir / fname
                if not path_trans.exists():
                    print(f"  Generating missing {trans_name} TTS on the fly: {fname}")
                    subprocess.run([
                        sys.executable, str(repo_root / "scripts" / "generate_psalms_tts.py"),
                        "--book", str(book), "--start", str(chapter), "--end", str(chapter),
                        "--translation", trans_name,
                    ], check=False)
                if path_trans.exists():
                    combined += _load_mp3(path_trans) + silence
                else:
                    print(f"⚠️ Missing {trans_name} TTS (generation failed): {path_trans}")

    if len(combined) == 0:
        print("❌ No chapters loaded")
        return 1

    # Trim trailing silence
    combined = combined[:-args.gap_ms] if args.gap_ms > 0 else combined

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
