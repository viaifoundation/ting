"""
Audio mixing utilities – background music and volume adjustment.
Adapted from devotion_tts (https://github.com/viaifoundation/devotion_tts).
"""

import os
import random
from typing import Optional

from pydub import AudioSegment


def mix_bgm(
    speech_audio: AudioSegment,
    bgm_dir: str = "assets/bgm",
    volume_db: int = -20,
    intro_delay_ms: int = 4000,
    specific_filename: Optional[str] = None,
    tail_delay_ms: int = 3000,
    speech_volume_db: int = 0,
    track_index: Optional[int] = None,
) -> AudioSegment:
    """
    Mixes speech audio with a background music track.

    Args:
        speech_audio: The spoken audio segment.
        bgm_dir: Directory containing mp3/wav/m4a background music files.
        volume_db: Volume adjustment for the background music (e.g. -20 = quieter).
        intro_delay_ms: How long the music plays before speech starts (ms).
        specific_filename: Optional filename to force use of a specific track.
        tail_delay_ms: How long the music plays after speech ends (ms).
        speech_volume_db: Volume adjustment for speech (e.g. 3 = louder, -3 = quieter). 0 = no change.
        track_index: When set (and no specific_filename), rotate through tracks: files[index % len(files)].

    Returns:
        AudioSegment: The mixed audio.
    """
    if not os.path.exists(bgm_dir):
        print(f"⚠️ BGM directory not found: {bgm_dir}. Skipping BGM.")
        return _apply_speech_volume(speech_audio, speech_volume_db)

    # Select track
    bgm_file = None
    if specific_filename:
        if os.path.exists(os.path.join(bgm_dir, specific_filename)):
            bgm_file = specific_filename
        else:
            print(f"⚠️ BGM file {specific_filename} not found in {bgm_dir}. Falling back to random.")

    if not bgm_file:
        files = sorted([f for f in os.listdir(bgm_dir) if f.lower().endswith((".mp3", ".wav", ".m4a"))])
        if not files:
            print(f"⚠️ No music files in {bgm_dir}. Skipping BGM.")
            return _apply_speech_volume(speech_audio, speech_volume_db)
        if track_index is not None:
            bgm_file = files[track_index % len(files)]  # rotate; loop if not enough
        else:
            bgm_file = random.choice(files)

    bgm_path = os.path.join(bgm_dir, bgm_file)
    print(f"🎵 Adding background music: {bgm_file} (BGM: {volume_db}dB, speech: {speech_volume_db}dB)")

    try:
        bgm = AudioSegment.from_file(bgm_path)
    except Exception as e:
        print(f"❌ Error loading BGM {bgm_file}: {e}")
        return _apply_speech_volume(speech_audio, speech_volume_db)

    # Normalize BGM so rotated tracks have consistent volume (different sources = different levels)
    bgm = _normalize_bgm(bgm)

    # Adjust BGM volume
    bgm = bgm + volume_db

    # Adjust speech volume
    speech = _apply_speech_volume(speech_audio, speech_volume_db)

    # Total length = intro + speech + tail
    total_len = intro_delay_ms + len(speech) + tail_delay_ms

    # Loop BGM if shorter than needed
    if len(bgm) < total_len:
        loops = (total_len // len(bgm)) + 1
        bgm = bgm * loops
    bgm = bgm[:total_len]

    # Fade in/out BGM
    bgm = bgm.fade_in(2000).fade_out(tail_delay_ms)

    # Overlay speech onto BGM
    final_mix = bgm.overlay(speech, position=intro_delay_ms)
    return final_mix


def _normalize_bgm(audio: AudioSegment, target_dBFS: float = -18.0) -> AudioSegment:
    """Normalize BGM to target RMS so rotated tracks have consistent volume."""
    if audio.dBFS == float("-inf"):
        return audio  # silence
    change_db = target_dBFS - audio.dBFS
    return audio.apply_gain(change_db)


def _apply_speech_volume(audio: AudioSegment, volume_db: int) -> AudioSegment:
    """Apply volume adjustment to speech. 0 = no change."""
    if volume_db == 0:
        return audio
    return audio + volume_db
